import { createContext, useContext, type ReactNode } from "react";
import { NeuroOS } from "./client.js";
import type { NeuroOSClientConfig } from "./types.js";

export const NeuroOSContext = createContext<NeuroOS | null>(null);

export interface NeuroOSProviderProps {
  config?: NeuroOSClientConfig;
  client?: NeuroOS;
  children: ReactNode;
}

export function NeuroOSProvider({ config, client, children }: NeuroOSProviderProps): ReactNode {
  const value = client ?? new NeuroOS(config);
  return <NeuroOSContext.Provider value={value}>{children}</NeuroOSContext.Provider>;
}

export function useNeuroOSClient(): NeuroOS {
  const client = useContext(NeuroOSContext);
  if (!client) {
    throw new Error("useNeuroOSClient must be used within a NeuroOSProvider");
  }
  return client;
}
