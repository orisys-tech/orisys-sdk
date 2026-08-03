"""Simple frame recording helper for example scripts."""

from __future__ import annotations

import os
from pathlib import Path

import cv2

from .render_2d import frame_to_bgr


class FrameRecorder:
    """Write camera frames to disk on demand (start/stop via keyboard hooks)."""

    def __init__(self, save_path: str | Path = "./data/pulse_test.mp4", fps: int = 30) -> None:
        self.save_path = Path(save_path)
        self.fps = fps
        self._writer: cv2.VideoWriter | None = None
        self._is_recording = False
        self._frame_count = 0

    @property
    def is_recording(self) -> bool:
        return self._is_recording

    def write_if_recording(self, frame) -> None:
        if not self._is_recording or self._writer is None or frame is None:
            return
        self._writer.write(frame_to_bgr(frame))
        self._frame_count += 1

    def start(self, frame) -> bool:
        if frame is None:
            print("当前没有可用帧，无法确定录像尺寸。")
            return False

        self.save_path.parent.mkdir(parents=True, exist_ok=True)
        bgr = frame_to_bgr(frame)
        height, width = bgr.shape[:2]
        writer = cv2.VideoWriter(
            str(self.save_path),
            cv2.VideoWriter_fourcc(*"mp4v"),
            self.fps,
            (width, height),
        )
        if not writer.isOpened():
            print(f"无法创建录像文件：{self.save_path}")
            return False

        self._writer = writer
        self._is_recording = True
        self._frame_count = 0
        print(f"开始录像：{self.save_path}")
        return True

    def stop(self) -> tuple[Path | None, int]:
        self._is_recording = False
        if self._writer is not None:
            self._writer.release()
            self._writer = None

        path = self.save_path if self._frame_count else None
        if path is not None:
            print(f"录像结束：{path}，总帧数：{self._frame_count}")
        else:
            print(f"录像结束，总帧数：{self._frame_count}")

        count = self._frame_count
        self._frame_count = 0
        return path, count
