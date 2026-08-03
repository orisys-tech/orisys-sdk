"""Finger example pipeline: runtime acquisition without GUI dependencies."""

from .config import PipelineConfig, mesh_threshold
from .csv_recorder import CSV_COLUMNS, CsvMeasurement, CsvRecorder
from .frame import FingerFrameView
from .service import FingerPipeline

__all__ = [
    "CSV_COLUMNS",
    "CsvMeasurement",
    "CsvRecorder",
    "FingerFrameView",
    "FingerPipeline",
    "PipelineConfig",
    "mesh_threshold",
]
