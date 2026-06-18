import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { NeuroOS } from "../src/client.js";
import { SessionAlreadyActiveError } from "../src/errors.js";

describe("NeuroOS client", () => {
  const fetchMock = vi.fn();

  beforeEach(() => {
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    fetchMock.mockReset();
  });

  it("connect checks health endpoint", async () => {
    fetchMock.mockResolvedValueOnce({
      ok: true,
      text: async () => JSON.stringify({ status: "ok" }),
    });

    const client = new NeuroOS({ baseUrl: "http://localhost:3000" });
    await client.connect();
    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:3000/health",
      expect.objectContaining({ method: "GET" }),
    );
  });

  it("registers a device", async () => {
    fetchMock.mockResolvedValueOnce({
      ok: true,
      text: async () =>
        JSON.stringify({ deviceId: "simulator:default:SIM-001", state: "connected" }),
    });

    const client = new NeuroOS();
    const device = await client.devices.register("neuroos-simulator", { numChannels: 16 });
    expect(device.deviceId).toBe("simulator:default:SIM-001");
    expect(device.numChannels).toBe(16);
  });

  it("maps session already active errors", async () => {
    fetchMock.mockResolvedValueOnce({
      ok: false,
      status: 409,
      text: async () =>
        JSON.stringify({
          error: "SESSION_ALREADY_ACTIVE",
          message: "A session is already running. Stop it first.",
        }),
    });

    const client = new NeuroOS();
    await expect(
      client.sessions.start({
        deviceId: "simulator:default:SIM-001",
        subjectId: "sub-001",
        sessionName: "test",
        paradigm: "motor_imagery",
      }),
    ).rejects.toBeInstanceOf(SessionAlreadyActiveError);
  });
});
