"""Runtime mesh viewport UI state shared by settings and the 3D mesh panel."""

from __future__ import annotations

from PyQt5.QtCore import QObject, pyqtSignal

from .layout import DashboardLayout, LAYOUT


class MeshViewState(QObject):
    """Mutable runtime toggles for the embedded mesh viewport."""

    flow_arrows_changed = pyqtSignal(bool)

    def __init__(self, *, flow_arrows_enabled: bool = True):
        super().__init__()
        self._flow_arrows_enabled = bool(flow_arrows_enabled)

    @property
    def flow_arrows_enabled(self) -> bool:
        return self._flow_arrows_enabled

    @classmethod
    def from_layout(cls, layout: DashboardLayout = LAYOUT) -> MeshViewState:
        return cls(flow_arrows_enabled=layout.mesh_flow_arrow.enabled)

    def set_flow_arrows_enabled(self, enabled: bool) -> None:
        enabled = bool(enabled)
        if enabled == self._flow_arrows_enabled:
            return
        self._flow_arrows_enabled = enabled
        self.flow_arrows_changed.emit(enabled)
