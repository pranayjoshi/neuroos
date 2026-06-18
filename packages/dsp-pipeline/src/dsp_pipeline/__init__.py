"""Compatibility package for `from dsp_pipeline import ...` imports."""

from config import DSPConfig
from pipeline import DSPPipeline, Pipeline, PipelineLatencyError

__all__ = ["DSPConfig", "DSPPipeline", "Pipeline", "PipelineLatencyError"]
