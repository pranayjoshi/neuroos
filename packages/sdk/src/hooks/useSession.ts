import { useCallback, useState } from "react";
import type { SessionMetadata } from "../types.js";
import type { SessionStartParams } from "../types.js";
import type { NeuroOSError } from "../errors.js";
import { useNeuroOSClient } from "../context.js";

export interface UseSessionResult {
  session: SessionMetadata | null;
  isActive: boolean;
  startSession: (params: SessionStartParams) => Promise<void>;
  stopSession: () => Promise<void>;
  error: NeuroOSError | null;
}

export function useSession(): UseSessionResult {
  const client = useNeuroOSClient();
  const [session, setSession] = useState<SessionMetadata | null>(null);
  const [error, setError] = useState<NeuroOSError | null>(null);

  const startSession = useCallback(
    async (params: SessionStartParams) => {
      try {
        setError(null);
        const started = await client.sessions.start(params);
        setSession(started);
      } catch (err) {
        setError(err as NeuroOSError);
        throw err;
      }
    },
    [client],
  );

  const stopSession = useCallback(async () => {
    if (!session) return;
    try {
      setError(null);
      const stopped = await client.sessions.stop(session.sessionId);
      setSession(stopped);
    } catch (err) {
      setError(err as NeuroOSError);
      throw err;
    }
  }, [client, session]);

  return {
    session,
    isActive: session?.state === "active" || session?.state === "paused",
    startSession,
    stopSession,
    error,
  };
}
