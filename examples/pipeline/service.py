"""Finger tactile acquisition loop for example dashboards."""

from __future__ import annotations

import time
from dataclasses import dataclass

import numpy as np
from orisys.finger import FingerRuntime, compute_uv_surface_frames

from viz import FrameRecorder, build_uv_surface_mesh, resolve_viz_pose_path

from .config import PipelineConfig
from .csv_recorder import CsvMeasurement
from .frame import FingerFrameView
from .profiling import StageProfiler, run_deformation_timed


@dataclass
class TickTimings:
    capture_ms: float = 0.0
    uv_unroll_ms: float = 0.0
    flow_ms: float = 0.0
    hhd_ms: float = 0.0
    contact_ms: float = 0.0
    read_info_ms: float = 0.0
    pipeline_ms: float = 0.0


class FingerPipeline:
    """Owns FingerRuntime and produces FingerFrameView snapshots per tick."""

    def __init__(self, config: PipelineConfig):
        self.config = config
        self.runtime: FingerRuntime | None = None
        self.recorder = FrameRecorder()
        self._start_time: float | None = None
        self.uv_mesh = None
        self.world_to_cam: np.ndarray | None = None
        self.mesh_lookat: np.ndarray | None = None
        self.profiler: StageProfiler | None = (
            StageProfiler(report_every=config.profile_every) if config.profile else None
        )
        self._world_xyz: np.ndarray | None = None
        self._surface_mask: np.ndarray | None = None
        self._geometric_center: np.ndarray | None = None
        self._tangent_x: np.ndarray | None = None
        self._tangent_y: np.ndarray | None = None
        self._normals: np.ndarray | None = None

    @property
    def is_open(self) -> bool:
        return self.runtime is not None

    @property
    def tactile(self):
        if self.runtime is None:
            raise RuntimeError("FingerPipeline is not open")
        return self.runtime.tactile

    def open(self) -> None:
        if self.runtime is not None:
            return
        self.runtime = FingerRuntime.open(
            export_dir=self.config.export_dir,
            config=self.config.config,
            calib=self.config.calib,
            video=self.config.video,
            verbose=self.config.verbose,
        )
        self._prepare_mesh_assets()
        self.runtime.warmup(color=self.config.use_color)
        self._start_time = time.time()

    def _prepare_mesh_assets(self) -> None:
        if self.runtime is None:
            return
        domain = self.runtime.domain
        if domain.surface is None or getattr(domain.surface, "world_xyz", None) is None:
            return
        self.uv_mesh = build_uv_surface_mesh(domain.surface.world_xyz, domain.valid_mask)
        self._cache_surface_geometry(domain.surface.world_xyz, domain.valid_mask)
        if self.config.viz_pose.lower() != "none":
            self.world_to_cam = np.load(resolve_viz_pose_path(self.config.viz_pose))
            self.mesh_lookat = self.uv_mesh.rest_vertices.mean(axis=0)

    def _cache_surface_geometry(self, world_xyz: np.ndarray, valid_mask: np.ndarray) -> None:
        world_xyz = np.asarray(world_xyz, dtype=np.float64)
        valid_mask = np.asarray(valid_mask, dtype=bool)
        finite = np.all(np.isfinite(world_xyz), axis=2)
        mask = valid_mask & finite
        self._world_xyz = world_xyz
        self._surface_mask = mask
        points = world_xyz[mask]
        self._geometric_center = (
            points.mean(axis=0) if len(points) else np.zeros(3, dtype=np.float64)
        )
        self._tangent_x, self._tangent_y, self._normals = compute_uv_surface_frames(
            world_xyz, mask
        )

    def close(self) -> None:
        if self.profiler is not None and self.profiler.frame_count:
            self.profiler.print_report(prefix="[profile final]")
        if self.runtime is not None:
            self.runtime.close()
            self.runtime = None
        self._start_time = None
        self._world_xyz = None
        self._surface_mask = None
        self._geometric_center = None
        self._tangent_x = None
        self._tangent_y = None
        self._normals = None

    def reset(self) -> None:
        if self.runtime is not None:
            self.runtime.tactile.reset()

    def tick(self) -> FingerFrameView | None:
        frame, _timings = self.tick_timed()
        return frame

    def tick_timed(self) -> tuple[FingerFrameView | None, TickTimings]:
        timings = TickTimings()
        if self.runtime is None or self._start_time is None:
            return None, timings

        pipeline_t0 = time.perf_counter()
        profile = self.profiler is not None

        if profile:
            t0 = time.perf_counter()
            ok, frame = self.runtime.read_source()
            timings.capture_ms = (time.perf_counter() - t0) * 1000.0
            if not ok:
                return None, timings
            t0 = time.perf_counter()
            unrolled = self.runtime.process_frame(frame, color=self.config.use_color)
            timings.uv_unroll_ms = (time.perf_counter() - t0) * 1000.0
        else:
            ok, unrolled = self.runtime.grab_and_process(color=self.config.use_color)
            if not ok:
                return None, timings

        tactile = self.runtime.tactile
        self.recorder.write_if_recording(tactile.frame)

        if profile:
            flow_ms, hhd_ms = run_deformation_timed(
                tactile, check_motion=True, threshold=0
            )
            timings.flow_ms = flow_ms
            timings.hhd_ms = hhd_ms
            self.profiler.record("capture", timings.capture_ms)
            self.profiler.record("uv_unroll", timings.uv_unroll_ms)
            self.profiler.record("flow", timings.flow_ms)
            self.profiler.record("hhd", timings.hhd_ms)
        else:
            tactile.compute_deformation(decompose=True, check_motion=True, threshold=0)

        t0 = time.perf_counter()
        tactile.compute_contact()
        timings.contact_ms = (time.perf_counter() - t0) * 1000.0
        if profile:
            self.profiler.record("contact", timings.contact_ms)

        t0 = time.perf_counter()
        view = FingerFrameView.from_tactile(
            tactile,
            unrolled,
            timestamp=time.time() - self._start_time,
        )
        timings.read_info_ms = (time.perf_counter() - t0) * 1000.0
        if profile:
            self.profiler.record("read_info", timings.read_info_ms)

        timings.pipeline_ms = (time.perf_counter() - pipeline_t0) * 1000.0
        if profile:
            self.profiler.record("pipeline", timings.pipeline_ms)

        return view, timings

    def record_total_frame(self, total_ms: float) -> None:
        if self.profiler is None:
            return
        self.profiler.record("total", total_ms)
        self.profiler.tick()

    def start_recording(self) -> bool:
        if self.runtime is None:
            return False
        return self.recorder.start(self.runtime.tactile.frame)

    def stop_recording(self) -> None:
        self.recorder.stop()

    def measure_for_csv(self, frame: FingerFrameView, frame_index: int) -> CsvMeasurement:
        """Lift contact + local forces into global-frame measurements for CSV export."""
        nan = float("nan")
        contact = (nan, nan, nan)
        normal = (nan, nan, nan)

        fn = float(frame.fnormal)
        fx = float(frame.fshearx)
        fy = float(frame.fsheary)

        if (
            frame.centroid_found
            and frame.centroid is not None
            and np.asarray(frame.centroid).size >= 2
            and self._world_xyz is not None
            and self._geometric_center is not None
            and self._normals is not None
            and self._tangent_x is not None
            and self._tangent_y is not None
        ):
            cx = int(round(float(np.asarray(frame.centroid).reshape(-1)[0])))
            cy = int(round(float(np.asarray(frame.centroid).reshape(-1)[1])))
            h, w = self._world_xyz.shape[:2]
            if 0 <= cy < h and 0 <= cx < w:
                if self._surface_mask is None or bool(self._surface_mask[cy, cx]):
                    world = self._world_xyz[cy, cx]
                    if np.all(np.isfinite(world)):
                        centered = world - self._geometric_center
                        contact = (float(centered[0]), float(centered[1]), float(centered[2]))

                    n = self._normals[cy, cx]
                    n_norm = float(np.linalg.norm(n))
                    if n_norm > 1e-8:
                        n_u = n / n_norm
                        normal = (float(n_u[0]), float(n_u[1]), float(n_u[2]))

        return CsvMeasurement(
            frame_index=int(frame_index),
            timestamp_s=float(frame.timestamp),
            contact_x=contact[0],
            contact_y=contact[1],
            contact_z=contact[2],
            normal_x=normal[0],
            normal_y=normal[1],
            normal_z=normal[2],
            force_local_fn=fn,
            force_local_fx=fx,
            force_local_fy=fy,
        )
