"""Shared stage timing helpers for finger example pipelines."""

from __future__ import annotations

import time
from collections import defaultdict


class StageProfiler:
    """Accumulate per-stage wall times and print rolling averages."""

    DEFAULT_ORDER = (
        "capture",
        "uv_unroll",
        "flow",
        "hhd",
        "contact",
        "read_info",
        "pipeline",
        "mesh",
        "arrows",
        "charts",
        "display",
        "total",
    )

    def __init__(self, *, report_every: int = 30, stage_order: tuple[str, ...] | None = None):
        self.report_every = max(1, int(report_every))
        self.stage_order = stage_order or self.DEFAULT_ORDER
        self.frame_count = 0
        self.totals: dict[str, float] = defaultdict(float)
        self.last: dict[str, float] = {}

    def record(self, name: str, ms: float) -> None:
        self.totals[name] += ms
        self.last[name] = ms

    def tick(self) -> None:
        self.frame_count += 1
        if self.frame_count % self.report_every == 0:
            self.print_report(prefix=f"[profile {self.frame_count} frames]")

    def print_report(self, *, prefix: str = "[profile summary]") -> None:
        if self.frame_count == 0:
            return
        n = self.frame_count
        parts = []
        for name in self.stage_order:
            if name in self.totals:
                parts.append(f"{name}={self.totals[name] / n:.2f}ms")
        total_ms = self.totals.get("total", 0.0) / n
        if total_ms > 0:
            parts.append(f"fps={1000.0 / total_ms:.1f}")
        print(f"\n{prefix} " + " | ".join(parts))


def run_deformation_timed(tactile, *, check_motion=True, threshold=0, tail_frames=10):
    """Run flow + gated HHD; return (flow_ms, hhd_ms). Mirrors Sensor.compute_deformation."""
    sensor = tactile.raw_sensor

    t0 = time.perf_counter()
    sensor.compute_flow()
    flow_ms = (time.perf_counter() - t0) * 1000.0

    run_hhd = True
    if check_motion:
        is_motion = sensor.detect_motion(threshold=threshold)
        try:
            tail_frames = max(0, int(tail_frames))
        except (TypeError, ValueError):
            tail_frames = 0

        if is_motion:
            sensor.tail_frames_count = 0
        elif sensor.tail_frames_count < tail_frames:
            sensor.tail_frames_count += 1
        else:
            run_hhd = False
            sensor.tail_frames_count = tail_frames

    hhd_ms = 0.0
    if run_hhd:
        t1 = time.perf_counter()
        sensor.compute_hhd()
        hhd_ms = (time.perf_counter() - t1) * 1000.0

    return flow_ms, hhd_ms
