import { describe, it, expect, beforeEach } from "vitest";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { SessionManager } from "../src/session/session_manager.js";
import { DeviceRegistry } from "../src/registry/device_registry.js";
import { SimulatorAdapter } from "../src/adapters/simulator_adapter.js";

const defaultConfig = {
  sampleRateHz: 256,
  numChannels: 4,
  channelLabels: null,
  samplesPerFrame: 16,
  hardwareFilter: false,
  driverOptions: {},
};

describe("SessionManager", () => {
  let registry: DeviceRegistry;
  let adapter: SimulatorAdapter;
  let sessionManager: SessionManager;
  const tempDir = join(tmpdir(), `neuroos-test-${Date.now()}`);

  beforeEach(() => {
    registry = new DeviceRegistry();
    adapter = new SimulatorAdapter(defaultConfig);
    registry.register(adapter);

    sessionManager = new SessionManager(tempDir, registry);
  });

  it("starts a session and returns SessionMetadata", async () => {
    const session = await sessionManager.startSession({
      deviceId: adapter.deviceId,
      subjectId: "sub-001",
      sessionName: "test-session",
      paradigm: "motor_imagery",
    });

    expect(session.sessionId).toBeTruthy();
    expect(session.state).toBe("active");
    expect(session.subjectId).toBe("sub-001");
    expect(session.sessionName).toBe("test-session");
    expect(session.endedAtMs).toBeNull();

    await adapter.stopRecording();
    await adapter.disconnect();
  });

  it("throws 409-style error if session already active", async () => {
    const s1 = await sessionManager.startSession({
      deviceId: adapter.deviceId,
      subjectId: "sub-001",
      sessionName: "first",
      paradigm: "motor_imagery",
    });

    await expect(
      sessionManager.startSession({
        deviceId: adapter.deviceId,
        subjectId: "sub-002",
        sessionName: "second",
        paradigm: "motor_imagery",
      })
    ).rejects.toThrow(/SESSION_ALREADY_ACTIVE/);

    await sessionManager.stopSession(s1.sessionId);
  });

  it("pauses and resumes a session", async () => {
    const session = await sessionManager.startSession({
      deviceId: adapter.deviceId,
      subjectId: "sub-001",
      sessionName: "pause-test",
      paradigm: "motor_imagery",
    });

    await sessionManager.pauseSession(session.sessionId);
    expect(sessionManager.getSession(session.sessionId)?.state).toBe("paused");

    await sessionManager.resumeSession(session.sessionId);
    expect(sessionManager.getSession(session.sessionId)?.state).toBe("active");

    await sessionManager.stopSession(session.sessionId);
  });

  it("stops a session and sets endedAtMs", async () => {
    const session = await sessionManager.startSession({
      deviceId: adapter.deviceId,
      subjectId: "sub-001",
      sessionName: "stop-test",
      paradigm: "motor_imagery",
    });

    const stopped = await sessionManager.stopSession(session.sessionId);
    expect(stopped.state).toBe("completed");
    expect(stopped.endedAtMs).not.toBeNull();
    expect(sessionManager.getActiveSession()).toBeNull();
  });

  it("getActiveSession returns null when no session running", () => {
    expect(sessionManager.getActiveSession()).toBeNull();
  });

  it("listSessions returns all sessions", async () => {
    const s1 = await sessionManager.startSession({
      deviceId: adapter.deviceId,
      subjectId: "sub-001",
      sessionName: "s1",
      paradigm: "motor_imagery",
    });
    await sessionManager.stopSession(s1.sessionId);

    const list = sessionManager.listSessions();
    expect(list.length).toBeGreaterThanOrEqual(1);
  });

  it("throws SESSION_NOT_FOUND for unknown sessionId", async () => {
    await expect(sessionManager.pauseSession("nonexistent")).rejects.toThrow(
      /SESSION_NOT_FOUND/
    );
  });
});
