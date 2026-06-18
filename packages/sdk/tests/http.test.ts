import { describe, expect, it } from "vitest";
import { parseIntentEvent } from "../src/http.js";

describe("parseIntentEvent", () => {
  it("revives bigint timestamps", () => {
    const event = parseIntentEvent({
      intentId: "abc",
      label: "motor_imagery_left",
      confidence: 0.9,
      posteriors: { motor_imagery_left: 0.9 },
      classifierType: "lda",
      sourceVectorId: "vec-1",
      timestampNs: "1700000000000000000",
      endToEndLatencyMs: 12.5,
      featureImportance: {},
      artifactFlag: false,
      feedbackLabel: null,
    });

    expect(event.timestampNs).toBe(1700000000000000000n);
    expect(event.label).toBe("motor_imagery_left");
  });
});
