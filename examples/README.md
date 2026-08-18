# Examples

Runnable demos live at the `examples/` root. Shared helpers stay in
`pipeline/`, `viz/`, and `gui/`. Run commands from the repository root.

## Product Entry Points

| Product | Entry | Default config |
|---------|-------|----------------|
| ORY-BOX | `basic_pipeline.py` | `box` |
| ORY-MINI | `mini_pipeline.py` | `mini` |
| ORY-FINGER (2D) | `finger_pipeline.py` | `finger` |
| ORY-FINGER (3D Qt) | `finger_pipeline_3dview.py` | `finger` |

`finger` is the public ORY-FINGER config stem. `dd02` remains a compatibility alias for `dd02-ov`.

## Typical Usage

ORY-BOX:

```bash
python examples/basic_pipeline.py -v 0 -c box
```

ORY-MINI:

```bash
python examples/mini_pipeline.py -v 0 -c mini
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
pip install -e ".[gui]"
python examples/finger_pipeline_3dview.py --video 0 --config finger
```

## Other Root Examples

- `plot_data.py` — single-sensor OpenCV views plus PyQtGraph force charts
- `two_sensor_pipeline.py` — two-sensor multiprocessing demo

## Requirements

- SDK installed from the repository root, for example `pip install -e .`
- camera index or test video path
- matching config names under `./config/` (or packaged `orisys/configs/`)

Qt / PyQtGraph examples additionally require:

```bash
pip install -e ".[gui]"
```

## Notes

- `finger_pipeline_3dview.py` is the main interactive finger demo.
  It uses `gui/app_paths.py` so the same entry works in editable and packaged runs.
- Dashboard controls: click **启动** to start acquisition; use **Record CSV / Stop CSV**
  and the CSV save-directory browser to log contact/force data; `Q` quits, `R` resets,
  `S` starts video recording, `E` stops video recording, and `Esc` toggles fullscreen.
- `finger_pipeline.py` is the leanest finger example if you want to
  validate UV unroll + force/contact processing without the full dashboard.
