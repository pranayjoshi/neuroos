import type { FastifyInstance, FastifyReply } from "fastify";
import type {
  StartSessionBody,
  ListSessionsResponse,
  ErrorResponse,
} from "../types.js";
import type { SessionMetadata } from "@neuroos/shared-contracts/schema";
import { globalSessionManager } from "../../session/session_manager.js";
import { globalPipelineOrchestrator } from "../../pipeline/pipeline_orchestrator.js";
import { createLogger } from "../../logger.js";

const logger = createLogger("SessionsRoute");

function jsonSafe<T>(obj: T): T {
  return JSON.parse(JSON.stringify(obj, (_k, v) =>
    typeof v === "bigint" ? v.toString() : v
  )) as T;
}

function sendSessionError(err: unknown, reply: FastifyReply): void {
  const message = err instanceof Error ? err.message : String(err);
  if (message.startsWith("SESSION_NOT_FOUND")) {
    void reply.code(404).send({ error: "SESSION_NOT_FOUND", message });
  } else {
    void reply.code(500).send({ error: "INTERNAL_ERROR", message });
  }
}

export async function sessionsRoutes(fastify: FastifyInstance): Promise<void> {
  fastify.post<{
    Body: StartSessionBody;
    Reply: SessionMetadata | ErrorResponse;
  }>("/sessions/start", async (request, reply) => {
    const { deviceId, subjectId, sessionName, paradigm } = request.body;

    try {
      const session = await globalSessionManager.startSession({
        deviceId,
        subjectId,
        sessionName,
        paradigm,
      });

      await globalPipelineOrchestrator.start(session);

      return reply.code(201).send(jsonSafe(session) as SessionMetadata);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : String(err);
      logger.error(`Failed to start session: ${message}`);

      if (message.startsWith("SESSION_ALREADY_ACTIVE")) {
        return reply.code(409).send({
          error: "SESSION_ALREADY_ACTIVE",
          message: "A session is already running. Stop it first.",
        } as ErrorResponse);
      }

      if (message.startsWith("DEVICE_NOT_FOUND")) {
        return reply.code(404).send({
          error: "DEVICE_NOT_FOUND",
          message,
        } as ErrorResponse);
      }

      return reply.code(500).send({ error: "INTERNAL_ERROR", message } as ErrorResponse);
    }
  });

  fastify.post<{
    Params: { id: string };
  }>("/sessions/:id/pause", async (request, reply) => {
    const { id } = request.params;

    try {
      await globalSessionManager.pauseSession(id);
      await globalPipelineOrchestrator.pause();
      return reply.send({ ok: true });
    } catch (err: unknown) {
      sendSessionError(err, reply);
    }
  });

  fastify.post<{
    Params: { id: string };
  }>("/sessions/:id/resume", async (request, reply) => {
    const { id } = request.params;

    try {
      await globalSessionManager.resumeSession(id);
      await globalPipelineOrchestrator.resume();
      return reply.send({ ok: true });
    } catch (err: unknown) {
      sendSessionError(err, reply);
    }
  });

  fastify.post<{
    Params: { id: string };
  }>("/sessions/:id/stop", async (request, reply) => {
    const { id } = request.params;

    try {
      await globalPipelineOrchestrator.stop();
      const session = await globalSessionManager.stopSession(id);
      return reply.send(jsonSafe(session));
    } catch (err: unknown) {
      sendSessionError(err, reply);
    }
  });

  fastify.get<{ Reply: ListSessionsResponse }>("/sessions", async (_request, reply) => {
    const sessions = globalSessionManager.listSessions().map(jsonSafe);
    return reply.send({ sessions });
  });
}
