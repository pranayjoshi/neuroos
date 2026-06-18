export interface NeuroOSWebSocket {
  readonly readyState: number;
  readonly OPEN: number;
  send(data: string): void;
  close(code?: number, reason?: string): void;
  addEventListener(type: "open", listener: () => void): void;
  addEventListener(type: "message", listener: (event: { data: unknown }) => void): void;
  addEventListener(type: "close", listener: () => void): void;
  addEventListener(type: "error", listener: () => void): void;
  removeEventListener(type: "open", listener: () => void): void;
  removeEventListener(type: "message", listener: (event: { data: unknown }) => void): void;
  removeEventListener(type: "close", listener: () => void): void;
  removeEventListener(type: "error", listener: () => void): void;
}

export type WebSocketFactory = (url: string) => NeuroOSWebSocket | Promise<NeuroOSWebSocket>;

export function defaultWebSocketFactory(): WebSocketFactory {
  if (typeof globalThis.WebSocket !== "undefined") {
    return (url: string) => new globalThis.WebSocket(url) as unknown as NeuroOSWebSocket;
  }

  return async (url: string) => {
    const { default: WS } = await import("ws");
    const socket = new WS(url);
    return socket as unknown as NeuroOSWebSocket;
  };
}

export async function openWebSocket(
  factory: WebSocketFactory,
  url: string,
): Promise<NeuroOSWebSocket> {
  const result = factory(url);
  return result instanceof Promise ? result : Promise.resolve(result);
}
