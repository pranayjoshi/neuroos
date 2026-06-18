import { useEffect, useRef, useState } from "react";
import type { IntentEvent, IntentLabel } from "../types.js";
import type { NeuroOSError } from "../errors.js";
import { useNeuroOSClient } from "../context.js";
import type { IntentStream } from "../stream.js";

export interface UseIntentOptions {
  filter?: IntentLabel[];
  minConfidence?: number;
}

export interface UseIntentResult {
  intent: IntentEvent | null;
  history: IntentEvent[];
  isConnected: boolean;
  error: NeuroOSError | null;
}

export function useIntent(options?: UseIntentOptions): UseIntentResult {
  const client = useNeuroOSClient();
  const [intent, setIntent] = useState<IntentEvent | null>(null);
  const [history, setHistory] = useState<IntentEvent[]>([]);
  const [isConnected, setIsConnected] = useState(false);
  const [error, setError] = useState<NeuroOSError | null>(null);
  const streamRef = useRef<IntentStream | null>(null);
  const optionsRef = useRef(options);
  optionsRef.current = options;

  useEffect(() => {
    const stream = client.intents.stream();
    streamRef.current = stream;

    stream.on("connected", () => setIsConnected(true));
    stream.on("disconnected", () => setIsConnected(false));
    stream.on("error", (err) => setError(err));
    stream.on("intent", (event) => {
      const opts = optionsRef.current;
      if (opts?.filter && !opts.filter.includes(event.label)) return;
      const minConfidence = opts?.minConfidence ?? 0.6;
      if (event.confidence < minConfidence) return;
      setIntent(event);
      setHistory((prev) => [event, ...prev].slice(0, 10));
    });

    return () => {
      void stream.close();
      streamRef.current = null;
    };
  }, [client]);

  return { intent, history, isConnected, error };
}

/** Alias for useIntent — matches simplified hook naming. */
export const useIntentStream = useIntent;
