# Examples

Top-level demo scripts under `examples/`. Run them from the repository root.

## Top-Level Files

- `README.md` — this overview of the root-level example entry points
- `basic_pipeline.py` — basic single-sensor OpenCV demo for the compound-eye pipeline
- `plot_data.py` — single-sensor demo with OpenCV views plus PyQtGraph force charts
- `two_sensor_pipeline.py` — two-sensor multiprocessing demo for parallel acquisition / display
- `finger_pipeline.py` — minimal finger UV-unroll pipeline with optional profiling
- `finger_pipeline_3dview.py` — main finger dashboard entry point with the unified Qt UI

## Typical Usage

For the Qt dashboard:

```bash
pip install -e ".[gui]"
python examples/finger_pipeline_3dview.py --video 0 --config ./config/dd02-ov.json
```

For the minimal finger pipeline:

```bash
python examples/finger_pipeline.py --camera_id 0 --config ./config/dd02-ov.json
```

For the minimal finger pipeline with profiling:

```bash
python examples/finger_pipeline.py --camera_id 0 --config ./config/dd02-ov.json --profile --profile-every 30
```

For a video-file finger run:

```bash
python examples/finger_pipeline.py --video ./data/sample.mp4 --config ./config/dd02-ov.json
```

For the basic compound-eye pipeline:

```bash
python examples/basic_pipeline.py -v 0 -c ./config/ddjx01.json
```

## Requirements

- SDK installed from the repository root, for example `pip install -e .`
- camera index or test video path
- matching config files under `./config/`

Qt / PyQtGraph examples additionally require:

```bash
pip install -e ".[gui]"
```

## Notes

- `finger_pipeline_3dview.py` is the main interactive demo. It uses `gui/app_paths.py` so the same entry point works in editable and packaged runs.
- Dashboard controls: click **启动** to start acquisition; use **Record CSV / Stop CSV** and the CSV save-directory browser to log contact/force data; `Q` quits, `R` resets, `S` starts video recording, `E` stops video recording, and `Esc` toggles fullscreen.
- `finger_pipeline.py` is the leanest finger example if you want to validate UV unroll + force/contact processing without the full dashboard.
- `finger_pipeline.py` uses `orisys.finger.FingerRuntime` as the high-level entry point, then runs tactile analysis through `runtime.tactile`.
- In `--profile` mode, the example splits the loop into capture, UV unroll, deformation, contact, and display stages so you can measure each step separately.
