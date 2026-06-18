import Fastify from "fastify";
import fastifyWebSocket from "@fastify/websocket";
import fastifyCors from "@fastify/cors";
import { devicesRoutes } from "./routes/devices.js";
import { sessionsRoutes } from "./routes/sessions.js";
import { streamRoutes } from "./routes/stream.js";
import { operatorRoutes } from "./routes/operator.js";
import { globalConfigStore } from "../config/config_store.js";
import { createLogger } from "../logger.js";

const logger = createLogger("Server");

export interface ServerOptions {
  port?: number;
  host?: string;
  corsOrigins?: string[];
}

export async function buildServer(opts: ServerOptions = {}) {
  let port = opts.port;
  let host = opts.host;
  let corsOrigins = opts.corsOrigins;

  try {
    port = port ?? globalConfigStore.get<number>("api.port");
    host = host ?? globalConfigStore.get<string>("api.host");
    corsOrigins = corsOrigins ?? globalConfigStore.get<string[]>("api.corsOrigins");
  } catch {
    port = port ?? 3000;
    host = host ?? "127.0.0.1";
    corsOrigins = corsOrigins ?? ["http://localhost:3000"];
  }

  const fastify = Fastify({
    logger: false,
    disableRequestLogging: true,
  });

  await fastify.register(fastifyCors, {
    origin: corsOrigins,
    methods: ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
  });

  await fastify.register(fastifyWebSocket);

  fastify.addHook("onRequest", async (request) => {
    logger.info(`${request.method} ${request.url}`);
  });

  fastify.setErrorHandler((error, _request, reply) => {
    logger.error(`Unhandled error: ${error.message}`);
    void reply.code(error.statusCode ?? 500).send({
      error: "INTERNAL_ERROR",
      message: error.message,
    });
  });

  await fastify.register(devicesRoutes);
  await fastify.register(sessionsRoutes);
  await fastify.register(streamRoutes);
  await fastify.register(operatorRoutes);

  fastify.get("/health", async () => ({ status: "ok", version: "0.1.0" }));

  return { fastify, port, host };
}

export async function startServer(opts: ServerOptions = {}): Promise<void> {
  const { fastify, port, host } = await buildServer(opts);

  try {
    await fastify.listen({ port: port!, host: host! });
    logger.info(`NeuroOS Platform Core listening on http://${host}:${port}`);
  } catch (err) {
    logger.error(`Failed to start server: ${String(err)}`);
    process.exit(1);
  }
}
