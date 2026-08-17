# Orisys SDK

本仓库面向 **GitHub Release** 用户，提供 **已编译** 的 Orisys SDK 安装说明。  

Orisys SDK 用于光学触觉传感：图像采集、预处理、稠密光流、力估计、接触与深度估计，并附带示例与文档。

> 源码开发、重新编译、问题定位请使用主 SDK 仓库或联系官方支持。本仓库不包含可用于二次编译的完整源码构建流程。

---

## 支持矩阵

| 项目 | 当前状态 |
|------|----------|
| Windows x64 (`win_amd64`) | 已发布 |
| Ubuntu 22.04 x64 或以上  (`linux_x86_64`) | 已发布 |
| CPython 3.10 / 3.11 / 3.12 | 已发布 |
| Jetson / ARM / aarch64 | **计划中**，当前请勿下载或安装不存在的 ARM wheel |

请务必选择与本机 **操作系统、CPU 架构、Python 小版本** 三者都匹配的 wheel。

---

## 如何选择正确的 `.whl`

文件名通常为：

```text
orisys-<version>-cp<py>-cp<py>-<platform>.whl
```

示例（请以 [Releases](../../releases) 中的**实际文件名**为准，不要照抄虚构版本）：

| 平台 | 文件名形态 |
|------|------------|
| Windows + Python 3.10 | `orisys-<version>-cp310-cp310-win_amd64.whl` |
| Windows + Python 3.11 | `orisys-<version>-cp311-cp311-win_amd64.whl` |
| Linux x64 + Python 3.10 | `orisys-<version>-cp310-cp310-manylinux..._x86_64.whl` |

标签说明：

- `cp310` / `cp311` / `cp312`：必须与 `python --version` 一致（不能混用）
- `win_amd64`：64 位 Windows
- `linux_x86_64`：64 位 Ubuntu

在命令行可快速核对当前环境：

```bash
python -c "import sys, platform; print(sys.version); print(platform.platform()); print(platform.machine())"
```

---

## 安装步骤

### 1. 创建虚拟环境（推荐 Anaconda / Miniconda）

```bash
conda create -n orisys python=3.10
conda activate orisys
```

也可使用 Python 3.11 或 3.12，但必须下载对应 `cp311` / `cp312` 的 wheel。

建议先升级 pip：

```bash
python -m pip install -U pip
```

### 2. 从 GitHub Release 下载 wheel

1. 打开本仓库的 **Releases** 页面
2. 选择目标版本
3. 下载与当前系统匹配的 `.whl` 文件

### 3. 安装本地 wheel

将终端切换到 wheel 所在目录后执行（文件名请替换为实际下载名）：

```bash
python -m pip install ./orisys-<version>-cp310-cp310-win_amd64.whl
```

Linux 示例：

```bash
python -m pip install ./orisys-<version>-cp310-cp310-manylinux2014_x86_64.whl
```

运行时依赖（NumPy、OpenCV、SciPy、Numba）会由 pip 自动安装。

### 4. （可选）安装 CuPy 做 GPU 加速

若无有 NVIDIA GPU 且已安装 CUDA，可按 CUDA 主版本安装 CuPy：

```bash
# CUDA 12.x
python -m pip install "cupy-cuda12x>=12.3.0"

# CUDA 13.x
python -m pip install "cupy-cuda13x>=13.0.0"
```

无 GPU / 仅 CPU 运行可跳过。  
说明：本地路径安装的 wheel 不宜依赖 `pip install orisys[cuda12]` 这种“按 PyPI 包名解析 extras”的写法；请采用「先装本地 wheel，再单独装 CuPy」。

### 5. 验证安装

```bash
python -c "import orisys; print(orisys.__version__)"
```

能打印版本号即表示安装成功。

### 6. （可选）GUI 依赖

若要运行ORY-FINGER 3D Qt 界面示例，额外安装：

```bash
python -m pip install "open3d>=0.17.0" "pyqt5>=5.15" "pyqtgraph>=0.13"
```

---

## 安装包说明

本 Release 提供的是已编译的 Orisys SDK wheel：

- Windows 版本包含 Nuitka 编译的 `.pyd` 二进制扩展
- Linux 版本包含对应的二进制扩展
- 安装时会自动处理 NumPy、OpenCV、SciPy、Numba 等运行时依赖
- 配置文件、示例程序和文档随 Release 提供，具体调用方式见下方产品章节

安装后可用包内配置：

```python
import orisys

print(orisys.__version__)
print(orisys.list_config())  # 列出可用配置名
```

更完整的 API 与上手说明见本仓库（或 Release 附带）的：

- [`docs/get_started.md`](docs/get_started.md)
- [`docs/api.md`](docs/api.md)

---

## 产品使用方法

配置参数可以使用 Release 提供的配置名称，也可以传入本地 JSON 文件路径。请根据实际产品选择对应配置，不要混用其他产品的配置。

推荐入口位于 examples/products/。旧路径 examples/basic_pipeline.py、examples/finger_pipeline*.py 仍可作为兼容入口。

### ORY-BOX

ORY-BOX 使用复眼 / 拼接传感器流程，推荐使用 `ddjx01` 系列配置。

```bash
python examples/products/ory_box/basic_pipeline.py -v 0 -c ddjx01
```

无相机索引时，请先确认本机摄像头编号：

- Windows（PowerShell）：`Get-PnpDevice -PresentOnly | Where-Object { $_.Class -match '^Camera' }`
- Linux：`v4l2-ctl --list-devices`

### ORY-MINI

ORY-MINI 使用 MINI 专用配置和基础传感器流程：

```bash
python examples/products/ory_mini/basic_pipeline.py -v 0 -c mini
```

如果需要更快的 MINI 配置，可以使用：

```bash
python examples/products/ory_mini/basic_pipeline.py -v 0 -c mini-fast
```

### ORY-FINGER

当前版本的 ORY-FINGER 配置名称为 `dd02`。`dd02` 是当前版本的兼容配置名称；后续版本更换产品名称后，仍会在兼容期内支持 `dd02`，新的配置名称以对应 Release 说明为准。

#### ORY-FINGER 2D 流程

```bash
python examples/products/ory_finger/finger_pipeline.py --camera_id 0 --config dd02
```

也可以使用视频文件：

```bash
python examples/products/ory_finger/finger_pipeline.py --video ./data/sample.mp4 --config dd02
```

#### ORY-FINGER 3D Qt 界面

安装 GUI 依赖后运行：

```bash
python -m pip install "open3d>=0.17.0" "pyqt5>=5.15" "pyqtgraph>=0.13"
python examples/products/ory_finger/finger_pipeline_3dview.py --video 0 --config dd02
```

---

## 升级 / 卸载

```bash
python -m pip uninstall -y orisys
python -m pip install ./orisys-<version>-cp<py>-cp<py>-<platform>.whl
```

建议先卸载再安装，避免旧二进制扩展残留。

---

## 常见问题

### 1. `is not a supported wheel on this platform` / 导入失败

原因几乎总是 **Python 版本或平台标签不匹配**。请重新核对：

- `python --version` 是否对应 `cp310` / `cp311` / `cp312`
- 是否在 64 位系统上安装了 `win_amd64` / `x86_64` wheel
- 是否误用了其他机器编译的 wheel

### 2. 找不到相机 / 打不开视频源

- 确认 USB 已连接，且无其他程序占用相机
- Windows / Linux 用上文命令确认设备编号
- 某些环境需要管理员权限或用户组权限（Linux 常见为 `video` 组）

### 3. Linux 上 OpenCV / GUI 相关报错

可能缺少系统图形或相机相关运行库。请按发行版安装 OpenCV / Qt / OpenGL 相关依赖后再试。

---

## 支持与反馈

- 版本与附件：以 GitHub **Releases** 页面为准
- 商业支持 / 定制需求：联系 Orisys-Tech 官方渠道
