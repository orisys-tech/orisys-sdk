# Orisys SDK

Orisys SDK 用于叠动科技视触觉传感器。

```bash
python -m pip install orisys
```

需要 Python 3.10 / 3.11 / 3.12（Windows x64 与 Ubuntu 22.04 x64）。环境创建见 [`docs/get_started.md`](docs/get_started.md)。

---

## 快速启动

```bash
python -c "import orisys; print(orisys.__version__)"
python examples/basic_pipeline.py -v 0 -c box
```

无相机时，请先确认本机摄像头编号：

- Windows（PowerShell）：`Get-PnpDevice -PresentOnly | Where-Object { $_.Class -match '^Camera' }`
- Linux：`v4l2-ctl --list-devices`

---

## 安装选项

- `orisys` — CPU / 基础流程
- `orisys[gui]` — Qt / Open3D 示例
- `orisys[cuda12]` / `orisys[cuda13]` — NVIDIA GPU 加速
- `orisys[gui,cuda12]` — GUI + CUDA 12

`orisys[cuda]` 与 `orisys[cuda12]` 等价。离线安装和 wheel 选择见 [`docs/get_started.md`](docs/get_started.md)。

---

## 示例

请在仓库根目录运行。配置名可用包内名称（`box`、`finger`），也可传入本地 JSON 路径。

ORY-BOX：

```bash
python examples/basic_pipeline.py -v 0 -c box
```

ORY-FINGER 2D：

```bash
python examples/finger_pipeline.py --camera_id 0 --config finger
```

ORY-FINGER 3D（需 `orisys[gui]`）：

```bash
python examples/finger_pipeline_3dview.py --video 0 --config finger
```

更多说明：

- [`docs/get_started.md`](docs/get_started.md)
- [`docs/api.md`](docs/api.md)
- [`examples/README.md`](examples/README.md)

```python
import orisys

print(orisys.__version__)
print(orisys.list_config())
```

---

## 支持与反馈

- 官网：[https://www.orisys-tech.cn](https://www.orisys-tech.cn)
- PyPI：[https://pypi.org/project/orisys/](https://pypi.org/project/orisys/)
- 版本与附件：以本仓库 [Releases](../../releases) 为准
- 问题反馈：GitHub Issues
