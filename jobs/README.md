# NeuroOS — Agent Job Folder

This directory divides NeuroOS into self-contained agent jobs. Each job is a puzzle block with a strict typed contract on its inputs and outputs so multiple AI agents can build in parallel without collision.

## Architecture

NeuroOS is like iOS for brain-computer interfaces. Just as iOS abstracts iPhone hardware, NeuroOS abstracts brain signal complexity and exposes clean intent APIs. The design is grounded in the BCI2000 four-module model (Schalk et al., 2004): source → signal processing → user application → operator.

```
Hardware / Electrodes
        │  raw μV samples
        ▼
┌───────────────────┐
│  Job 01           │  EEG/EMG Dummy Data Generator
│  Data Generator   │  (Source Module)
└────────┬──────────┘
         │  RawSignalFrame
         ▼
┌───────────────────┐
│  Job 02           │  Bio-Signal DSP Pipeline
│  DSP Engineer     │  (Signal Processing Module)
└────────┬──────────┘
         │  FeatureVector
         ▼
┌───────────────────┐
│  Job 03           │  Intent Engine
│  Intent Engine    │  (AI Classifier + Normalizer)
└────────┬──────────┘
         │  IntentEvent
         ▼
┌───────────────────┐
│  Job 04           │  Platform Core
│  Platform Arch.   │  (OS Layer: Registry, Session, API)
└────────┬──────────┘
         │  REST / WebSocket API
         ▼
┌───────────────────┐
│  Job 05           │  Developer SDK
│  SDK Engineer     │  (@neuroos/sdk + Python neuroos)
└───────────────────┘

Job 06 — CI/CD Infrastructure (cross-cutting, integrates all)
Job 00 — Shared Contracts    (prerequisite for all)
```

## Job Dependency & Parallelism

```
Wave 1:  Job 00 (Shared Contracts)          ← must complete first
Wave 2:  Job 01, Job 02, Job 03, Job 04     ← all parallel
Wave 3:  Job 05                             ← after Job 04
Wave 4:  Job 06                             ← after all others
```

## Job Index

| Folder                  | Agent Role           | Input              | Output              |
|-------------------------|----------------------|--------------------|---------------------|
| `00_shared_contracts/`  | Any (prerequisite)   | —                  | TypeScript schemas  |
| `01_data_generator/`    | Data Generator       | DeviceAdapter ifc  | RawSignalFrame      |
| `02_dsp_pipeline/`      | DSP Engineer         | RawSignalFrame     | FeatureVector       |
| `03_intent_engine/`     | Intent Engine        | FeatureVector      | IntentEvent         |
| `04_platform_core/`     | Platform Architect   | DeviceAdapter + IE | REST/WS API         |
| `05_developer_sdk/`     | SDK Engineer         | REST/WS API        | npm + PyPI packages |
| `06_cicd_infra/`        | CI/CD Manager        | All modules        | Green CI + Docker   |

## Rules for All Agents

1. **Read your JOB.md fully before writing any code.**
2. **Import types only from `00_shared_contracts/schema/`** — never redefine them.
3. **Respect your "Must NOT do" list** — scope violations break other agents' contracts.
4. **Your acceptance criteria in JOB.md is the definition of done.**
5. **Write unit tests for every public function** — Job 06 will run them.
6. **Use the tech stack defined in your JOB.md** — no unapproved dependencies.

## Tech Stack Summary

- TypeScript (Node.js 20) — Platform Core, Developer SDK
- Python 3.11 — DSP Pipeline, Intent Engine, Data Generator
- NumPy / SciPy / MNE-Python — signal processing
- PyTorch (training) + ONNX Runtime (inference) — ML models
- Fastify + `@fastify/websocket` — REST/WS API
- pnpm workspaces + Turborepo — monorepo
- Docker Compose — multi-service dev environment
- GitHub Actions — CI/CD
