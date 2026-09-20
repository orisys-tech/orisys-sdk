#!/usr/bin/env python3
"""Multi-sensor real-time example: N streams, one process each.

This is the deployment shape the multi-sensor throughput numbers assume. Each
stream owns a process and pipelines the per-frame work into three concurrent
stages (capture+unroll -> DIS flow -> HHD+readout), so a stream's rate is bounded
by its slowest stage instead of the sum of all three.

    # five finger streams from a video file (benchmark / smoke test)
    python examples/multi_stream.py --streams 5 -c finger -v data/dd02-0703/1.mp4

    # five live cameras, camera ids 0..4
    python examples/multi_stream.py --streams 5 -c finger --camera-base 0

    # single box sensor
    python examples/multi_stream.py --streams 1 -c box -v data/long.mp4

    # five streams, additionally recording an arrow-overlay video per stream
    # plus one 5-up mosaic, without stalling the pipeline
    python examples/multi_stream.py --streams 5 -c finger -v data/dd02-0703/1.mp4 \
        --seconds 10 --record outputs/arrows --mosaic

Notes
-----
* One process per stream. Threads inside a single process share the GIL and,
  measured on a 9950X, five finger streams reach ~150 FPS aggregate as threads
  versus ~626 FPS as processes.
* ``cv2.setNumThreads(2)`` per process: at five streams that beats 1, 4 and 8.
* Run one stream per process even when the sensor count is small; the process
  boundary also isolates a crashed camera from the rest.
* ``--record`` draws the DIS flow with ``orisys.util.draw_arrows`` (plus the
  contact overlay with ``--contact``) and encodes it with ``cv2.VideoWriter``.
  Both happen on a dedicated thread fed by a bounded drop-oldest queue, so the
  pipeline never waits on the encoder; frames the writer cannot keep up with are
  counted in the ``rec`` column as ``written/dropped``. Keep ``--record`` for
  verification runs - the encoder still competes for CPU with the pipeline.
"""

from __future__ import annotations

import argparse
import json
import multiprocessing as mp
import os
import statistics as st
import sys
import time

os.environ.setdefault("OPENCV_VIDEOIO_MSMF_ENABLE_HW_TRANSFORMS", "0")

import orisys
from orisys import StreamPipeline, StreamRecorder, configs


def _make_stream(args, index):
    """Return (sensor, produce, close) for one stream."""
    source = args.video
    if args.camera_base is not None:
        source = int(args.camera_base) + index
    if source is None:
        raise ValueError("pass --video PATH or --camera-base ID")

    cfg = configs.load_config(args.config)
    if str(cfg.get("type", "")).lower() == "single_camera":
        from orisys.finger import FingerRuntime

        runtime = FingerRuntime.open(config=args.config, video=source,
                                     verbose=False)
        return runtime.tactile.raw_sensor, _finger_produce(runtime), runtime.close

    sensor = orisys.Sensor(source, config_name=args.config, isstitch=True,
                           cuda=False, backend="cpu", verbose=False)

    def produce():
        return sensor.get_img()

    return sensor, produce, sensor.disconnect


def _finger_produce(runtime):
    def produce():
        ok, frame = runtime.grab_and_process(color=False)
        return frame if ok else None

    return produce


def worker(args, index, out_path):
    """One stream: own process, three-stage pipeline."""
    import cv2

    cv2.setNumThreads(int(args.threads))
    sensor, produce, close = _make_stream(args, index)

    frames = []
    stamps = []
    started = time.perf_counter()

    def collect(snap):
        frames.append(snap.age_ms)
        stamps.append(time.perf_counter())

    # Recording is entirely off the hot path: ``on_frame`` only pushes onto a
    # bounded drop-oldest queue, and a separate thread does the drawing and the
    # H.264/MPEG-4 encoding. The pipeline never blocks on the encoder.
    recorder = None
    on_frame = collect
    if args.record:
        recorder = StreamRecorder(
            os.path.join(args.record, f"stream_{index}.mp4"),
            fps=args.record_fps,
            every=args.record_every,
            fourcc=args.record_fourcc,
            valid_mask=lambda: getattr(sensor, "valid_mask", None),
            grid_spacing=args.record_grid,
            threshold=args.record_threshold,
            arrow_scale=args.record_arrow_scale,
            draw_contact=args.contact,
            label=f"#{index}",
            verbose=True,
        )

        def on_frame(snap, _collect=collect, _rec=recorder):
            _collect(snap)
            _rec.on_frame(snap)

    if args.no_arrays:
        include = ()
    elif recorder is not None:
        include = ("image", "flow")  # what the arrow overlay needs
    else:
        include = ("image",)

    pipe = StreamPipeline(sensor, produce, on_frame=on_frame,
                          include=include, contact=args.contact, depth=args.depth)
    pipe.start()
    record_stats = None
    try:
        deadline = started + args.seconds if args.seconds else None
        while True:
            if not pipe.running:
                break
            if args.frames and pipe.stats.published >= args.frames:
                break
            if deadline is not None and time.perf_counter() >= deadline:
                break
            time.sleep(0.002)
    finally:
        try:
            pipe.stop()
        except BaseException as exc:  # surface a stage failure
            print(f"[stream {index}] pipeline error: {type(exc).__name__}: {exc}",
                  file=sys.stderr)
            raise
        finally:
            if recorder is not None:
                record_stats = recorder.close()
            close()

    wall = time.perf_counter() - started
    # Steady-state rate: skip the first frames, which pay the JIT / HHD-cache /
    # DIS-reference-frame warm-up and would drag a short run's average down.
    warm = min(30, max(0, len(stamps) - 2))
    span = (stamps[-1] - stamps[warm]) if len(stamps) > warm + 1 else 0.0
    steady = (len(stamps) - 1 - warm) / span if span > 0 else 0.0
    payload = {
        "index": index,
        "published": pipe.stats.published,
        "wall": wall,
        "fps": pipe.stats.published / wall if wall else 0.0,
        "steady_fps": steady,
        "stats": pipe.stats.as_dict(),
        "age_p95_ms": float(st.quantiles(frames, n=20)[18]) if len(frames) >= 20 else 0.0,
        "record": record_stats,
    }
    with open(out_path, "w") as fh:
        json.dump(payload, fh)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--streams", "-n", type=int, default=5)
    ap.add_argument("--config", "-c", default="finger")
    ap.add_argument("--video", "-v", default=None, help="video file shared by all streams")
    ap.add_argument("--camera-base", type=int, default=None,
                    help="first camera id; stream i uses base + i")
    ap.add_argument("--frames", type=int, default=0, help="stop after N frames (0 = until EOF)")
    ap.add_argument("--seconds", type=float, default=10.0, help="max wall time per stream")
    ap.add_argument("--threads", type=int, default=2, help="cv2.setNumThreads per stream")
    ap.add_argument("--depth", type=int, default=2, help="queue depth between stages")
    ap.add_argument("--contact", action="store_true", help="also run compute_contact")
    ap.add_argument("--no-arrays", action="store_true",
                    help="scalars only (fastest; skips the snapshot image copy)")
    ap.add_argument("--out-dir", default=None)
    ap.add_argument("--record", default=None, metavar="DIR",
                    help="write one arrow-overlay mp4 per stream into DIR "
                         "(drawing+encoding run on a separate thread, off the "
                         "pipeline's critical path)")
    ap.add_argument("--record-fps", type=float, default=30.0,
                    help="playback fps of the recorded files")
    ap.add_argument("--record-every", type=int, default=1,
                    help="keep one frame in N (raise it if the writer falls behind)")
    ap.add_argument("--record-fourcc", default="mp4v",
                    help="mp4v (built in) or MJPG/avi for maximum compatibility")
    ap.add_argument("--record-grid", type=int, default=14, help="arrow grid spacing in px")
    ap.add_argument("--record-threshold", type=float, default=0.1,
                    help="displacement (px) below which a dot is drawn instead of an arrow")
    ap.add_argument("--record-arrow-scale", type=float, default=0.15,
                    help="draw_arrows divides the displacement by this; 0.15 magnifies "
                         "the finger's ~1-3 px field ~6.7x so directions are legible")
    ap.add_argument("--mosaic", action="store_true",
                    help="after the run, tile the recordings into one grid video")
    ap.add_argument("--mosaic-cols", type=int, default=0, help="mosaic columns (0 = square-ish)")
    ap.add_argument("--mosaic-scale", type=float, default=1.0, help="mosaic downscale factor")
    args = ap.parse_args()

    if args.record and args.no_arrays:
        ap.error("--record needs the frame and flow arrays; drop --no-arrays")
    if args.mosaic and not args.record:
        ap.error("--mosaic needs --record DIR")

    if args.record:
        args.record = os.path.abspath(args.record)
        os.makedirs(args.record, exist_ok=True)

    out_dir = args.out_dir or os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                           "..", "outputs", "multi_stream")
    out_dir = os.path.abspath(out_dir)
    os.makedirs(out_dir, exist_ok=True)

    ctx = mp.get_context("spawn")
    procs, paths = [], []
    for i in range(args.streams):
        path = os.path.join(out_dir, f"stream_{i}.json")
        paths.append(path)
        procs.append(ctx.Process(target=worker, args=(args, i, path)))
    for p in procs:
        p.start()
    for p in procs:
        p.join()

    rows = []
    for path in paths:
        try:
            with open(path) as fh:
                rows.append(json.load(fh))
        except Exception:
            pass
    if not rows:
        print("no stream produced results", file=sys.stderr)
        return 1

    wall = max(r["wall"] for r in rows)
    total = sum(r["published"] for r in rows)
    steady_rows = [r for r in rows if r.get("steady_fps")]
    steady = st.mean(r["steady_fps"] for r in steady_rows) if steady_rows else 0.0
    print(f"\nstreams={len(rows)}  frames={total}  wall={wall:.2f}s")
    print(f"aggregate throughput     : {total / wall:.1f} FPS (incl. warm-up)")
    print(f"per-stream throughput    : {total / wall / len(rows):.1f} FPS (incl. warm-up)")
    print(f"per-stream steady-state  : {steady:.1f} FPS")
    recording = args.record is not None
    print(f"\n{'stream':>7}{'published':>11}{'FPS':>9}{'steady':>9}{'produce':>10}"
          f"{'flow':>9}{'hhd':>9}{'age':>9}{'age p95':>10}"
          + (f"{'rec':>13}" if recording else ""))
    for r in sorted(rows, key=lambda x: x["index"]):
        s = r["stats"]
        rec = ""
        if recording:
            rs = r.get("record") or {}
            rec = f"{rs.get('written', 0)}/{rs.get('dropped', 0)}"
            if rs.get("error"):
                rec = "ERR"
        print(f"{r['index']:>7}{r['published']:>11}{r['fps']:>9.1f}"
              f"{r.get('steady_fps', 0.0):>9.1f}"
              f"{s['produce_ms']:>10.2f}{s['flow_ms']:>9.2f}{s['hhd_ms']:>9.2f}"
              f"{s['age_ms']:>9.2f}{r['age_p95_ms']:>10.2f}"
              + (f"{rec:>13}" if recording else ""))
    if recording:
        print("rec column = frames written / frames dropped by the writer thread")
        for r in sorted(rows, key=lambda x: x["index"]):
            rs = r.get("record") or {}
            if rs.get("error"):
                print(f"  stream {r['index']}: {rs['error']}")

    if args.mosaic and recording:
        streams = sorted(r["index"] for r in rows)
        srcs = [os.path.join(args.record, f"stream_{i}.mp4") for i in streams]
        missing = [p for p in srcs if not os.path.isfile(p)]
        if missing:
            print(f"mosaic skipped, missing {missing}", file=sys.stderr)
        else:
            out = os.path.join(args.record, "mosaic.mp4")
            # No tile labels: each recorded frame already carries the "#N" HUD.
            info = orisys.mosaic_videos(srcs, out, cols=args.mosaic_cols or None,
                                        scale=args.mosaic_scale,
                                        fps=args.record_fps)
            print(f"\nmosaic -> {info['path']}  {info['size'][0]}x{info['size'][1]}  "
                  f"{info['grid'][0]}x{info['grid'][1]} grid  {info['frames']} frames "
                  f"@ {info['fps']:g} fps")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
