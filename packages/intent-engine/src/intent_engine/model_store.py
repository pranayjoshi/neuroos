"""
Model Store — save/load classifier weights in ONNX and numpy formats.

Supports:
  - ONNX export of sklearn classifiers (LDA, CSP-LDA) via skl2onnx.
  - ONNX inference session loading via onnxruntime.
  - NumPy array save/load (.npy) for P300 templates.
  - Pickle fallback for any sklearn estimator.

Usage
-----
store = ModelStore()
store.save_sklearn_to_onnx(clf.sklearn_model, "lda.onnx", n_features=6)
session = store.load_onnx("lda.onnx")
# session.run(None, {"float_input": x})
"""

from __future__ import annotations

import pickle
from pathlib import Path
from typing import Any

import numpy as np

try:
    import onnxruntime as ort

    _ORT_AVAILABLE = True
except ImportError:
    _ORT_AVAILABLE = False

try:
    from skl2onnx import convert_sklearn
    from skl2onnx.common.data_types import FloatTensorType

    _SKL2ONNX_AVAILABLE = True
except ImportError:
    _SKL2ONNX_AVAILABLE = False


class ModelStore:
    """
    Centralised utility for serialising and loading model artefacts.

    All paths are accepted as str or pathlib.Path.
    """

    # ------------------------------------------------------------------
    # ONNX
    # ------------------------------------------------------------------

    def save_sklearn_to_onnx(
        self,
        sklearn_model: Any,
        path: str | Path,
        n_features: int,
        input_name: str = "float_input",
    ) -> None:
        """
        Export a fitted sklearn model to ONNX format.

        Parameters
        ----------
        sklearn_model:
            A fitted sklearn estimator (e.g. LinearDiscriminantAnalysis).
        path:
            Output .onnx file path.
        n_features:
            Number of input features (required for ONNX shape specification).
        input_name:
            ONNX input tensor name (default 'float_input').

        Raises
        ------
        RuntimeError
            If skl2onnx is not installed.
        """
        if not _SKL2ONNX_AVAILABLE:
            raise RuntimeError(
                "skl2onnx is not installed. Install it with: pip install skl2onnx"
            )
        initial_type = [(input_name, FloatTensorType([None, n_features]))]
        onx = convert_sklearn(sklearn_model, initial_types=initial_type)
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(onx.SerializeToString())

    def load_onnx(self, path: str | Path) -> "ort.InferenceSession":
        """
        Load an ONNX model and return an onnxruntime InferenceSession.

        Raises
        ------
        RuntimeError
            If onnxruntime is not installed.
        FileNotFoundError
            If the model file does not exist.
        """
        if not _ORT_AVAILABLE:
            raise RuntimeError(
                "onnxruntime is not installed. Install it with: pip install onnxruntime"
            )
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"ONNX model not found: {path}")
        return ort.InferenceSession(
            str(path),
            providers=["CPUExecutionProvider"],
        )

    def predict_onnx(
        self,
        session: "ort.InferenceSession",
        features: np.ndarray,
        input_name: str = "float_input",
    ) -> tuple[np.ndarray, np.ndarray]:
        """
        Run inference on an ONNX session.

        Parameters
        ----------
        session:
            An onnxruntime InferenceSession.
        features:
            [n_features] or [1, n_features] float32 input.
        input_name:
            ONNX input tensor name.

        Returns
        -------
        labels:
            [1] predicted integer class label.
        probabilities:
            [1, n_classes] class probability array.
        """
        x = features.reshape(1, -1).astype(np.float32)
        output_names = [o.name for o in session.get_outputs()]
        outputs = session.run(output_names, {input_name: x})
        # ONNX sklearn classifiers output: [label_array, {label: prob} dict list]
        # Flatten to ndarray
        labels = np.array(outputs[0]).ravel()
        if len(outputs) > 1 and isinstance(outputs[1], list) and len(outputs[1]) > 0:
            prob_dict = outputs[1][0]
            proba = np.array(list(prob_dict.values()), dtype=np.float64)
        else:
            proba = np.ones(1, dtype=np.float64)
        return labels, proba

    # ------------------------------------------------------------------
    # NumPy arrays (P300 templates, CSP filters)
    # ------------------------------------------------------------------

    def save_numpy(self, array: np.ndarray, path: str | Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        np.save(str(path), array)

    def load_numpy(self, path: str | Path) -> np.ndarray:
        return np.load(str(path))

    # ------------------------------------------------------------------
    # Pickle fallback
    # ------------------------------------------------------------------

    def save_pickle(self, obj: Any, path: str | Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "wb") as fh:
            pickle.dump(obj, fh)

    def load_pickle(self, path: str | Path) -> Any:
        with open(path, "rb") as fh:
            return pickle.load(fh)

    # ------------------------------------------------------------------
    # Convenience: save / load whole IntentClassifier
    # ------------------------------------------------------------------

    def save_classifier(self, clf: Any, path: str | Path) -> None:
        """Pickle an IntentClassifier to disk."""
        self.save_pickle(clf, path)

    def load_classifier(self, path: str | Path) -> Any:
        """Load a pickled IntentClassifier from disk."""
        return self.load_pickle(path)
