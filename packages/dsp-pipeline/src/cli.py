"""CLI entry point for JSONL stdin/stdout processing."""

from __future__ import annotations

import json
import sys

from config import DSPConfig
from pipeline import Pipeline


def run_pipeline(config: DSPConfig | None = None) -> None:
    pipeline = Pipeline(config or DSPConfig.default())
    pending_calibration: list[dict] = []

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        frame = json.loads(line)
        if frame.get("calibration"):
            pending_calibration.append(frame)
            if len(pending_calibration) >= int(frame.get("calibrationBatchSize", 1)):
                pipeline.calibrate(pending_calibration)
                pending_calibration.clear()
            continue

        if pending_calibration:
            pipeline.calibrate(pending_calibration)
            pending_calibration.clear()

        feature_vector = pipeline.process(frame)
        sys.stdout.write(json.dumps(feature_vector) + "\n")
        sys.stdout.flush()


def main() -> None:
    run_pipeline()
