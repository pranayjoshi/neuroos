"""Shared pytest fixtures."""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SCHEMA_PATH = REPO_ROOT / "jobs/00_shared_contracts/json-schema/RawSignalFrame.schema.json"


@pytest.fixture(scope="session")
def raw_signal_frame_schema() -> dict:
    with SCHEMA_PATH.open(encoding="utf-8") as handle:
        return json.load(handle)


@pytest.fixture(scope="session")
def schema_validator(raw_signal_frame_schema: dict):
    return jsonschema.Draft7Validator(raw_signal_frame_schema)
