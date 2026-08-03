"""CSV recorder for DD02 contact / force logging."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


CSV_COLUMNS = (
    "frame_index",
    "timestamp_s",
    "contact_x_mm",
    "contact_y_mm",
    "contact_z_mm",
    "normal_x",
    "normal_y",
    "normal_z",
    "force_local_fn",
    "force_local_fx",
    "force_local_fy",
)


@dataclass
class CsvMeasurement:
    frame_index: int
    timestamp_s: float
    contact_x: float
    contact_y: float
    contact_z: float
    normal_x: float
    normal_y: float
    normal_z: float
    force_local_fn: float
    force_local_fx: float
    force_local_fy: float


def measurement_to_csv_row(row: CsvMeasurement) -> dict[str, float | int]:
    return {
        "frame_index": row.frame_index,
        "timestamp_s": row.timestamp_s,
        "contact_x_mm": row.contact_x,
        "contact_y_mm": row.contact_y,
        "contact_z_mm": row.contact_z,
        "normal_x": row.normal_x,
        "normal_y": row.normal_y,
        "normal_z": row.normal_z,
        "force_local_fn": row.force_local_fn,
        "force_local_fx": row.force_local_fx,
        "force_local_fy": row.force_local_fy,
    }


class CsvRecorder:
    """Write one contact/force measurement row per frame."""

    def __init__(self, save_dir: str | Path = "./outputs/csv") -> None:
        self.save_dir = Path(save_dir)
        self._file = None
        self._writer: csv.DictWriter | None = None
        self._path: Path | None = None
        self._row_count = 0

    @property
    def is_recording(self) -> bool:
        return self._writer is not None

    @property
    def path(self) -> Path | None:
        return self._path

    @property
    def row_count(self) -> int:
        return self._row_count

    def start(self, save_dir: str | Path | None = None) -> Path:
        if self.is_recording:
            self.stop()

        if save_dir is not None:
            self.save_dir = Path(save_dir)
        self.save_dir.mkdir(parents=True, exist_ok=True)

        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self._path = self.save_dir / f"dd02_record_{stamp}.csv"
        self._file = self._path.open("w", newline="", encoding="utf-8")
        self._writer = csv.DictWriter(self._file, fieldnames=CSV_COLUMNS)
        self._writer.writeheader()
        self._file.flush()
        self._row_count = 0
        return self._path

    def write(self, row: CsvMeasurement) -> None:
        if self._writer is None:
            return
        self._writer.writerow(measurement_to_csv_row(row))
        self._row_count += 1
        if self._file is not None and self._row_count % 30 == 0:
            self._file.flush()

    def stop(self) -> tuple[Path | None, int]:
        count = self._row_count
        saved_path = self._path
        if self._file is not None:
            self._file.flush()
            self._file.close()
        self._file = None
        self._writer = None
        self._path = None
        self._row_count = 0
        return saved_path, count
