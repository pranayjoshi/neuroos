import type { IntentEvent, IntentLabel, ServerMessage } from "./types.js";
import { parseIntentEvent, toWebSocketUrl } from "./http.js";
import { ConnectionError, NeuroOSError, StreamClosedError } from "./errors.js";
import { defaultWebSocketFactory, openWebSocket, type NeuroOSWebSocket, type WebSocketFactory } from "./ws.js";

type IntentStreamEventMap = {
  intent: IntentEvent;
  connected: void;
  disconnected: void;
  error: NeuroOSError;
};

type IntentStreamListener<K extends keyof IntentStreamEventMap> = (
  payload: IntentStreamEventMap[K],
) => void;

export interface IntentStreamOptions {
  baseUrl: string;
  reconnect?: boolean;
  reconnectDelayMs?: number;
  wsFactory?: WebSocketFactory;
}

interface QueueEntry {
  resolve: (value: IteratorResult<IntentEvent>) => void;
  reject: (err: Error) => void;
}

export class IntentStream implements AsyncIterable<IntentEvent> {
  private socket: NeuroOSWebSocket | null = null;
  private closed = false;
  private connected = false;
  private readonly listeners = new Map<
    keyof IntentStreamEventMap,
    Set<IntentStreamListener<keyof IntentStreamEventMap>>
  >();
  private readonly queue: IntentEvent[] = [];
  private readonly waiters: QueueEntry[] = [];
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private readonly wsFactory: WebSocketFactory;

  constructor(private readonly options: IntentStreamOptions) {
    this.wsFactory = options.wsFactory ?? defaultWebSocketFactory();
    void this.connect();
  }

  on<K extends keyof IntentStreamEventMap>(
    event: K,
    listener: IntentStreamListener<K>,
  ): this {
    let set = this.listeners.get(event);
    if (!set) {
      set = new Set();
      this.listeners.set(event, set);
    }
    set.add(listener as IntentStreamListener<keyof IntentStreamEventMap>);
    return this;
  }

  off<K extends keyof IntentStreamEventMap>(
    event: K,
    listener: IntentStreamListener<K>,
  ): this {
    this.listeners.get(event)?.delete(listener as IntentStreamListener<keyof IntentStreamEventMap>);
    return this;
  }

  sendFeedback(intentId: string, trueLabel: IntentLabel): void {
    this.send({ type: "feedback", intentId, trueLabel });
  }

  /** Alias for sendFeedback — matches simplified SDK naming. */
  feedback(intentId: string, trueLabel: IntentLabel): void {
    this.sendFeedback(intentId, trueLabel);
  }

  async close(): Promise<void> {
    this.closed = true;
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    this.rejectWaiters(new StreamClosedError());
    if (this.socket) {
      this.socket.close();
      this.socket = null;
    }
    if (this.connected) {
      this.connected = false;
      this.emit("disconnected", undefined);
    }
  }

  [Symbol.asyncIterator](): AsyncIterator<IntentEvent> {
    return {
      next: () => this.nextIntent(),
      return: async () => {
        await this.close();
        return { done: true, value: undefined };
      },
    };
  }

  private emit<K extends keyof IntentStreamEventMap>(
    event: K,
    payload: IntentStreamEventMap[K],
  ): void {
    const set = this.listeners.get(event);
    if (!set) return;
    for (const listener of set) {
      (listener as IntentStreamListener<K>)(payload);
    }
  }

  private send(message: { type: "feedback"; intentId: string; trueLabel: IntentLabel }): void {
    const OPEN = 1;
    if (!this.socket || this.socket.readyState !== OPEN) {
      this.emit("error", new StreamClosedError());
      return;
    }
    this.socket.send(JSON.stringify(message));
  }

  private async connect(): Promise<void> {
    if (this.closed) return;

    const url = toWebSocketUrl(this.options.baseUrl, "/stream/intents");

    try {
      const socket = await openWebSocket(this.wsFactory, url);
      this.socket = socket;
      this.bindSocket(socket);
    } catch (err) {
      const error =
        err instanceof NeuroOSError
          ? err
          : new ConnectionError(this.options.baseUrl, err);
      this.emit("error", error);
      this.scheduleReconnect();
    }
  }

  private bindSocket(socket: NeuroOSWebSocket): void {
    const onOpen = () => {
      this.connected = true;
      this.emit("connected", undefined);
    };

    const onMessage = (event: { data: unknown }) => {
      const text = typeof event.data === "string" ? event.data : String(event.data);
      this.handleMessage(text);
    };

    const onClose = () => {
      this.socket = null;
      if (this.connected) {
        this.connected = false;
        this.emit("disconnected", undefined);
      }
      if (!this.closed) {
        this.emit("error", new StreamClosedError());
        this.scheduleReconnect();
      }
    };

    const onError = () => {
      this.emit("error", new ConnectionError(this.options.baseUrl));
    };

    socket.addEventListener("open", onOpen);
    socket.addEventListener("message", onMessage);
    socket.addEventListener("close", onClose);
    socket.addEventListener("error", onError);
  }

  private handleMessage(text: string): void {
    let msg: ServerMessage;
    try {
      msg = JSON.parse(text) as ServerMessage;
    } catch {
      return;
    }

    switch (msg.type) {
      case "connected":
        return;
      case "intent":
        this.pushIntent(parseIntentEvent(msg.data));
        return;
      case "error":
        this.emit("error", new NeuroOSError("UNKNOWN", msg.message));
        return;
      default:
        return;
    }
  }

  private pushIntent(intent: IntentEvent): void {
    this.emit("intent", intent);
    const waiter = this.waiters.shift();
    if (waiter) {
      waiter.resolve({ done: false, value: intent });
      return;
    }
    this.queue.push(intent);
  }

  private nextIntent(): Promise<IteratorResult<IntentEvent>> {
    if (this.queue.length > 0) {
      const value = this.queue.shift();
      if (value) {
        return Promise.resolve({ done: false, value });
      }
    }

    if (this.closed) {
      return Promise.resolve({ done: true, value: undefined });
    }

    return new Promise<IteratorResult<IntentEvent>>((resolve, reject) => {
      this.waiters.push({ resolve, reject });
    });
  }

  private rejectWaiters(err: Error): void {
    while (this.waiters.length > 0) {
      const waiter = this.waiters.shift();
      waiter?.reject(err);
    }
  }

  private scheduleReconnect(): void {
    if (this.closed || this.options.reconnect === false) return;
    const delay = this.options.reconnectDelayMs ?? 1000;
    this.reconnectTimer = setTimeout(() => {
      this.reconnectTimer = null;
      void this.connect();
    }, delay);
  }
}
