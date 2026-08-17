# Examples

Top-level demo scripts under `examples/`. Run them from the repository root.

## Top-Level Files

- `README.md` — this overview of the root-level example entry points
- `basic_pipeline.py` — basic single-sensor OpenCV demo for ORY-BOX
- `plot_data.py` — single-sensor demo with OpenCV views plus PyQtGraph force charts
- `two_sensor_pipeline.py` — two-sensor multiprocessing demo for parallel acquisition / display
- `finger_pipeline.py` — minimal ORY-FINGER UV-unroll pipeline
- `finger_pipeline_3dview.py` — ORY-FINGER dashboard with the unified Qt UI

## Typical Usage

ORY-BOX:

```bash
python examples/basic_pipeline.py -v 0 -c box
```

ORY-FINGER 2D:

```bash
python examples/finger_pipeline.py --camera_id 0 --config finger
```

ORY-FINGER video file:

```bash
python examples/finger_pipeline.py --video ./data/sample.mp4 --config finger
```

ORY-FINGER 3D Qt dashboard:

```bash
python -m pip install "orisys[gui]"
python examples/finger_pipeline_3dview.py --video 0 --config finger
```

## Requirements

- SDK installed, for example `python -m pip install orisys`
- camera index or test video path
- packaged config names (`box`, `finger`) or a local JSON path

Qt / Open3D examples additionally require `orisys[gui]`.

## Notes

- `finger_pipeline_3dview.py` is the main interactive demo. It uses `gui/app_paths.py` so the same entry point works in editable and packaged runs.
- Dashboard controls: click **启动** to start acquisition; use **Record CSV / Stop CSV** and the CSV save-directory browser to log contact/force data; `Q` quits, `R` resets, `S` starts video recording, `E` stops video recording, and `Esc` toggles fullscreen.
- `finger_pipeline.py` is the leanest finger example if you want to validate UV unroll + force/contact processing without the full dashboard.
