import type { FastifyInstance } from "fastify";
import type {
  RegisterDeviceBody,
  RegisterDeviceResponse,
  ListDevicesResponse,
  ErrorResponse,
} from "../types.js";
import { globalDeviceRegistry } from "../../registry/device_registry.js";
import { globalPluginSystem } from "../../plugins/plugin_system.js";
import type { DeviceAdapterConfig } from "@neuroos/shared-contracts/schema";
import { createLogger } from "../../logger.js";

const logger = createLogger("DevicesRoute");

const BUILT_IN_ADAPTERS = new Set(["neuroos-simulator", "openbci-cyton"]);

export async function devicesRoutes(fastify: FastifyInstance): Promise<void> {
  fastify.post<{
    Body: RegisterDeviceBody;
    Reply: RegisterDeviceResponse | ErrorResponse;
  }>("/devices/register", async (request, reply) => {
    const { adapterName, config = {} } = request.body;

    const adapterConfig: DeviceAdapterConfig = {
      sampleRateHz: config.sampleRateHz ?? 256,
      numChannels: config.numChannels ?? 16,
      channelLabels: config.channelLabels ?? null,
      samplesPerFrame: config.samplesPerFrame ?? 16,
      hardwareFilter: config.hardwareFilter ?? false,
      driverOptions: config.driverOptions ?? {},
    };

    try {
      if (BUILT_IN_ADAPTERS.has(adapterName)) {
        const { SimulatorAdapter } = await import("../../adapters/simulator_adapter.js");
        const adapter = new SimulatorAdapter(adapterConfig);
        globalDeviceRegistry.register(adapter);
        return reply.code(200).send({ deviceId: adapter.deviceId, state: adapter.state });
      }

      const pluginPath = config.pluginPath ?? adapterName;
      const adapter = await globalPluginSystem.loadAndRegisterPlugin(pluginPath, adapterConfig);
      return reply.code(200).send({ deviceId: adapter.deviceId, state: adapter.state });
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : String(err);
      logger.error(`Failed to register adapter "${adapterName}": ${message}`);

      if (message.includes("already registered")) {
        return reply.code(409).send({
          error: "DEVICE_ALREADY_REGISTERED",
          message,
        });
      }

      return reply.code(422).send({
        error: "ADAPTER_LOAD_FAILED",
        message,
      });
    }
  });

  fastify.get<{ Reply: ListDevicesResponse }>("/devices", async (_request, reply) => {
    const devices = globalDeviceRegistry.listAdapters();
    return reply.send({ devices });
  });
}
