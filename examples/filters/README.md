# 滤波预设：可直接复制的 `filters` 段

`json.load` 不支持注释，所以这个目录就是"在配置里写说明"的替代品：**把下面任意一段整块替换**
到 `sensors/<name>/sensor.json` 的 `"filters"` 段即可。原有的 `filters` 段请整段替换，
不要只改其中一行（避免出现 `preset` 与数值混写的歧义——显式键优先于预设值，混写容易看错）。

配置里**没写**的滤波键等于"关"：整段删掉就是什么都不滤，和 `off` 那段等价。

背景、代价与可追溯性约定见 `docs/filters.md`；延迟/噪声实测见 `_perf/` 与
`orisys-sdk-perf-plan.md`。

下面每一段都有一个同目录的机器可读副本 `filters_<预设名>.json`（四个文件），
`tests/test_filter_presets.py` 会核对它们与 `FILTER_PRESETS` 完全一致 —— 所以改预设时
这些文件会一起红，不会悄悄过时。

---

## `off` —— 原始读数（默认）

```json
"filters": {
  "flow_ema_alpha": 1.0,
  "force_median_window": 1,
  "force_lowpass_cutoff_hz": 0.0,
  "force_lowpass_order": 2,
  "force_lowpass_sample_rate_hz": "auto"
}
```

## `low_latency` —— 只去尖峰（≈1 帧 @30fps）

```json
"filters": {
  "flow_ema_alpha": 1.0,
  "force_median_window": 3,
  "force_lowpass_cutoff_hz": 0.0,
  "force_lowpass_order": 2,
  "force_lowpass_sample_rate_hz": "auto"
}
```

## `balanced` —— 建议默认（≈2 帧 @30fps）

```json
"filters": {
  "flow_ema_alpha": 0.5,
  "force_median_window": 3,
  "force_lowpass_cutoff_hz": 0.0,
  "force_lowpass_order": 2,
  "force_lowpass_sample_rate_hz": "auto"
}
```

## `low_noise` —— 底噪优先（≈3 帧 @30fps）

```json
"filters": {
  "flow_ema_alpha": 0.3,
  "force_median_window": 3,
  "force_lowpass_cutoff_hz": 10.0,
  "force_lowpass_order": 2,
  "force_lowpass_sample_rate_hz": "auto"
}
```

## 用预设名（等价写法，数值由代码展开）

```json
"filters": { "preset": "balanced" }
```

`off / low_latency / balanced / low_noise` 四个名字来自
`src/orisys/sensor.py::FILTER_PRESETS`（单一真值）；想从预设出发只改一个旋钮，就在同一段里写
那一个键，例如：

```json
"filters": { "preset": "balanced", "force_lowpass_cutoff_hz": 10.0 }
```

---

## 复制后请核对"实际生效值"

配置只是**意图**；`Sensor.configure()` 可以在运行时再改，所以审计与记录一律看生效值：

```python
from orisys.sensor import Sensor
s = Sensor("external", config_name="mini", verbose=False)   # 无需硬件即可核对
print(s.filters_state()["preset"], s.filters_state()["measurement"], s.filters_state()["readout"])
```

`flow_ema_applied` / `force_median_applied` / `force_lowpass_applied` 三个布尔就是
"这一级到底有没有在滤"的答案；`flow_ema_alpha` 属于 **measurement**（改变测量，
不同值的两次录制不可比），中值与低通属于 **readout**（只影响读数呈现）。

导出标定/写记录时把同一个状态交给指纹函数，文件里就会留下可核对的设置：

```python
from orisys.calibration import pipeline_from_sensor_json
pipeline = pipeline_from_sensor_json("sensors/mini/sensor.json", filters_state=s.filters_state())
print(pipeline["filters"])   # measurement / readout / preset / source
```

详见 `docs/filters.md` 第 7 节。
