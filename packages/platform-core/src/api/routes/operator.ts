import type { FastifyInstance } from "fastify";
import type {
  DiagnosticsResponse,
  SignalResponse,
  FeaturesResponse,
} from "../types.js";
import { globalDeviceRegistry } from "../../registry/device_registry.js";
import { globalSessionManager } from "../../session/session_manager.js";
import { globalPipelineOrchestrator } from "../../pipeline/pipeline_orchestrator.js";

function jsonSafe<T>(obj: T): T {
  return JSON.parse(JSON.stringify(obj, (_k, v) =>
    typeof v === "bigint" ? v.toString() : v
  )) as T;
}

export async function operatorRoutes(fastify: FastifyInstance): Promise<void> {
  fastify.get<{ Reply: DiagnosticsResponse }>("/operator/diagnostics", async (_req, reply) => {
    const session = globalSessionManager.getActiveSession();
    const adapters = globalDeviceRegistry.listAdapters();
    const firstAdapter = adapters[0];

    let deviceDiagnostics: unknown = null;
    if (firstAdapter) {
      const adapter = globalDeviceRegistry.getAdapter(firstAdapter.deviceId);
      if (adapter) {
        try {
          deviceDiagnostics = await adapter.getDiagnostics();
        } catch {
          deviceDiagnostics = null;
        }
      }
    }

    const latency = globalPipelineOrchestrator.getLatencyStats();

    const response: DiagnosticsResponse = {
      device: {
        deviceId: firstAdapter?.deviceId ?? null,
        adapterName: firstAdapter?.adapterName ?? null,
        state: firstAdapter?.state ?? null,
        diagnostics: deviceDiagnostics,
      },
      pipeline: {
        meanLatencyMs: latency.mean,
        p95LatencyMs: latency.p95,
        p99LatencyMs: latency.p99,
        maxLatencyMs: latency.max,
        jitterMs: latency.jitter,
        droppedFrames: session?.droppedFrames ?? 0,
        currentScenario: session?.pipelineConfig.paradigm.type ?? null,
      },
      session: session ? jsonSafe(session) : null,
    };

    return reply.send(response);
  });

  fastify.get<{
    Querystring: { channels?: string; seconds?: string };
    Reply: SignalResponse;
  }>("/operator/signal", async (request, reply) => {
    const seconds = Number(request.query.seconds ?? 5);
    const frames = globalPipelineOrchestrator
      .getRecentSignalFrames(seconds)
      .map((f) => jsonSafe(f));

    return reply.send({ frames });
  });

  fastify.get<{
    Querystring: { seconds?: string };
    Reply: FeaturesResponse;
  }>("/operator/features", async (request, reply) => {
    const seconds = Number(request.query.seconds ?? 5);
    const vectors = globalPipelineOrchestrator
      .getRecentFeatureVectors(seconds)
      .map((v) => jsonSafe(v));

    return reply.send({ vectors });
  });
}
