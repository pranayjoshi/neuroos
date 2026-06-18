import { spawn, type ChildProcess } from "node:child_process";
import { createInterface } from "node:readline";
import type {
  SessionMetadata,
  RawSignalFrame,
  FeatureVector,
  IntentEvent,
} from "@neuroos/shared-contracts/schema";
import { globalEventBus } from "../bus/event_bus.js";
import { globalDeviceRegistry, DeviceRegistry } from "../registry/device_registry.js";
import { createLogger } from "../logger.js";

const logger = createLogger("PipelineOrchestrator");

const LATENCY_WARNING_MS = 15;
const LATENCY_CRITICAL_MS = 20;
const LATENCY_WINDOW = 100;

interface LatencyStats {
  mean: number;
  p50: number;
  p95: number;
  p99: number;
  max: number;
  jitter: number;
}

class JSONLWriter {
  private queue: string[] = [];
  private writing = false;
  private process: ChildProcess;

  constructor(proc: ChildProcess) {
    this.process = proc;
  }

  write(obj: object): void {
    this.queue.push(JSON.stringify(obj) + "\n");
    if (!this.writing) {
      void this.flush();
    }
  }

  private async flush(): Promise<void> {
    this.writing = true;
    while (this.queue.length > 0) {
      const line = this.queue.shift()!;
      if (!this.process.stdin) break;
      const ok = this.process.stdin.write(line);
      if (!ok) {
        await new Promise<void>((r) => this.process.stdin!.once("drain", r));
      }
    }
    this.writing = false;
  }
}

export class PipelineOrchestrator {
  private dspProcess: ChildProcess | null = null;
  private intentProcess: ChildProcess | null = null;
  private dspWriter: JSONLWriter | null = null;
  private intentWriter: JSONLWriter | null = null;
  private frameUnsubscribe: (() => void) | null = null;
  private latencyHistory: number[] = [];
  private session: SessionMetadata | null = null;
  private paused = false;
  private registry: DeviceRegistry;

  private recentSignalFrames: RawSignalFrame[] = [];
  private recentFeatureVectors: FeatureVector[] = [];
  private readonly SIGNAL_WINDOW_SECONDS = 5;

  constructor(registry?: DeviceRegistry) {
    this.registry = registry ?? globalDeviceRegistry;
  }

  getRecentSignalFrames(seconds = 5): RawSignalFrame[] {
    const cutoff = Date.now() - seconds * 1000;
    return this.recentSignalFrames.filter(
      (f) => Number(f.timestampNs) / 1_000_000 >= cutoff
    );
  }

  getRecentFeatureVectors(seconds = 5): FeatureVector[] {
    const cutoff = Date.now() - seconds * 1000;
    return this.recentFeatureVectors.filter(
      (v) => Number(v.timestampNs) / 1_000_000 >= cutoff
    );
  }

  async start(session: SessionMetadata): Promise<void> {
    this.session = session;
    this.paused = false;
    this.latencyHistory = [];

    const dspBin = process.env["NEUROOS_DSP_BIN"] ?? "python3";
    const dspScript = process.env["NEUROOS_DSP_SCRIPT"] ?? "-c";
    const dspArgs =
      dspBin === "python3" && dspScript === "-c"
        ? [
            "-c",
            `
import sys, json, time, uuid
for line in sys.stdin:
    line = line.strip()
    if not line:
        continue
    try:
        frame = json.loads(line)
        vector = {
            "vectorId": str(uuid.uuid4()),
            "sourceFrameIndices": [frame.get("frameIndex", 0)],
            "timestampNs": frame.get("timestampNs", str(int(time.time_ns()))),
            "deviceId": frame.get("deviceId", ""),
            "signalType": frame.get("signalType", "EEG"),
            "bandPowers": {"delta":[],"theta":[],"alpha":[],"beta":[],"gamma":[],"high_gamma":[]},
            "spatialFeatures": [],
            "erd": {},
            "evokedResponse": None,
            "artifactFlag": False,
            "processingLatencyMs": 0.5,
            "channelLabels": frame.get("channelLabels", [])
        }
        print(json.dumps(vector), flush=True)
    except Exception as e:
        pass
`,
          ]
        : [dspScript];

    const intentBin = process.env["NEUROOS_INTENT_BIN"] ?? "python3";
    const intentScript = process.env["NEUROOS_INTENT_SCRIPT"] ?? "-c";
    const intentArgs =
      intentBin === "python3" && intentScript === "-c"
        ? [
            "-c",
            `
import sys, json, time, uuid
for line in sys.stdin:
    line = line.strip()
    if not line:
        continue
    try:
        vector = json.loads(line)
        intent = {
            "intentId": str(uuid.uuid4()),
            "label": "motor_imagery_rest",
            "confidence": 0.75,
            "posteriors": {"motor_imagery_rest": 0.75, "motor_imagery_left": 0.15, "motor_imagery_right": 0.10},
            "classifierType": "lda",
            "sourceVectorId": vector.get("vectorId", ""),
            "timestampNs": str(int(time.time_ns())),
            "endToEndLatencyMs": 5.0,
            "featureImportance": {},
            "artifactFlag": False,
            "feedbackLabel": None
        }
        print(json.dumps(intent), flush=True)
    except Exception as e:
        pass
`,
          ]
        : [intentScript];

    this.dspProcess = spawn(dspBin, dspArgs, {
      stdio: ["pipe", "pipe", "pipe"],
    });

    this.intentProcess = spawn(intentBin, intentArgs, {
      stdio: ["pipe", "pipe", "pipe"],
    });

    if (!this.dspProcess.stdin || !this.dspProcess.stdout) {
      throw new Error("Failed to open DSP process pipes");
    }

    if (!this.intentProcess.stdin || !this.intentProcess.stdout) {
      throw new Error("Failed to open Intent Engine process pipes");
    }

    this.dspWriter = new JSONLWriter(this.dspProcess);
    this.intentWriter = new JSONLWriter(this.intentProcess);

    const dspRl = createInterface({ input: this.dspProcess.stdout });
    dspRl.on("line", (line) => {
      if (!line.trim()) return;
      try {
        const vector = JSON.parse(line) as FeatureVector;
        vector.timestampNs = BigInt(vector.timestampNs as unknown as string);
        globalEventBus.emit("dsp.features", vector);
        this.recentFeatureVectors.push(vector);
        if (this.recentFeatureVectors.length > 1000) {
          this.recentFeatureVectors.shift();
        }
        this.intentWriter?.write(JSON.parse(JSON.stringify(vector, (_k, v) =>
          typeof v === "bigint" ? v.toString() : v
        )));
      } catch {
        // ignore malformed lines
      }
    });

    const intentRl = createInterface({ input: this.intentProcess.stdout });
    intentRl.on("line", (line) => {
      if (!line.trim()) return;
      try {
        const intent = JSON.parse(line) as IntentEvent;
        intent.timestampNs = BigInt(intent.timestampNs as unknown as string);

        const latencyMs = intent.endToEndLatencyMs ?? 0;
        this.recordLatency(latencyMs);

        if (latencyMs > LATENCY_WARNING_MS) {
          logger.warn(`High latency: ${latencyMs.toFixed(2)}ms`);
        }
        if (latencyMs > LATENCY_CRITICAL_MS) {
          globalEventBus.emit("pipeline.latency_warning", { latencyMs });
        }

        globalEventBus.emit("intent.event", intent);
      } catch {
        // ignore malformed lines
      }
    });

    this.dspProcess.stderr?.on("data", (chunk: Buffer) => {
      logger.warn(`DSP stderr: ${chunk.toString().trim()}`);
    });

    this.intentProcess.stderr?.on("data", (chunk: Buffer) => {
      logger.warn(`Intent stderr: ${chunk.toString().trim()}`);
    });

    this.dspProcess.on("exit", (code) => {
      if (code !== 0 && code !== null) {
        logger.error(`DSP process exited with code ${code}`);
        globalEventBus.emit("pipeline.error", {
          message: `DSP process exited with code ${code}`,
          code: "DSP_EXIT",
        });
      }
    });

    this.intentProcess.on("exit", (code) => {
      if (code !== 0 && code !== null) {
        logger.error(`Intent process exited with code ${code}`);
        globalEventBus.emit("pipeline.error", {
          message: `Intent process exited with code ${code}`,
          code: "INTENT_EXIT",
        });
      }
    });

    this.frameUnsubscribe = this.registry.onFrame(
      session.deviceInfo.deviceId,
      (frame) => {
        if (this.paused) return;

        this.recentSignalFrames.push(frame);
        const cutoffMs = Date.now() - this.SIGNAL_WINDOW_SECONDS * 1000;
        while (
          this.recentSignalFrames.length > 0 &&
          Number(this.recentSignalFrames[0]!.timestampNs) / 1_000_000 < cutoffMs
        ) {
          this.recentSignalFrames.shift();
        }

        const serializable = JSON.parse(
          JSON.stringify(frame, (_k, v) =>
            typeof v === "bigint" ? v.toString() : v
          )
        ) as object;

        this.dspWriter?.write(serializable);
      }
    );

    logger.info(`Pipeline started for session: ${session.sessionId}`);
  }

  async stop(): Promise<void> {
    if (this.frameUnsubscribe) {
      this.frameUnsubscribe();
      this.frameUnsubscribe = null;
    }

    if (this.dspProcess) {
      this.dspProcess.stdin?.end();
      this.dspProcess.kill("SIGTERM");
      this.dspProcess = null;
    }

    if (this.intentProcess) {
      this.intentProcess.stdin?.end();
      this.intentProcess.kill("SIGTERM");
      this.intentProcess = null;
    }

    this.dspWriter = null;
    this.intentWriter = null;
    this.session = null;

    logger.info("Pipeline stopped");
  }

  async pause(): Promise<void> {
    this.paused = true;
    logger.info("Pipeline paused");
  }

  async resume(): Promise<void> {
    this.paused = false;
    logger.info("Pipeline resumed");
  }

  getLatencyStats(): LatencyStats {
    if (this.latencyHistory.length === 0) {
      return { mean: 0, p50: 0, p95: 0, p99: 0, max: 0, jitter: 0 };
    }

    const sorted = [...this.latencyHistory].sort((a, b) => a - b);
    const n = sorted.length;
    const mean = sorted.reduce((s, v) => s + v, 0) / n;
    const variance = sorted.reduce((s, v) => s + (v - mean) ** 2, 0) / n;
    const jitter = Math.sqrt(variance);

    const p50 = sorted[Math.floor(n * 0.5)] ?? 0;
    const p95 = sorted[Math.floor(n * 0.95)] ?? 0;
    const p99 = sorted[Math.floor(n * 0.99)] ?? 0;
    const max = sorted[n - 1] ?? 0;

    return { mean, p50, p95, p99, max, jitter };
  }

  private recordLatency(latencyMs: number): void {
    this.latencyHistory.push(latencyMs);
    if (this.latencyHistory.length > LATENCY_WINDOW) {
      this.latencyHistory.shift();
    }
  }
}

export const globalPipelineOrchestrator = new PipelineOrchestrator();
