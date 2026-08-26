"""
ORY-BOX：单传感器基础流程

本示例演示 Orisys SDK 的标准处理流程：
1. 初始化传感器（摄像头或视频文件）
2. 获取图像并计算形变
3. 按需计算接触区域
4. 读取并可视化结果

SDK version: 0.4.4
"""
import os
os.environ["OPENCV_VIDEOIO_MSMF_ENABLE_HW_TRANSFORMS"] = "0" 
import cv2
import orisys
import numpy as np
import argparse

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--video","-v", type=str, default="0", help="视频源：摄像头编号或视频文件路径")
    parser.add_argument("--config","-c", type=str, default="box", help="配置文件名称或路径")
    parser.add_argument("--verbose","-verbose", type=bool, default=True, help="是否输出详细日志")
    args = parser.parse_args()

    # 步骤 1：创建传感器对象（必需）
    # config_name 可以是内置配置名称，也可以是自定义配置文件路径
    # cal_path 为标定文件路径；每台设备建议使用独立的标定文件

    # 输入既可以是摄像头编号，也可以是视频文件路径
    try:
        input = int(args.video)
        is_camera = True
        sensor = orisys.Sensor(input, config_name=args.config, verbose=args.verbose)
    except:
        is_camera = False
        sensor = orisys.Sensor(args.video, config_name=args.config, verbose=args.verbose)

    print("\n按键说明：'q' 退出程序，'r' 重置追踪器。")

    while True:
        # 步骤 2：数据处理
        # 步骤 2.1：获取并拼接图像（必需）
        sensor.get_img() 
        # 步骤 2.2：计算形变场（必需）；返回值表示当前帧是否检测到接触/运动
        is_contact_now = sensor.compute_deformation()
        # 步骤 2.3：仅在当前帧检测到接触/运动时计算接触区域
        # if is_contact_now:
        sensor.compute_contact()

    
        # 步骤 2.4：读取结果（FNORMAL/FSHEAR* 在有 sensors/box/force_calibration.json 时为标定后牛顿力；
        # *_RAW 始终为原始积分量）
        (
            fps,
            flow,
            vnormal,
            img,
            contour,
            centroid,
            depth_map,
            fnormal,
            fshearx,
            fsheary,
            fnormal_raw,
            fshearx_raw,
            fsheary_raw,
        ) = sensor.read_info(
            sensor.info.FPS,
            sensor.info.VRAW,
            sensor.info.VNORMAL,
            sensor.info.IMG,
            sensor.info.CONTOUR,
            sensor.info.CENTROID,
            sensor.info.DEPTH,
            sensor.info.FNORMAL,
            sensor.info.FSHEARX,
            sensor.info.FSHEARY,
            sensor.info.FNORMAL_RAW,
            sensor.info.FSHEARX_RAW,
            sensor.info.FSHEARY_RAW,
        )
        
        # 步骤 3：可视化显示
        # 步骤 3.1：显示形变矢量场
        arrows = orisys.util.draw_arrows(
            img,
            flow,
            threshold=2,
            grid_spacing=20,
            arrow_scale=1.0
        )
        cv2.imshow("arrow", arrows)
        
        # 步骤 3.2：显示接触区域和质心
        image_with_foe = orisys.util.draw_contact(img, contour, centroid)
        cv2.imshow("contact", image_with_foe)

        # 步骤 3.3：显示深度图
        # 将深度值归一化到 0-255 范围
        div_abs = depth_map
        if div_abs.max() > div_abs.min():
            div_normalized = ((div_abs - div_abs.min()) / (div_abs.max() - div_abs.min()) * 255).astype(np.uint8)
        else:
            div_normalized = np.zeros_like(div_abs, dtype=np.uint8)
        
        # 应用伪彩色映射
        cv2.imshow("depth", cv2.applyColorMap(div_normalized, cv2.COLORMAP_JET))

        # 步骤 3.4：打印关键结果（标定力 + 原始力）
        print(
            f"FPS={fps:.2f}, "
            f"法向力={fnormal:.4f} N (raw={fnormal_raw:.4f}), "
            f"切向力X={fshearx:.4f} N (raw={fshearx_raw:.4f}), "
            f"切向力Y={fsheary:.4f} N (raw={fsheary_raw:.4f}), "
            f"深度图尺寸={depth_map.shape}, 原始分辨率={sensor.img_size_raw}"
        )
            
        # 步骤 3.5：键盘控制
        key = cv2.waitKey(1) & 0xFF
        if key == ord("q"):
            print("\n正在退出示例程序...")
            break
        if key == ord("r"):
            # 当光流追踪出现漂移时，可手动重置追踪器
            sensor.reset()
            print("追踪器已重置。")
        
    # =========================================================================
    # 4. 释放资源
    # =========================================================================
    sensor.disconnect()  # 释放视频源及相关资源


if __name__ == '__main__':
    main()
