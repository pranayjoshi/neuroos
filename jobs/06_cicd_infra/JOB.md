# Job 06 — CI/CD & Infrastructure

**Agent Role:** CI/CD Manager  
**Language:** TypeScript (Turborepo), Shell, Docker, GitHub Actions YAML  
**Depends on:** All other jobs must be complete (Jobs 00–05)  
**Consumed by:** All developers; this is the glue that makes the monorepo work

---

## Purpose

Wire all modules together into a coherent monorepo, validate that every module's acceptance criteria passes, and provide a one-command developer experience.

Primary mandate: **if `make dev` doesn't work, NeuroOS doesn't work.**

---

## Deliverables

### Monorepo root: `/` (workspace root)

| File | Responsibility |
|---|---|
| `package.json` | pnpm workspace root, Turborepo scripts |
| `pnpm-workspace.yaml` | Workspace package globs |
| `turbo.json` | Pipeline dependency graph for build/test/lint |
| `Makefile` | Human-friendly development commands |
| `.nvmrc` | Node.js version pin (20.x) |
| `.python-version` | Python version pin (3.11) |
| `tsconfig.base.json` | Shared TypeScript compiler options |
| `.eslintrc.json` | Shared ESLint config (TypeScript + Prettier) |
| `.prettierrc` | Shared Prettier config |
| `pyproject.toml` | Root Python project config (mypy, ruff, pytest) |

### Docker: `docker/`

| File | Responsibility |
|---|---|
| `docker-compose.yml` | Full stack: all services + networking |
| `docker-compose.dev.yml` | Dev override: volume mounts, hot reload |
| `Dockerfile.data-generator` | Python 3.11 slim image for data generator |
| `Dockerfile.dsp-pipeline` | Python 3.11 slim image for DSP pipeline |
| `Dockerfile.intent-engine` | Python 3.11 slim image for intent engine |
| `Dockerfile.platform-core` | Node.js 20 alpine image for platform core |

### GitHub Actions: `.github/workflows/`

| File | Trigger | Responsibility |
|---|---|---|
| `ci.yml` | push, PR | Full lint + unit test + integration test |
| `benchmark.yml` | manual, weekly | Latency benchmark vs. BCI2000 targets |
| `release.yml` | tag v*.*.* | Build, publish SDK to npm + PyPI |
| `security.yml` | daily | npm audit + pip-audit |

### Integration Tests: `tests/integration/`

| File | What it Tests |
|---|---|
| `test_full_pipeline.py` | Simulator → DSP → Intent → Platform Core end-to-end |
| `test_latency.py` | End-to-end latency vs. 15 ms BCI2000 benchmark |
| `test_scenario_accuracy.py` | Per-scenario intent accuracy across canned scenarios |
| `test_sdk_e2e.test.ts` | SDK connects to running platform, receives intents |
| `test_ws_stream.test.ts` | WebSocket streaming protocol conformance |

### Benchmark Suite: `tests/benchmarks/`

| File | Metric |
|---|---|
| `bench_dsp_latency.py` | DSP per-frame processing time |
| `bench_intent_latency.py` | Intent engine inference time per vector |
| `bench_e2e_latency.py` | Full pipeline output latency + jitter |
| `bench_throughput.py` | Max sustainable frame rate before dropping |

---

## Monorepo Structure

```
neuroos/
├── packages/
│   ├── data-generator/      # Job 01 (Python)
│   ├── dsp-pipeline/        # Job 02 (Python)
│   ├── intent-engine/       # Job 03 (Python)
│   ├── platform-core/       # Job 04 (TypeScript)
│   ├── sdk-ts/              # Job 05 (TypeScript)
│   └── playground/          # Job 05 (TypeScript)
├── examples/                # Job 05
├── jobs/                    # This folder (agent job specs)
├── tests/
│   ├── integration/
│   └── benchmarks/
├── docker/
├── .github/
│   └── workflows/
├── docs/
├── Makefile
├── package.json
├── pnpm-workspace.yaml
├── turbo.json
├── tsconfig.base.json
├── pyproject.toml
└── README.md
```

---

## Makefile

```makefile
.PHONY: dev test lint benchmark clean setup

# One-command developer setup
setup:
	pnpm install
	pip install -e packages/data-generator -e packages/dsp-pipeline -e packages/intent-engine
	cp packages/platform-core/config/neuroos.config.yaml.example neuroos.config.yaml

# Start all services in development mode (hot reload)
dev:
	docker-compose -f docker/docker-compose.yml -f docker/docker-compose.dev.yml up

# Run all unit tests across all packages
test:
	pnpm turbo run test
	pytest packages/data-generator/tests packages/dsp-pipeline/tests packages/intent-engine/tests -v

# Run integration tests (requires running services)
test-integration:
	pytest tests/integration/ -v
	pnpm vitest run tests/integration/

# Run full lint (TypeScript + Python)
lint:
	pnpm turbo run lint
	ruff check packages/
	mypy packages/data-generator packages/dsp-pipeline packages/intent-engine

# Run benchmark suite and print results table
benchmark:
	pytest tests/benchmarks/ -v --benchmark-only --benchmark-sort=mean

# Type check all TypeScript packages
typecheck:
	pnpm turbo run typecheck

# Build all packages for production
build:
	pnpm turbo run build

# Remove all build artifacts
clean:
	pnpm turbo run clean
	find . -name "*.pyc" -delete
	find . -name "__pycache__" -delete
```

---

## Turborepo Pipeline (`turbo.json`)

```json
{
  "$schema": "https://turbo.build/schema.json",
  "pipeline": {
    "build": {
      "dependsOn": ["^build"],
      "outputs": ["dist/**"]
    },
    "test": {
      "dependsOn": ["build"],
      "outputs": ["coverage/**"]
    },
    "lint": {
      "outputs": []
    },
    "typecheck": {
      "dependsOn": ["^build"],
      "outputs": []
    },
    "clean": {
      "cache": false
    }
  }
}
```

---

## Docker Compose

```yaml
# docker/docker-compose.yml
version: "3.9"

services:
  data-generator:
    build:
      context: ..
      dockerfile: docker/Dockerfile.data-generator
    command: python -m data_generator --scenario motor_imagery_left --channels 16
    # Writes frames to stdout; platform-core reads via subprocess pipe.
    # In compose, we use a named pipe via shared volume.
    volumes:
      - pipes:/tmp/neuroos/pipes

  dsp-pipeline:
    build:
      context: ..
      dockerfile: docker/Dockerfile.dsp-pipeline
    command: python -m dsp_pipeline
    volumes:
      - pipes:/tmp/neuroos/pipes
    depends_on: [data-generator]

  intent-engine:
    build:
      context: ..
      dockerfile: docker/Dockerfile.intent-engine
    command: python -m intent_engine
    volumes:
      - pipes:/tmp/neuroos/pipes
    depends_on: [dsp-pipeline]

  platform-core:
    build:
      context: ..
      dockerfile: docker/Dockerfile.platform-core
    ports:
      - "3000:3000"
    volumes:
      - pipes:/tmp/neuroos/pipes
      - sessions:/root/.neuroos/sessions
    depends_on: [intent-engine]
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:3000/health"]
      interval: 5s
      timeout: 3s
      retries: 5

volumes:
  pipes:
  sessions:
```

---

## CI Workflow (`ci.yml`)

```yaml
name: CI

on:
  push:
    branches: [main, develop]
  pull_request:

jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: { node-version: '20', cache: 'pnpm' }
      - uses: actions/setup-python@v5
        with: { python-version: '3.11' }
      - run: pnpm install --frozen-lockfile
      - run: pip install ruff mypy
      - run: make lint

  test-ts:
    runs-on: ubuntu-latest
    needs: lint
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: { node-version: '20', cache: 'pnpm' }
      - run: pnpm install --frozen-lockfile
      - run: pnpm turbo run test --filter='!@neuroos/sdk-py' -- --coverage
      - uses: codecov/codecov-action@v4

  test-python:
    runs-on: ubuntu-latest
    needs: lint
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: '3.11' }
      - run: pip install -e packages/data-generator -e packages/dsp-pipeline -e packages/intent-engine pytest pytest-cov pytest-asyncio
      - run: pytest packages/*/tests/ -v --cov --cov-report=xml
      - uses: codecov/codecov-action@v4

  integration:
    runs-on: ubuntu-latest
    needs: [test-ts, test-python]
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: { node-version: '20', cache: 'pnpm' }
      - uses: actions/setup-python@v5
        with: { python-version: '3.11' }
      - run: pnpm install --frozen-lockfile
      - run: pip install -e packages/data-generator -e packages/dsp-pipeline -e packages/intent-engine
      - name: Start platform core
        run: pnpm --filter platform-core start &
      - name: Wait for platform to be ready
        run: npx wait-on http://localhost:3000/health
      - run: pytest tests/integration/test_full_pipeline.py tests/integration/test_latency.py -v
      - run: pnpm vitest run tests/integration/

  latency-gate:
    runs-on: ubuntu-latest
    needs: integration
    steps:
      - uses: actions/checkout@v4
      - name: Run latency benchmark
        run: |
          pytest tests/benchmarks/bench_e2e_latency.py -v --benchmark-json=benchmark.json
      - name: Assert P95 < 15ms
        run: |
          python -c "
          import json
          with open('benchmark.json') as f:
              data = json.load(f)
          for bench in data['benchmarks']:
              p95 = bench['stats']['q_95'] * 1000  # ns → ms
              assert p95 < 15, f'P95 latency {p95:.1f}ms exceeds 15ms budget!'
          print('Latency gate: PASSED')
          "
```

---

## Integration Test: Full Pipeline

```python
# tests/integration/test_full_pipeline.py
import asyncio
import pytest
from neuroos import NeuroOS

@pytest.mark.asyncio
async def test_motor_imagery_intent_arrives():
    """End-to-end: simulator + full stack → SDK receives intent."""
    async with NeuroOS(base_url="http://localhost:3000") as client:
        device = await client.devices.register("neuroos-simulator", num_channels=16)
        session = await client.sessions.start(
            device_id=device["deviceId"],
            subject_id="test",
            session_name="integration-test",
            paradigm="motor_imagery",
        )

        intents = []
        async for intent in client.intents.stream():
            intents.append(intent)
            if len(intents) >= 10:
                break

        await client.sessions.stop(session["sessionId"])

    assert len(intents) == 10
    assert all(intent["confidence"] >= 0 for intent in intents)
    assert all(intent["endToEndLatencyMs"] >= 0 for intent in intents)
```

---

## Latency Benchmark

```python
# tests/benchmarks/bench_e2e_latency.py
"""
Replicates BCI2000 Table I methodology.
Measures output latency: time from frame acquisition to IntentEvent receipt.
Target: mean < 15 ms, jitter (std) < 2 ms.
"""
import asyncio
import statistics
import pytest

@pytest.mark.benchmark
async def test_latency_benchmark():
    latencies = []
    # ... connect to running platform, collect 1000 IntentEvent.endToEndLatencyMs values
    assert statistics.mean(latencies) < 15.0,  f"Mean latency {statistics.mean(latencies):.1f}ms > 15ms"
    assert statistics.stdev(latencies) < 2.0,  f"Latency jitter {statistics.stdev(latencies):.1f}ms > 2ms"
    assert max(latencies) < 50.0,              f"Max latency {max(latencies):.1f}ms is concerning"
    print(f"\nLatency results (n={len(latencies)}):")
    print(f"  Mean:   {statistics.mean(latencies):.2f} ms")
    print(f"  P95:    {sorted(latencies)[int(0.95*len(latencies))]:.2f} ms")
    print(f"  P99:    {sorted(latencies)[int(0.99*len(latencies))]:.2f} ms")
    print(f"  Jitter: {statistics.stdev(latencies):.2f} ms")
    print(f"  Max:    {max(latencies):.2f} ms")
```

---

## Scenario Accuracy Test

```python
# tests/integration/test_scenario_accuracy.py
"""
For each canned scenario, verify that the full pipeline produces
the expected dominant intent label.
"""
SCENARIO_EXPECTATIONS = {
    "motor_imagery_left":  "motor_imagery_left",
    "motor_imagery_right": "motor_imagery_right",
    "rest":                "motor_imagery_rest",
    "p300_target":         "p300_target",
}

@pytest.mark.parametrize("scenario,expected_label", SCENARIO_EXPECTATIONS.items())
async def test_scenario_accuracy(scenario: str, expected_label: str):
    # ... configure simulator to scenario, collect 50 intents, check majority label
    dominant_label = most_common([i["label"] for i in intents])
    assert dominant_label == expected_label, \
        f"Scenario '{scenario}': expected '{expected_label}', got '{dominant_label}'"
```

---

## Acceptance Criteria

- [ ] `make setup && make dev` brings up all services with zero errors
- [ ] `make test` passes with zero failures across all packages
- [ ] `make lint` passes with zero warnings (TypeScript strict mode + ruff E + mypy strict)
- [ ] `make benchmark` prints a latency table showing mean <15 ms
- [ ] GitHub Actions `ci.yml` runs green on main branch push
- [ ] `latency-gate` job passes (P95 <15 ms asserted programmatically)
- [ ] `test_scenario_accuracy.py` passes for all 4 scenarios
- [ ] `docker-compose up` starts all 4 services; platform-core healthcheck passes within 30 s
- [ ] Release workflow publishes `@neuroos/sdk` to npm test registry

---

## Must NOT Do

- Implement any signal processing, classification, or business logic
- Modify Platform Core routes or SDK public API
- Import from job folders (this job orchestrates them at process level only)
