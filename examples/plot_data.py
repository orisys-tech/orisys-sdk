"""
示例 3：实时曲线与幅值图显示

本示例演示如何在读取传感器结果的同时：
1. 显示形变矢量场
2. 显示流场幅值热力图
3. 使用 PyQtGraph 实时绘制法向力与切向力曲线
4. 按键控制录像开始与结束
"""

import argparse
import os
import sys
import time
from pathlib import Path

os.environ["OPENCV_VIDEOIO_MSMF_ENABLE_HW_TRANSFORMS"] = "0"

import cv2
import orisys

_EXAMPLES_DIR = Path(__file__).resolve().parent
if str(_EXAMPLES_DIR) not in sys.path:
    sys.path.insert(0, str(_EXAMPLES_DIR))

from viz import ForceChartWindow, FrameRecorder, draw_magnitude_map, lowpass_filter


def open_sensor(video: str, config: str, cal: str, verbose: bool):
    try:
        source = int(video)
    except ValueError:
        source = video
    return orisys.Sensor(source, config_name=config, cal_path=cal, verbose=verbose)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--video", "-v", type=str, default="0", help="视频源：摄像头编号或视频文件路径")
    parser.add_argument("--config", "-c", type=str, default="./config/ddjx01.json", help="配置文件名称或路径")
    parser.add_argument("--cal", "-cal", type=str, default="./config/ddjx01.npy", help="标定文件路径")
    parser.add_argument("--verbose", "-verbose", type=bool, default=True, help="是否输出详细日志")
    args = parser.parse_args()

    charts = ForceChartWindow()
    recorder = FrameRecorder()
    sensor = open_sensor(args.video, args.config, args.cal, args.verbose)
    start_time = time.time()

    print("\n按键说明：'q' 退出程序，'s' 开始录像，'e' 结束录像。")
    try:
        while True:
            sensor.get_img()
            recorder.write_if_recording(sensor.frame)

            sensor.compute_deformation(check_motion=True, threshold=0)
            fps, fn, fx, fy, flow, vnormal, vshear = sensor.read_info(
                sensor.info.FPS,
                sensor.info.FNORMAL,
                sensor.info.FSHEARX,
                sensor.info.FSHEARY,
                sensor.info.VRAW,
                sensor.info.VNORMAL,
                sensor.info.VSHEAR,
            )
            print(f"FPS={fps:.2f}, 法向力={fn:.4f}, 切向力X={fx:.4f}, 切向力Y={fy:.4f}")

            arrows = orisys.util.draw_arrows(sensor.img, flow, threshold=5, grid_spacing=10, arrow_scale=1.0)
            cv2.imshow("形变矢量场", arrows)
            cv2.imshow("流场幅值图", draw_magnitude_map(flow))

            charts.push(time.time() - start_time, fn, fx, fy)
            display = charts.data.copy()
            for channel in range(3):
                display[:, 1, channel] = lowpass_filter(
                    charts.data[:, 1, channel],
                    cutoff_hz=5,
                    sample_rate_hz=30,
                )
            charts.refresh(display)

            key = cv2.waitKey(1)
            if key & 0xFF == ord("q"):
                print("\n正在退出示例程序...")
                break
            if key == ord("s"):
                recorder.start(sensor.frame)
            if key == ord("e"):
                recorder.stop()
    finally:
        sensor.disconnect()


if __name__ == "__main__":
    main()
