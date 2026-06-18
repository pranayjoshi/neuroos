import { useEffect, useState } from "react";
import type { DeviceDiagnostics, DeviceInfo, DeviceState } from "../types.js";
import { useNeuroOSClient } from "../context.js";

export interface UseDeviceResult {
  device: DeviceInfo | null;
  state: DeviceState;
  diagnostics: DeviceDiagnostics | null;
}

export function useDevice(deviceId?: string): UseDeviceResult {
  const client = useNeuroOSClient();
  const [device, setDevice] = useState<DeviceInfo | null>(null);
  const [state, setState] = useState<DeviceState>("disconnected");
  const [diagnostics, setDiagnostics] = useState<DeviceDiagnostics | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      const devices = await client.devices.list();
      const match = deviceId
        ? devices.find((item) => item.deviceId === deviceId)
        : devices[0];

      if (cancelled || !match) return;

      setState(match.state);
      setDevice({
        deviceId: match.deviceId,
        vendor: "NeuroOS",
        model: match.adapterName,
        firmwareVersion: "0.1.0",
        numChannels: 16,
        sampleRateHz: 256,
        signalType: "EEG",
        channelLabels: [],
        adResolutionBits: 24,
        referenceElectrode: "average",
      });

      try {
        const diag = await client.devices.getDiagnostics(match.deviceId);
        if (!cancelled) setDiagnostics(diag);
      } catch {
        if (!cancelled) setDiagnostics(null);
      }
    }

    void load();
    const interval = setInterval(() => {
      void load();
    }, 5000);

    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, [client, deviceId]);

  return { device, state, diagnostics };
}

/** Alias for useDevice — plural naming used in some examples. */
export const useDevices = useDevice;
