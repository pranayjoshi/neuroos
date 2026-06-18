"""
NeuroOS Intent Engine — AI classifier: FeatureVector → IntentEvent.

Public API
----------
IntentEngine   — main orchestrator (engine.py)
EngineConfig   — engine configuration dataclass (engine.py)
IntentNormalizer — confidence calibration (normalizer.py)
OnlineTrainer  — streaming LDA adaptation (online_trainer.py)
ModelStore     — ONNX / pickle model I/O (model_store.py)

Classifiers
-----------
LDAClassifier           — Linear Discriminant Analysis
CSPLDAClassifier        — CSP spatial filter + LDA
P300Detector            — Template matching for P300
EnsembleClassifier      — Weighted ensemble
"""

from .classifiers import (
    ClassificationResult,
    CSPLDAClassifier,
    EnsembleClassifier,
    IntentClassifier,
    LDAClassifier,
    P300Detector,
)
from .engine import EngineConfig, IntentEngine
from .model_store import ModelStore
from .normalizer import IntentNormalizer
from .online_trainer import OnlineTrainer

__all__ = [
    "IntentClassifier",
    "ClassificationResult",
    "LDAClassifier",
    "CSPLDAClassifier",
    "P300Detector",
    "EnsembleClassifier",
    "IntentEngine",
    "EngineConfig",
    "IntentNormalizer",
    "OnlineTrainer",
    "ModelStore",
]
