---
title: 快速开始
description: 安装并运行 Orisys SDK 的基础步骤
---

# 快速开始

版本：0.4.4

## 简介
本文件介绍如何上手和运行叠动视触觉传感器配套的开发套件。本套件是配合叠动视触觉传感器进行图像处理，计算形变、力以及接触信息。它可以从摄像头或视频文件中读取图像，处理后打印和展示处理后信息。  
支持操作系统：Windows、Ubuntu  
建议Python 版本: 3.10, 3.11, 3.12

项目链接：

- PyPI 安装页：[https://pypi.org/project/orisys/](https://pypi.org/project/orisys/)
- 项目文档/代码：[https://github.com/Orisys-Tech/orisys-sdk](https://github.com/Orisys-Tech/orisys-sdk)

## 基础环境设置
### 安装 Python 与 Anaconda
1.	访问 [Anaconda 官网](https://www.anaconda.com/download) 下载适合您操作系统的安装包（Windows、Linux）。
2.	按照提示完成安装。
3.	安装完成后，打开命令行终端（Windows 用户可在 “Anaconda Navigator” 打开 “Anaconda Prompt”），输入 `conda info`，若能显示 conda 的信息，则说明安装成功。

### 创建 conda 虚拟环境
虚拟环境相当于一个独立的 Python 工作空间，可以避免不同项目所需的库版本冲突。
打开命令行终端（或 Anaconda Prompt），依次输入以下命令（以 Python 3.10 为例）：
```bash
conda create -n orisys python=3.10
conda activate orisys
```

激活后，命令行提示符前会出现 `(orisys)` 字样，表示当前已进入虚拟环境。

### 创建工作区文件夹
“Anaconda Prompt” 启动后的默认工作路径在用户根文件夹中，建议创建工作区文件夹方便管理。可以手动创建文件夹，也可以运行 `mkdir <path>` 命令。例如：

```bash
mkdir orisys_ws
```

创建后如果要更换工作区，使用 `cd <path>` 命令，例如：

```bash
cd "C:\Users\orisys\orisys_ws"
```
### 安装 CUDA 和 cuDNN（可选）
如果您拥有 NVIDIA 显卡，并希望利用 GPU 加速计算，则需要安装 CUDA 工具包和 cuDNN。

1. 方法一（官网下载）：
访问 [NVIDIA CUDA Toolkit 官网](https://developer.nvidia.com/cuda/toolkit) 下载对应系统的 CUDA Toolkit 安装包，并按照提示安装。注意 12.x 和 13.x 的版本对应不同的 CuPy 库版本。

2. 方法二（使用 Anaconda 安装，推荐）：
在已激活的 orisys 环境中直接运行以下命令（以 CUDA 12.9 为例）：

```bash
conda install nvidia/label/cuda-12.9.0::cuda-toolkit nvidia::cudnn
```

该方法会自动配置好 CUDA 和 cuDNN，无需手动下载。

注意：如果您的计算机没有 NVIDIA 显卡，或者不想使用 GPU 加速，可以跳过此步骤。套件也支持纯 CPU 运行（但速度可能较慢）。

## 安装 orisys SDK

推荐优先从 PyPI 安装。PyPI 会自动选择适合当前 Python 版本和操作系统的安装包，适合大多数用户。

### 使用 PyPI 安装（推荐）
确认已经激活 `orisys` 虚拟环境后，运行：

```bash
pip install orisys
```

如果需要升级到最新版本，运行：

```bash
pip install --upgrade orisys
```

如果当前网络无法访问 PyPI，或需要安装客服提供的指定版本，可以使用下方 `.whl` 文件安装方式。

### 使用 .whl 文件安装（离线或指定版本）
从官方渠道获取 .whl 文件，文件名格式通常为：
orisys-{版本}-{Python版本}-{Python版本}-{操作系统}_{硬件架构}.whl
例如：orisys-0.4.4-cp310-cp310-win_amd64.whl 表示：

版本：0.4.4
Python 版本：3.10（cp310）
操作系统：Windows（win）
硬件架构：64位（amd64）

请根据您的系统选择对应的文件，或者咨询客服索取。

将下载好的 `.whl` 文件放在一个文件夹中（如上述 `orisys_ws` 文件夹），打开命令行（确保已激活 `orisys` 环境或使用 “Anaconda Prompt”），使用 `cd` 命令切换到该文件夹，然后运行：

```bash
# 请将文件名替换为您实际下载的文件名
pip install orisys-0.4.4-cp310-cp310-win_amd64.whl
```

### 安装 CuPy（可选）
注意：如果您没有安装 CUDA，或者使用 CPU 运行，可以跳过这一步。

CuPy 是一个与 NumPy 类似但支持 GPU 加速的库，您需要根据您安装的 CUDA 版本选择对应的 CuPy 版本。

方法一（使用 extras 参数，推荐）：
在安装 orisys 时，可以直接指定 CUDA 版本，pip 会自动安装配套的 CuPy：

```bash
# 如果您的 CUDA 版本是 12.x
pip install "orisys[cuda12]"

# 如果您的 CUDA 版本是 13.x
pip install "orisys[cuda13]"
```
如果之前已经安装了 orisys，可以单独安装 CuPy：

方法二（手动安装）：

```bash
# CUDA 12.x
pip install "cupy-cuda12x>=12.3.0"

# CUDA 13.x
pip install "cupy-cuda13x>=13.0.0"
```

### 测试安装
安装完成后，在命令行输入 `python` 命令进入 Python 环境，并导入 `orisys` 库查看版本号，验证是否成功：
```bash
python
```

进入 Python 后继续输入：

```python
import orisys
print(orisys.__version__)
```
如果输出版本号（例如 0.4.4），则说明安装成功。

## 使用方法
### 运行示例程序
套件里面包含了多个例子。运行示例前，请先进入 SDK 示例所在的文件夹，建议在仓库根目录运行（即 `config/`、`examples/`、`assets/` 同级目录）。如果您是通过 PyPI 安装并且本地没有示例文件，可以从上方项目链接下载示例。按产品入口如下：

1. `examples/basic_pipeline.py`：ORY-BOX 复眼/拼接传感器基础 OpenCV 示例（默认配置 `box`）
2. `examples/mini_pipeline.py`：ORY-MINI 基础 OpenCV 示例（默认配置 `mini`）
3. `examples/finger_pipeline.py`：ORY-FINGER 2D 显示最小流程（默认配置 `finger`）
4. `examples/finger_pipeline_3dview.py`：ORY-FINGER Qt 3D 可视化界面（默认配置 `finger`）

`finger` 是当前 ORY-FINGER 的产品配置名。

下面先介绍最基础的 ORY-BOX 运行方式。

#### Windows
1.	检查是否有其他正在连接的 USB 摄像头设备：打开 PowerShell，运行命令 `Get-PnpDevice -PresentOnly | Where-Object { $_.Class -match '^Camera' }`，如果没有的话不会有输出。
2.	把传感器的 USB 头与电脑连接，再次运行步骤一的命令，会新增一行输出。
3.	如果第一步没有输出，传感器的 ID 就是 `0`；如果第一步有一个设备，传感器的 ID 就是 `1`，如此类推。
4.	在确定了传感器的 ID（下方例子假设为 `0`）后，打开 Anaconda Prompt，切换到工作路径，然后在命令行中输入：
    ```bash
    python examples/basic_pipeline.py -v 0 -c box
    ```
5.	程序会运行，并自动打开可视化窗口和打印资料。在窗口上按键盘 `q` 键可以停止运行，按 `r` 键可以重设数据。

#### Ubuntu
1.	检查是否有其他正在连接的 USB 摄像头设备：打开终端，运行命令 `v4l2 --list-devices`，如果没有的话不会有输出。
2.	把传感器的 USB 头与电脑连接，再次运行步骤一的命令，会新增输出。
3.	根据新增的输出，例如 `/dev/video0`，确定传感器的 ID 为 `0`；如果是 `/dev/video3`，ID 为 `3`，如此类推。
4.	在确定了传感器的 ID（下方例子假设为 `0`）后，打开终端，激活相应的 Python 环境，切换到工作路径，然后在命令行中输入：
    ```bash
    python examples/basic_pipeline.py -v 0 -c box
    ```
5.	程序会运行，并自动打开可视化窗口和打印资料。在窗口上按键盘 `q` 键可以停止运行，按 `r` 键可以重设数据。

#### ORY-FINGER 示例

如果您使用的是 ORY-FINGER（配置名 `finger`），可运行：

```bash
python examples/finger_pipeline.py --camera_id 0 --config finger
```

如果输入来自视频文件，也可以改用：

```bash
python examples/finger_pipeline.py --video ./data/sample.mp4 --config finger
```

该示例会：

- 读取相机或视频源
- 将图像展开到平面
- 计算光流、法向/切向力和接触区域
- 在 OpenCV 窗口中显示展开后的光流箭头图

常用参数：

- `--verbose`：输出更详细的初始化日志

例如：

```bash
python examples/finger_pipeline.py --camera_id 0 --config finger
```

#### ORY-FINGER 3D 可视化界面

如果要使用 GUI，先安装 GUI 依赖：
```bash
pip install "orisys[gui]"
```
然后运行：
```bash
python examples/finger_pipeline_3dview.py --video 0 --config finger
```

该界面会提供：

- 手指平面化光流箭头显示
- 力曲线
- 3D 视图

### 开发套件使用方法
参考开发套件附带的开发文档。