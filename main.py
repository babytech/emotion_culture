"""
简化版 - 儿童情绪识别与文化心理疏导系统
使用最少的依赖，主要功能包括：
- 简单的面部检测（使用OpenCV）
- 基于亮度的简单情绪估计
- 诗词响应
- 唐宋八大家静态形象显示
- 简单的Gradio界面
- 语音情绪识别
"""

import os
import numpy as np
import gradio as gr
import random
import logging
import threading
import socket
import signal
import sys
import time
from datetime import datetime
from PIL import Image

# 导入UI模块
from ui import create_ui

# 导入emotion模块中的函数和变量
from emotion import comfort_text, guochao_characters, detect_face_emotion, analyze_text_sentiment

# 导入语音情绪识别模块
from speech import analyze_speech_emotion

# -------- 配置日志记录 --------
def setup_logger():
    """设置日志记录器"""
    # 创建logs目录（如果不存在）
    if not os.path.exists('logs'):
        os.makedirs('logs')
    
    # 生成日志文件名，包含日期和时间
    log_filename = f'logs/emotion_culture_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'
    
    # 配置根日志记录器
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    
    # 创建文件处理器
    file_handler = logging.FileHandler(log_filename)
    file_handler.setLevel(logging.INFO)
    
    # 创建控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    
    # 创建格式化器
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)
    
    # 添加处理器到记录器
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger

# 初始化日志记录器
logger = setup_logger()

# -------- 导入文化模块 --------
from culture import CultureManager

# 初始化文化管理器
culture_manager = CultureManager()

def get_poem_for_emotion(emotion):
    """根据情绪随机返回对应诗人的诗词"""
    return culture_manager.get_poem_for_emotion(emotion)

# -------- 静态图片加载函数 --------
def get_poet_image(poet_name):
    """从静态图片文件夹加载对应诗人的图片"""
    return culture_manager.get_poet_image(poet_name)

# -------- 获取国潮卡通形象 --------
def get_guochao_image(emotion):
    """
    根据情绪从国潮卡通形象中随机选择一个
    """
    try:
        # 获取对应情绪的国潮卡通人物列表
        characters = guochao_characters.get(emotion, guochao_characters["neutral"])
        # 随机选择一个人物
        character_name = random.choice(characters)
        
        # 加载对应的图片
        image_path = os.path.join("images", "guochao", f"{character_name}.png")
        if os.path.exists(image_path):
            img = Image.open(image_path)
            # 如果图像太大，缩小它
            if max(img.size) > 800:
                ratio = 800 / max(img.size)
                new_size = (int(img.size[0] * ratio), int(img.size[1] * ratio))
                try:
                    # 尝试使用LANCZOS（新版Pillow中可能已重命名）
                    img = img.resize(new_size, Image.LANCZOS)
                except AttributeError:
                    # 如果LANCZOS不可用，尝试使用Lanczos或BICUBIC
                    try:
                        img = img.resize(new_size, Image.Resampling.LANCZOS)
                    except AttributeError:
                        img = img.resize(new_size, Image.BICUBIC)
            return img, character_name
        else:
            print(f"找不到{character_name}的图片")
            blank_img = Image.new('RGB', (300, 300), color=(255, 255, 255))
            return blank_img, character_name
    except Exception as e:
        print(f"加载国潮卡通形象出错: {e}")
        return Image.new('RGB', (300, 300), color=(255, 255, 255)), "未知角色"

# -------- 生成丰富的诗词解读 --------
def get_rich_poem_interpretation(poet, poem_text, emotion):
    """生成包含情绪解读、诗词含义和背景的丰富内容"""
    return culture_manager.get_rich_poem_interpretation(poet, poem_text, emotion)

# -------- 调整摄像头图像尺寸 --------
def process_image(image):
    """处理上传的图像或摄像头捕获的图像，缩小到原来的一半"""
    if image is None:
        return None
    
    # 使用PIL处理图像
    pil_image = Image.fromarray(image)
    width, height = pil_image.size
    # 缩小到原来的一半
    try:
        # 尝试使用LANCZOS（新版Pillow中可能已重命名）
        pil_image = pil_image.resize((width // 2, height // 2), Image.LANCZOS)
    except AttributeError:
        # 如果LANCZOS不可用，尝试使用Lanczos或BICUBIC
        try:
            pil_image = pil_image.resize((width // 2, height // 2), Image.Resampling.LANCZOS)
        except AttributeError:
            pil_image = pil_image.resize((width // 2, height // 2), Image.BICUBIC)
    # 转回numpy数组
    return np.array(pil_image)

# -------- 端口管理 --------
def check_port_in_use(port):
    """检查端口是否被占用"""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(1)
            result = s.connect_ex(('localhost', port))
            return result == 0
    except Exception as e:
        logger.error(f"检查端口 {port} 时出错: {e}")
        return True  # 如果发生错误，保守假设端口被占用

def find_and_kill_process_by_port(port):
    """找到并杀死占用指定端口的进程"""
    try:
        # 不同操作系统下查找占用端口进程的命令
        if sys.platform.startswith('win'):
            # Windows
            cmd = f'netstat -ano | findstr :{port}'
            output = os.popen(cmd).read()
            if output:
                lines = output.strip().split('\n')
                for line in lines:
                    parts = line.strip().split()
                    if len(parts) > 4 and parts[1].endswith(f':{port}'):
                        pid = parts[-1]
                        logger.info(f"找到使用端口 {port} 的进程 PID: {pid}")
                        try:
                            os.system(f'taskkill /PID {pid} /F')
                            logger.info(f"成功终止进程 {pid}")
                            return True
                        except Exception as e:
                            logger.error(f"终止进程时出错: {e}")
        else:
            # Unix/Linux/MacOS
            # 使用更具体的命令找出所有可能占用端口的进程
            cmd = f"lsof -i :{port}"
            output = os.popen(cmd).read()
            if output:
                lines = output.strip().split('\n')
                killed_any = False
                pids_found = []
                for line in lines:
                    if line and not line.startswith("COMMAND"):  # 跳过标题行
                        parts = line.strip().split()
                        if len(parts) > 1:
                            pid = parts[1]
                            if pid not in pids_found: # 避免重复记录和尝试杀死同一个PID
                                pids_found.append(pid)
                                logger.info(f"找到使用端口 {port} 的进程 PID: {pid}")
                                try:
                                    # 使用更强力的信号终止进程
                                    os.system(f'kill -9 {pid}')
                                    logger.info(f"已发送SIGKILL到进程 {pid} (端口 {port})")
                                    killed_any = True
                                except Exception as e:
                                    logger.error(f"终止进程 {pid} (端口 {port}) 时出错: {e}")
                
                # macOS特有的端口清理 (移除sudo命令，避免权限问题)
                if sys.platform == 'darwin' and pids_found: # 只有在找到PID时才尝试这个
                    try:
                        # 不使用sudo，避免权限问题
                        os.system(f"lsof -i :{port} | grep -v PID | awk '{{print $2}}' | xargs kill -9 2>/dev/null || true")
                        logger.info(f"已尝试进一步释放端口 {port} (macOS特定操作)")
                    except Exception as e:
                        logger.error(f"macOS特定端口释放操作出错: {e}")
                
                return killed_any or not pids_found # 如果杀死了任何进程，或者本来就没找到进程，都认为"处理"过了
            else: # lsof 未输出任何内容
                logger.info(f"未找到使用端口 {port} 的活动进程 (lsof无输出)。")
                return True # 没有进程占用，认为是成功的状态
    except Exception as e:
        logger.error(f"查找或终止占用端口 {port} 的进程时出错: {e}")
    
    logger.warning(f"未能明确找到或终止使用端口 {port} 的进程。")
    return False

def ensure_port_available(port):
    """确保端口可用，如果被占用则尝试释放"""
    if not check_port_in_use(port):
        logger.info(f"端口 {port} 可用")
        return True

    logger.warning(f"端口 {port} 已被占用。将尝试释放它。")
    
    for attempt in range(1, 3): # 尝试两次 (attempt 1 和 2)
        logger.info(f"开始释放端口 {port} 的第 {attempt} 次尝试。")
        
        # 尝试终止进程
        find_and_kill_process_by_port(port) 
        # find_and_kill_process_by_port 内部会记录日志，我们在这里不判断其返回值，
        # 因为即使它报告失败，端口也可能因其他原因被释放。
        # 主要依赖后续的 check_port_in_use。

        # 等待并检查端口是否释放
        logger.info(f"第 {attempt} 次尝试：现在检查端口 {port} 是否已释放（最多等待5秒）。")
        for i in range(5):  # 等待最多5秒
            if not check_port_in_use(port):
                logger.info(f"端口 {port} 在第 {attempt} 次尝试后成功释放（等待 {i+1} 秒后）。")
                return True # 成功释放
            if i < 4: # 避免在最后一次检查后打印 "等待中"
                 logger.info(f"等待端口 {port} 释放... {i+1}/5")
            time.sleep(1)
        
        logger.warning(f"在第 {attempt} 次尝试后，等待5秒后端口 {port} 仍被占用。")

        if attempt == 2: # 如果这是最后一次尝试
            logger.error(f"经过 {attempt} 次尝试，无法释放端口 {port}。")
            
    return False # 如果两次尝试都失败

# -------- 多线程启动Gradio服务 --------
def launch_gradio_server(interface, primary_port=7890, port_range=(7890, 7900)):
    """在单独的线程中启动Gradio服务器，提供备选端口范围"""
    def run_server():
        try:
            target_port = None
            # 尝试使用指定端口
            if ensure_port_available(primary_port):
                target_port = primary_port
                logger.info(f"将使用首选端口 {target_port} 启动Gradio服务")
            else:
                # 如果首选端口不可用或无法释放，在指定范围内查找可用端口
                logger.warning(f"首选端口 {primary_port} 不可用或无法释放，将在范围 {port_range[0]}-{port_range[1]} 内寻找可用端口")
                for port_to_try in range(port_range[0], port_range[1] + 1):
                    if port_to_try == primary_port: # 已经尝试过主端口
                        continue
                    if not check_port_in_use(port_to_try): # 只检查，不尝试强制释放备选端口
                        target_port = port_to_try
                        logger.info(f"找到备选可用端口 {target_port}")
                        break
                
                if target_port is None:
                    logger.error(f"在范围 {port_range[0]}-{port_range[1]} 内未找到其他可用端口。将尝试让 Gradio 自动选择端口。")
                    # target_port 保持 None，Gradio 会自动选择
            
            # 启动Gradio服务
            logger.info(f"正在启动Gradio服务 (尝试端口: {'自动选择' if target_port is None else target_port})...")
            interface.launch(
                server_name="0.0.0.0",
                server_port=target_port, # 如果 None, Gradio 会自动选择
                share=True,
                prevent_thread_lock=True # 确保非阻塞
            )
            logger.info("Gradio `interface.launch()` 已调用。服务应在后台线程启动。")
            logger.info("请检查控制台输出，Gradio通常会打印访问URL (本地和共享链接，如果share=True成功)。")

        except Exception as e:
            logger.error(f"启动Gradio服务时出错: {e}")

    server_thread = threading.Thread(target=run_server)
    server_thread.daemon = True  # 设置为守护线程，主程序退出时自动退出
    server_thread.start()
    
    return server_thread

# -------- 主函数 --------
def main_app(text_input, image_input, audio_input=None):
    """
    简化版主函数：
    输入: 文本输入, 摄像头图像, 语音输入
    输出: 情绪文本结果, 诗词文字与解读, 文人静态图像, 国潮形象, 安抚文案
    """
    # 处理图像尺寸
    if image_input is not None:
        image_input = process_image(image_input)
        
    # 面部表情识别
    face_emotion = None
    if image_input is not None:
        face_emotion = detect_face_emotion(image_input)
        
    # 文本情感分析
    text_emotion = None
    if text_input:
        text_emotion = analyze_text_sentiment(text_input)
        # 修改print语句以同时显示中文翻译
        if text_emotion: # 确保text_emotion不是None
            translated_text_emotion = culture_manager.translate_emotion(text_emotion)
            print(f"文本情感分析结果 (原始): {text_emotion}, 翻译为: {translated_text_emotion}")
        else:
            print(f"文本情感分析结果: 未能识别出明确情绪")
    
    # 语音情绪分析
    speech_emotion = None
    if audio_input:
        speech_emotion = analyze_speech_emotion(audio_input)
        print(f"语音情感分析结果: {speech_emotion}")
    
    # 决定使用的情绪 - 优先级：面部 > 语音 > 文本
    chosen_emotion = face_emotion if face_emotion else None
    if not chosen_emotion and speech_emotion:
        chosen_emotion = speech_emotion
    if not chosen_emotion and text_emotion:
        chosen_emotion = text_emotion
    if not chosen_emotion:
        chosen_emotion = "neutral"
    
    # 诗词情绪响应
    poet, poem_text = get_poem_for_emotion(chosen_emotion)
    
    # 生成丰富的诗词解读
    rich_poem_interpretation = get_rich_poem_interpretation(poet, poem_text, chosen_emotion)
    
    # 获取文人静态图片
    poet_image = get_poet_image(poet)
    poet_image = np.array(poet_image)
    
    # 获取国潮卡通形象
    guochao_image, character_name = get_guochao_image(chosen_emotion)
    guochao_image = np.array(guochao_image)
    
    # 获取情绪安抚文案
    comfort = comfort_text.get(chosen_emotion, comfort_text["neutral"])
    guochao_response = f"{character_name}：\n{comfort}"
    
    # 返回情绪识别结果文本（中文翻译）
    emotion_cn = culture_manager.translate_emotion(chosen_emotion)
    emotion_result = f"检测到的情绪: {emotion_cn}"
    
    return emotion_result, rich_poem_interpretation, poet_image, guochao_response, guochao_image

# 使用ui.py创建界面
iface = create_ui(main_app)

def ensure_image_directories():
    """确保图像目录存在"""
    required_dirs = [
        os.path.join("images"),
        os.path.join("images", "tangsong"),
        os.path.join("images", "guochao")
    ]
    
    for directory in required_dirs:
        if not os.path.exists(directory):
            logger.info(f"创建目录: {directory}")
            os.makedirs(directory)
            
    # 检查图像文件是否存在
    tangsong_images = os.listdir(os.path.join("images", "tangsong")) if os.path.exists(os.path.join("images", "tangsong")) else []
    guochao_images = os.listdir(os.path.join("images", "guochao")) if os.path.exists(os.path.join("images", "guochao")) else []
    
    if not tangsong_images:
        logger.warning("唐宋八大家图片目录为空，将使用空白图片代替")
    
    if not guochao_images:
        logger.warning("国潮卡通形象目录为空，将使用空白图片代替")

if __name__ == "__main__":
    try:
        logger.info("="*50)
        logger.info("准备启动儿童情绪识别与文化心理疏导系统...")
        logger.info("="*50)
        
        # 确保图像目录存在
        ensure_image_directories()
        
        # 端口配置
        primary_port = 8080
        port_range = (8080, 8100)  # 提供备选端口范围
        
        # 启动Gradio服务器线程
        server_thread = launch_gradio_server(iface, primary_port=primary_port, port_range=port_range)
        
        # 保持主线程运行，可以在这里添加其他功能
        try:
            while True:
                # 主线程保持活跃，但不消耗太多CPU
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("收到键盘中断，正在安全退出...")
            # 这里不需要做额外工作，因为server_thread是守护线程
    
    except Exception as e:
        logger.error(f"程序运行过程中出错: {e}")
        sys.exit(1) 