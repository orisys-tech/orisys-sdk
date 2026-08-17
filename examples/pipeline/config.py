"""Configuration for the finger tactile example pipeline."""

from __future__ import annotations

from dataclasses import dataclass

from orisys.finger import DEFAULT_FINGER_EXPORT_DIR
from viz.mesh_camera import DEFAULT_FINGER_VIZ_POSE


def mesh_threshold(mesh_map: str, threshold: float | None) -> float:
    if threshold is not None:
        return threshold
    return 0.0 if mesh_map == "depth" else 0.4


@dataclass
class PipelineConfig:
    video: str = "0"
    config: str = "finger"
    calib: str | None = None
    export_dir: str = DEFAULT_FINGER_EXPORT_DIR
    csv_save_dir: str = "./outputs/csv"
    verbose: bool = False
    mesh_map: str = "depth"
    threshold: float | None = None
    viz_pose: str = DEFAULT_FINGER_VIZ_POSE
    enable_3d: bool = True
    use_color: bool = False
    lowpass_cutoff_hz: float = 5.0
    force_sample_rate_hz: float = 30.0
    profile: bool = False
    profile_every: int = 30

    @classmethod
    def from_args(cls, args) -> "PipelineConfig":
        return cls(
            video=args.video,
            config=args.config,
            calib=getattr(args, "cal", None) or None,
            verbose=args.verbose,
            mesh_map=args.mesh_map,
            threshold=args.threshold,
            viz_pose=args.viz_pose,
            enable_3d=not args.no_3d,
            lowpass_cutoff_hz=getattr(args, "cutoff", 5.0),
            profile=getattr(args, "profile", False),
            profile_every=getattr(args, "profile_every", 30),
            csv_save_dir=getattr(args, "csv_save_dir", "./outputs/csv"),
        )

    @property
    def flow_threshold(self) -> float:
        return mesh_threshold(self.mesh_map, self.threshold)
