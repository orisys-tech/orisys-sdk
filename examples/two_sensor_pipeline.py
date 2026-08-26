"""
示例 2：双传感器并行处理（多进程）

本示例演示如何使用 multiprocessing 同时运行两个传感器：
- 每个传感器运行在独立进程中
- 每个进程拥有独立的 CUDA 上下文
- 通过 Process 和 Queue 在主进程中汇总结果并显示

架构说明：
    进程 1（传感器 0）：采集 → 光流 → HHD → 接触检测 → 队列
    进程 2（传感器 1）：采集 → 光流 → HHD → 接触检测 → 队列
                                              ↓
    主进程：              显示 ← ───────────────┘

适用场景：多指触觉传感器、多视角采集，以及需要 GPU 加速的多路处理。

注意事项：
- Windows 下必须在 if __name__ == '__main__' 中调用 mp.freeze_support()
- 每个传感器进程都会占用独立的 GPU 显存

SDK version: 0.4.4
"""
import os
os.environ["OPENCV_VIDEOIO_MSMF_ENABLE_HW_TRANSFORMS"] = "0" 
import cv2
import orisys
import numpy as np
import multiprocessing as mp
from multiprocessing import Queue, Process
import time
import argparse


def sensor_worker(sensor_id, vid_src, config_name, result_queue, stop_event, target_fps=None):
    """
    传感器工作进程。

    Args:
        sensor_id: 传感器编号
        vid_src: 视频源（文件路径或摄像头索引）
        config_name: 配置名称
        result_queue: 结果队列，用于向主进程发送数据
        stop_event: 停止事件，用于通知工作进程退出
        target_fps: 目标帧率；设置后将对处理循环限速，使多路传感器 FPS 更接近
    """
    try:
        # 在每个进程中创建独立的传感器实例
        sensor = orisys.Sensor(
            vid_src,
            isstitch=True,
            cuda=True,
            verbose=False,  # 减少子进程输出
            config_name=config_name
        )

        print(f"传感器 {sensor_id} 已启动" + (f"（目标帧率：{target_fps} FPS）" if target_fps else ""))

        frame_interval = 1.0 / target_fps if target_fps and target_fps > 0 else 0.0

        while not stop_event.is_set():
            t_start = time.perf_counter()
            try:
                # 步骤 1：获取图像
                sensor.get_img()

                # 步骤 2：计算形变场
                sensor.compute_deformation()

                # 步骤 3：计算接触区域（如需要可取消注释）
                # sensor.compute_contact()

                # 步骤 4：读取结果
                fps, flow, vnormal, img, contour, centroid, depth_map = sensor.read_info(
                    sensor.info.FPS,
                    sensor.info.VRAW,
                    sensor.info.VNORMAL,
                    sensor.info.IMG,
                    sensor.info.CONTOUR,
                    sensor.info.CENTROID,
                    sensor.info.DEPTH
                )

                # 步骤 5：整理结果字典（确保数据可序列化）
                data = {
                    'sensor_id': sensor_id,
                    'fps': fps,
                    'flow': flow.copy() if flow is not None else None,
                    'vnormal': vnormal.copy() if vnormal is not None else None,
                    'img': img.copy() if img is not None else None,
                    'contour': contour,
                    'centroid': centroid,
                    'depth_map': depth_map.copy() if depth_map is not None else None,
                    'timestamp': time.time()
                }

                # 步骤 6：将结果发送到主进程（非阻塞）
                try:
                    result_queue.put_nowait(data)
                except Exception:
                    # 如果队列已满，则丢弃当前帧，避免阻塞工作进程
                    pass

            except Exception as e:
                print(f"传感器 {sensor_id} 处理失败：{e}")
                time.sleep(0.1)

            # 步骤 7：按 target_fps 限速，使多路传感器 FPS 更接近
            if frame_interval > 0:
                elapsed = time.perf_counter() - t_start
                sleep_time = frame_interval - elapsed
                if sleep_time > 0.001:  # 至少 1ms 才 sleep，避免无意义调度
                    time.sleep(sleep_time)
        
        # 释放资源
        sensor.disconnect()
        print(f"传感器 {sensor_id} 已停止。")
        
    except Exception as e:
        print(f"传感器 {sensor_id} 初始化失败：{e}")
        result_queue.put({'sensor_id': sensor_id, 'error': str(e)})


def main():
    # =========================================================================
    # 1. 配置多路传感器
    # =========================================================================
    # 目标帧率：设为正数时，两路传感器会按该帧率限速；设为 None 则不限速
    
    parser = argparse.ArgumentParser()
    parser.add_argument("--video1","-v1", type=str, default="0", help="视频文件路径")
    parser.add_argument("--video2","-v2", type=str, default="0", help="视频文件路径")
    args = parser.parse_args()
    
    target_fps = 30

    num_sensors = 2
    sensor_configs = [
        {
            'sensor_id': 0,
            'vid_src': args.video1,
            'config_name': 'box'
        },  
        {
            'sensor_id': 1,
            'vid_src': args.video2,  # 可替换为其他视频源或摄像头索引
            'config_name': 'box'
        },
    ]

    # =========================================================================
    # 2. 创建进程间通信对象
    # =========================================================================
    # 适当增大队列容量，以缓冲更多帧并减轻主进程偶发延迟带来的丢帧
    result_queues = [Queue(maxsize=30) for _ in sensor_configs]
    stop_events = [mp.Event() for _ in sensor_configs]

    # =========================================================================
    # 3. 启动工作进程
    # =========================================================================
    processes = []
    for i, config in enumerate(sensor_configs):
        p = Process(
            target=sensor_worker,
            args=(i, config['vid_src'], config['config_name'],
                  result_queues[i], stop_events[i], target_fps)
        )
        p.start()
        processes.append(p)
    
    print(f"\n已启动 {len(processes)} 个传感器进程。")
    print("按键说明：'q' 退出程序。")
    
    # 保存每个传感器的最新一帧数据
    latest_data = [None] * len(sensor_configs)
    
    # 控制打印频率，减少 I/O 开销
    print_counter = 0
    print_interval = 30  # 每 30 帧打印一次
    
    # 控制按键检查频率
    key_check_counter = 0
    key_check_interval = 5  # 每 5 帧检查一次按键
    
    try:
        # =====================================================================
        # 4. 主循环：从队列获取结果并显示
        # =====================================================================
        while True:
            # 从所有队列中快速获取最新数据，只保留最后一帧
            for i, queue in enumerate(result_queues):
                # 清空队列，仅保留最后一帧
                data = None
                # 读取所有可用数据，只保留最新结果
                while True:
                    try:
                        data = queue.get_nowait()
                    except:
                        break
                
                if data is not None:
                    latest_data[i] = data
            
            # 显示所有传感器的最新结果
            for data in latest_data:
                if data is None or 'error' in data:
                    continue
                
                sid = data['sensor_id']
                
                # 显示形变矢量场
                if data['img'] is not None and data['flow'] is not None:
                    arrows = orisys.util.draw_arrows(
                        data['img'],
                        data['flow'],
                        threshold=5,
                        grid_spacing=10,
                        arrow_scale=1.0
                    )
                    cv2.imshow(f"传感器 {sid} - 形变矢量场", arrows)
                
                # # 显示触碰点和区域
                # if data['img'] is not None:
                #     image_with_foe = orisys.util.draw_contact(
                #         data['img'], 
                #         data['contour'], 
                #         data['centroid']
                #     )
                #     cv2.imshow(f"Contact Centroid {sid}", image_with_foe)
                
                # # 显示深度图
                # if data['depth_map'] is not None and data['depth_map'].size > 0:
                #     div_abs = data['depth_map']
                #     if div_abs.max() > div_abs.min():
                #         div_normalized = ((div_abs - div_abs.min()) / 
                #                         (div_abs.max() - div_abs.min()) * 255).astype(np.uint8)
                #     else:
                #         div_normalized = np.zeros_like(div_abs, dtype=np.uint8)
                #     cv2.imshow(f"Depth Map {sid}", 
                #              cv2.applyColorMap(div_normalized, cv2.COLORMAP_JET))
            
            # 降低打印频率，减少主循环中的 I/O 开销
            print_counter += 1
            if print_counter >= print_interval:
                for data in latest_data:
                    if data is not None and 'error' not in data:
                        sid = data['sensor_id']
                        print(f"传感器 {sid}：FPS={data['fps']:5.1f}")
                print_counter = 0
            
            # 降低按键检查频率，减少额外开销
            key_check_counter += 1
            if key_check_counter >= key_check_interval:
                key = cv2.waitKey(1) & 0xFF
                if key == ord('q'):
                    print("\n正在退出示例程序...")
                    break
                key_check_counter = 0
    
    finally:
        # =====================================================================
        # 5. 释放资源
        # =====================================================================
        # 通知所有工作进程停止
        for event in stop_events:
            event.set()
        
        # 等待所有工作进程结束
        for p in processes:
            p.join(timeout=2)
            if p.is_alive():
                p.terminate()
                p.join()
        
        cv2.destroyAllWindows()
        print("所有传感器进程已停止。")


if __name__ == '__main__':
    # Windows 下运行多进程示例所需的初始化
    mp.freeze_support()
    main()
