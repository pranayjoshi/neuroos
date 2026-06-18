import type { FastifyInstance } from "fastify";
import type { SocketStream } from "@fastify/websocket";
import type { IntentEvent } from "@neuroos/shared-contracts/schema";
import type { ServerMessage, ClientMessage } from "../types.js";
import { globalEventBus } from "../../bus/event_bus.js";
import { globalSessionManager } from "../../session/session_manager.js";
import { createLogger } from "../../logger.js";

const logger = createLogger("StreamRoute");

const NEUROOS_VERSION = "0.1.0";

function serialize(msg: ServerMessage): string {
  return JSON.stringify(msg, (_k, v) =>
    typeof v === "bigint" ? v.toString() : v
  );
}

export async function streamRoutes(fastify: FastifyInstance): Promise<void> {
  fastify.get("/stream/intents", { websocket: true }, (connection: SocketStream) => {
    const socket = connection.socket;
    const session = globalSessionManager.getActiveSession();

    const connected: ServerMessage = {
      type: "connected",
      sessionId: session?.sessionId ?? null,
      deviceId: session?.deviceInfo.deviceId ?? null,
      version: NEUROOS_VERSION,
    };
    socket.send(serialize(connected));

    const onIntent = (intent: IntentEvent) => {
      if (socket.readyState !== socket.OPEN) return;
      const msg: ServerMessage = { type: "intent", data: intent };
      socket.send(serialize(msg));
    };

    const onSessionStopped = (data: { sessionId: string; totalFrames: number }) => {
      if (socket.readyState !== socket.OPEN) return;
      const msg: ServerMessage = {
        type: "session_stopped",
        sessionId: data.sessionId,
        totalFrames: data.totalFrames,
      };
      socket.send(serialize(msg));
    };

    const onPipelineError = (data: { message: string; code: string }) => {
      if (socket.readyState !== socket.OPEN) return;
      const msg: ServerMessage = {
        type: "error",
        code: data.code,
        message: data.message,
      };
      socket.send(serialize(msg));
    };

    globalEventBus.on("intent.event", onIntent);
    globalEventBus.on("session.stopped", onSessionStopped);
    globalEventBus.on("pipeline.error", onPipelineError);

    socket.on("message", (raw: Buffer | string) => {
      try {
        const text = typeof raw === "string" ? raw : raw.toString("utf-8");
        const msg = JSON.parse(text) as ClientMessage;

        if (msg.type === "ping") {
          socket.send(serialize({ type: "feedback_ack", intentId: "pong" }));
          return;
        }

        if (msg.type === "feedback") {
          const { intentId } = msg;
          logger.info(`Received feedback for intent ${intentId}: ${msg.trueLabel}`);
          const ack: ServerMessage = { type: "feedback_ack", intentId };
          socket.send(serialize(ack));
          return;
        }
      } catch (err) {
        logger.warn(`Malformed WebSocket message: ${String(err)}`);
        const errMsg: ServerMessage = {
          type: "error",
          code: "INVALID_MESSAGE",
          message: "Could not parse message as JSON.",
        };
        socket.send(serialize(errMsg));
      }
    });

    socket.on("close", () => {
      globalEventBus.off("intent.event", onIntent);
      globalEventBus.off("session.stopped", onSessionStopped);
      globalEventBus.off("pipeline.error", onPipelineError);
      logger.info("WebSocket client disconnected");
    });

    socket.on("error", (err: Error) => {
      logger.warn(`WebSocket error: ${err.message}`);
      globalEventBus.off("intent.event", onIntent);
      globalEventBus.off("session.stopped", onSessionStopped);
      globalEventBus.off("pipeline.error", onPipelineError);
    });

    logger.info("WebSocket client connected");
  });
}
