"""Shared log-panel configuration for Qt viewers (2D and 3D)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LogConfig:
    """Log panel — edit LOG_CONFIG or DashboardLayout.log_config."""

    status_enabled: bool = True
    max_lines: int = 2000
    font_family: str = "Cascadia Mono"
    font_pt: int = 12
    show_flow: bool = True
    show_mask: bool = True

    def format_status(
        self,
        *,
        fps: float,
        fnormal: float,
        fshearx: float,
        fsheary: float,
        flow_rms: float = 0.0,
        mask_coverage: float = 0.0,
        wall_fps: float | None = None,
        contact_xyz_mm: tuple[float, float, float] | None = None,
    ) -> str:
        shear_mag = float((fshearx**2 + fsheary**2) ** 0.5)
        if wall_fps is not None:
            parts = [f"FPS={wall_fps:.1f}", f"sdk={fps:.1f}"]
        else:
            parts = [f"FPS={fps:.1f}"]
        parts.extend(
            [
                f"Fn={fnormal:.1f}",
                f"|(Fx,Fy)|={shear_mag:.1f}",
                f"Fx, Fy=({fshearx:.1f}, {fsheary:.1f})",
            ]
        )
        force_line = "  ".join(parts)
        if contact_xyz_mm is None:
            contact_line = "contact=---"
        else:
            cx, cy, cz = contact_xyz_mm
            contact_line = f"contact=({cx:.1f}, {cy:.1f}, {cz:.1f}) mm"
        return f"{force_line}\n{contact_line}"


LOG_CONFIG = LogConfig()
