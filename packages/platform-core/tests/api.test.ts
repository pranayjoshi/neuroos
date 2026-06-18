import { describe, it, expect, beforeAll, afterAll } from "vitest";
import { buildServer } from "../src/api/server.js";
import { globalDeviceRegistry } from "../src/registry/device_registry.js";
import { globalSessionManager } from "../src/session/session_manager.js";
import { globalPipelineOrchestrator } from "../src/pipeline/pipeline_orchestrator.js";
import type { FastifyInstance } from "fastify";

let fastify: FastifyInstance;

beforeAll(async () => {
  const built = await buildServer({ port: 0, host: "127.0.0.1", corsOrigins: [] });
  fastify = built.fastify;
  await fastify.ready();
});

afterAll(async () => {
  await globalPipelineOrchestrator.stop().catch(() => {});
  const session = globalSessionManager.getActiveSession();
  if (session) {
    await globalSessionManager.stopSession(session.sessionId).catch(() => {});
  }
  await fastify.close();
});

describe("GET /health", () => {
  it("returns 200 with status ok", async () => {
    const res = await fastify.inject({ method: "GET", url: "/health" });
    expect(res.statusCode).toBe(200);
    const body = res.json<{ status: string }>();
    expect(body.status).toBe("ok");
  });
});

describe("POST /devices/register", () => {
  it("registers the simulator adapter", async () => {
    const res = await fastify.inject({
      method: "POST",
      url: "/devices/register",
      payload: {
        adapterName: "neuroos-simulator",
        config: { numChannels: 4, sampleRateHz: 256, samplesPerFrame: 16 },
      },
    });
    expect(res.statusCode).toBe(200);
    const body = res.json<{ deviceId: string; state: string }>();
    expect(body.deviceId).toMatch(/^simulator:default:/);
    expect(body.state).toBe("disconnected");
  });
});

describe("GET /devices", () => {
  it("returns the list of devices", async () => {
    const res = await fastify.inject({ method: "GET", url: "/devices" });
    expect(res.statusCode).toBe(200);
    const body = res.json<{ devices: unknown[] }>();
    expect(Array.isArray(body.devices)).toBe(true);
  });
});

describe("POST /sessions/start", () => {
  it("returns 404 if device not found", async () => {
    const res = await fastify.inject({
      method: "POST",
      url: "/sessions/start",
      payload: {
        deviceId: "nonexistent:device:001",
        subjectId: "sub-001",
        sessionName: "test",
        paradigm: "motor_imagery",
      },
    });
    expect(res.statusCode).toBe(404);
  });
});

describe("POST /sessions/:id/pause", () => {
  it("returns 404 for unknown session", async () => {
    const res = await fastify.inject({
      method: "POST",
      url: "/sessions/nonexistent-id/pause",
    });
    expect(res.statusCode).toBe(404);
  });
});

describe("GET /sessions", () => {
  it("returns sessions array", async () => {
    const res = await fastify.inject({ method: "GET", url: "/sessions" });
    expect(res.statusCode).toBe(200);
    const body = res.json<{ sessions: unknown[] }>();
    expect(Array.isArray(body.sessions)).toBe(true);
  });
});

describe("GET /operator/diagnostics", () => {
  it("returns diagnostics object", async () => {
    const res = await fastify.inject({ method: "GET", url: "/operator/diagnostics" });
    expect(res.statusCode).toBe(200);
    const body = res.json<{ pipeline: unknown; session: unknown }>();
    expect(body).toHaveProperty("pipeline");
    expect(body).toHaveProperty("session");
  });
});

describe("GET /operator/signal", () => {
  it("returns frames array", async () => {
    const res = await fastify.inject({ method: "GET", url: "/operator/signal?seconds=5" });
    expect(res.statusCode).toBe(200);
    const body = res.json<{ frames: unknown[] }>();
    expect(Array.isArray(body.frames)).toBe(true);
  });
});
