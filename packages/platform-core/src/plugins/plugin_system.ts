import { resolve, isAbsolute } from "node:path";
import type { DeviceAdapter, DeviceAdapterConfig } from "@neuroos/shared-contracts/schema";
import { globalDeviceRegistry } from "../registry/device_registry.js";
import { createLogger } from "../logger.js";

const logger = createLogger("PluginSystem");

interface PluginModule {
  default: new (config: DeviceAdapterConfig) => DeviceAdapter;
}

export class PluginSystem {
  private loadedPlugins = new Map<string, PluginModule>();

  async loadPlugin(pluginPath: string, config: DeviceAdapterConfig): Promise<DeviceAdapter> {
    const resolvedPath = isAbsolute(pluginPath)
      ? pluginPath
      : resolve(process.cwd(), pluginPath);

    logger.info(`Loading plugin from: ${resolvedPath}`);

    let pluginModule: PluginModule;

    if (this.loadedPlugins.has(resolvedPath)) {
      pluginModule = this.loadedPlugins.get(resolvedPath)!;
    } else {
      const imported = (await import(resolvedPath)) as unknown;
      if (
        typeof imported !== "object" ||
        imported === null ||
        !("default" in imported) ||
        typeof (imported as { default: unknown }).default !== "function"
      ) {
        throw new Error(
          `Plugin at "${resolvedPath}" must export a default class implementing DeviceAdapter.`
        );
      }
      pluginModule = imported as PluginModule;
      this.loadedPlugins.set(resolvedPath, pluginModule);
    }

    const AdapterClass = pluginModule.default;
    const adapter = new AdapterClass(config);

    logger.info(`Plugin loaded successfully: ${adapter.adapterName} (${adapter.deviceId})`);
    return adapter;
  }

  async loadAndRegisterPlugin(
    pluginPath: string,
    config: DeviceAdapterConfig
  ): Promise<DeviceAdapter> {
    const adapter = await this.loadPlugin(pluginPath, config);
    globalDeviceRegistry.register(adapter);
    return adapter;
  }

  isLoaded(pluginPath: string): boolean {
    const resolvedPath = isAbsolute(pluginPath)
      ? pluginPath
      : resolve(process.cwd(), pluginPath);
    return this.loadedPlugins.has(resolvedPath);
  }
}

export const globalPluginSystem = new PluginSystem();
