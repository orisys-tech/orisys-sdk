#!/usr/bin/env python3
"""
Minimum UV-unroll finger tactile pipeline.

Offline: load Blender export -> build_or_load_domain -> unroll_map_uv.npz
Runtime:  camera frame -> FrameUnwarper -> TactileProcessor -> forces/contact

For the full demo (UV debug panels, dashboard, benchmarks) see:
  tools/3d_patch_generation_blender/unroll_realtime.py
"""

import argparse
import os
import sys

os.environ.setdefault("OPENCV_VIDEOIO_MSMF_ENABLE_HW_TRANSFORMS", "0")

import cv2
import orisys
from orisys.finger import FingerRuntime


def main():
    parser = argparse.ArgumentParser(description="Minimum UV-unroll finger tactile pipeline")
    parser.add_argument("--camera_id", type=int, default=0)
    parser.add_argument("--video", help="Video file path (overrides camera)")
    parser.add_argument("--config", "-c", default="finger", help="Orisys SDK config")
    parser.add_argument("--show", action="store_true", default=True, help="Show unrolled image window")
    parser.add_argument("--verbose", action="store_true", help="SDK verbose logs")
    args = parser.parse_args()

    try:
        video = args.camera_id
        if args.video:
            video = args.video
        runtime = FingerRuntime.open(
            config=args.config,
            video=video,
            verbose=args.verbose,
        )
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)

    if args.verbose:
        geometry = runtime.geometry
        print(
            f"UV geometry: native={geometry.native_width}x{geometry.native_height}, "
            f"source={geometry.source_width}x{geometry.source_height} "
            f"output={geometry.out_width}x{geometry.out_height} "
        )

    runtime.warmup(color=False)
    tactile = runtime.tactile

    print("Press 'q' to quit, 'r' to reset tracker.")
    try:
        while True:
            ok, unrolled = runtime.grab_and_process(color=False)
            if not ok:
                break

            tactile.compute_deformation(check_motion=True, threshold=0)
            tactile.compute_contact()

            fps, flow, vnormal, img, contour, centroid, depth_map, fnormal, fshearx, fsheary = tactile.read_info(
                tactile.info.FPS,
                tactile.info.VRAW,
                tactile.info.VNORMAL,
                tactile.info.IMG,
                tactile.info.CONTOUR,
                tactile.info.CENTROID,
                tactile.info.DEPTH,
                tactile.info.FNORMAL,
                tactile.info.FSHEARX,
                tactile.info.FSHEARY,
            )

            status = (
                f"FPS={fps:.2f} normal={fnormal:.2f} shear=({fshearx:.2f}, {fsheary:.2f}) "
                f"mask={tactile.mask_stats['coverage']:.2f}"
            )

            if args.show:
                arrows = orisys.util.draw_arrows(
                    unrolled,
                    flow,
                    threshold=0.4,
                    grid_spacing=10,
                    arrow_scale=1.0,
                )
                cv2.imshow("UV Unrolled", arrows)

            print(status, end="\r")

            key = cv2.waitKey(1) & 0xFF
            if key == ord("q"):
                print("\nExiting.")
                break
            if key == ord("r"):
                tactile.reset()
                print("\nTracker reset.")
    finally:
        runtime.close()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
