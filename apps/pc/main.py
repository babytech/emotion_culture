"""
青少年情绪识别与文化心理疏导系统
使用最少的依赖，主要功能包括：
- 简单的面部检测（使用OpenCV）
- 基于亮度的简单情绪估计
- 诗词响应
- 唐宋八大家静态形象显示
- 简单的Gradio界面
- 语音情绪识别
"""

import os
import json
import numpy as np
import gradio as gr
import random
import logging
import threading
import socket
import signal
import sys
import time
import uuid
from datetime import datetime
from PIL import Image
import pyttsx3
import platform
import cv2

# 导入UI模块
from ui import create_ui

# 导入emotion模块中的函数和变量
from emotion import comfort_text, guochao_characters, detect_face_emotion, analyze_text_sentiment

# 导入语音情绪识别模块
from speech import analyze_speech_emotion, validate_audio_input

# 导入 email_utils 中的邮件发送函数
from email_utils import send_analysis_email

# 统一基于当前文件位置解析资源路径，避免运行目录变化导致找不到图片/数据
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def app_path(*parts):
    """构建基于当前应用目录的绝对路径。"""
    return os.path.join(BASE_DIR, *parts)

# -------- 配置日志记录 --------
def setup_logger():
    """设置日志记录器"""
    # 创建logs目录（如果不存在）
    logs_dir = app_path("logs")
    if not os.path.exists(logs_dir):
        os.makedirs(logs_dir)
    
    # 生成日志文件名，包含日期和时间
    log_filename = app_path("logs", f'emotion_culture_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log')
    
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

# -------- 文本转语音函数 --------
# 创建TTS引擎的全局实例和锁
tts_engine = None
tts_lock = threading.Lock()

def speak_text_in_thread(text_to_speak, gender='female'):
    """
    使用 pyttsx3 在单独的线程中朗读文本，优先使用'月' (Yue) 语音。
    """
    def speak():
        global tts_engine
        try:
            with tts_lock:
                logger.info("TTS speak_text_in_thread: 尝试初始化或重用 pyttsx3 引擎...")
                
                # 如果引擎已存在但状态不正常，则重置它
                if tts_engine is not None:
                    try:
                        # 尝试获取属性来测试引擎是否正常
                        voices = tts_engine.getProperty('voices')
                        logger.info("TTS speak_text_in_thread: 复用现有引擎")
                    except Exception as e:
                        logger.warning(f"TTS speak_text_in_thread: 现有引擎不可用，将重新初始化: {e}")
                        try:
                            tts_engine = None
                        except:
                            pass
                
                # 初始化引擎（如果需要）
                if tts_engine is None:
                    logger.info("TTS speak_text_in_thread: 创建新的TTS引擎实例")
                    tts_engine = pyttsx3.init()
                
                system_platform = platform.system() # 获取平台信息，以备后续特定逻辑
                logger.info(f"TTS speak_text_in_thread: 引擎已准备。当前平台: {system_platform}")

                voices = tts_engine.getProperty('voices')
                logger.info(f"TTS speak_text_in_thread: 找到 {len(voices)} 个可用语音。")
                # 调试时可以取消注释下一行以查看所有语音的详细信息
                # for i, voice in enumerate(voices):
                #     try:
                #         lang_str = ", ".join(voice.languages) if hasattr(voice, 'languages') and voice.languages else "N/A"
                #         gender_str = voice.gender if hasattr(voice, 'gender') and voice.gender else "N/A"
                #         logger.info(f"  语音 {i}: ID='{voice.id}', 名称='{voice.name}', 性别='{gender_str}', 语言='{lang_str}'")
                #     except Exception as e_voice_attr:
                #         logger.warning(f"  语音 {i}: ID='{getattr(voice, 'id', 'N/A')}', 名称='{getattr(voice, 'name', 'N/A')}' (获取部分属性失败: {e_voice_attr})")

                chosen_voice_id = None
                chosen_voice_name = "未选择"

                # 1. 优先尝试精确查找名为 "月" 或 "Yue" 的语音
                preferred_voice_names = ["月", "Yue"] # "Yue (Premium)" 也可以加入，但 "Yue" 应该能匹配到
                logger.info(f"TTS speak_text_in_thread: 尝试精确查找首选中文语音 (名称包含: {', '.join(preferred_voice_names)})...")
                for voice in voices:
                    if hasattr(voice, 'name') and voice.name:
                        for preferred_name in preferred_voice_names:
                            if preferred_name.lower() in voice.name.lower(): # 不区分大小写匹配
                                # 确保它也支持中文，以防有其他语言的Yue
                                if hasattr(voice, 'languages') and voice.languages and any('zh' in lang.lower() for lang in voice.languages):
                                    chosen_voice_id = voice.id
                                    chosen_voice_name = voice.name
                                    logger.info(f"TTS speak_text_in_thread:  => 精确匹配成功: 找到指定中文语音 '{chosen_voice_name}' (ID: {chosen_voice_id})")
                                    break 
                        if chosen_voice_id: 
                            break
                
                if chosen_voice_id:
                    logger.info(f"TTS speak_text_in_thread: 首选语音 '{chosen_voice_name}' 已找到并选中。")
                else:
                    logger.info("TTS speak_text_in_thread: 未能通过精确名称查找到首选语音'月'或'Yue'。将继续通用选择逻辑...")
                    # 2. 如果未找到精确匹配，执行之前的通用女性和中文语音选择逻辑
                    if gender == 'female': # 只有当要求女声时才应用后续的通用女声逻辑
                        for voice in voices:
                            name_lower = voice.name.lower() if hasattr(voice, 'name') and voice.name else ""
                            is_female_by_name = "female" in name_lower or "女孩" in name_lower or "女声" in name_lower
                            is_female_by_gender = hasattr(voice, 'gender') and voice.gender and voice.gender.lower() == 'female'
                            is_female = is_female_by_name or is_female_by_gender

                            supports_chinese_by_lang = hasattr(voice, 'languages') and voice.languages and any('zh' in lang.lower() for lang in voice.languages)
                            # macOS 上常见的其他中文语音名，作为后备补充
                            supports_chinese_by_name_macos = "ting-ting" in name_lower or "mei-jia" in name_lower or "sin-ji" in name_lower 
                            supports_chinese = supports_chinese_by_lang or (system_platform == 'Darwin' and supports_chinese_by_name_macos)

                            if is_female and supports_chinese:
                                chosen_voice_id = voice.id
                                chosen_voice_name = voice.name
                                logger.info(f"TTS speak_text_in_thread:  => 通用选择：找到支持中文的女性语音 '{chosen_voice_name}' (ID: {chosen_voice_id})")
                                break
                        
                        if not chosen_voice_id: # 如果没有找到中文女声，退一步选择任何女声
                            for voice in voices:
                                name_lower = voice.name.lower() if hasattr(voice, 'name') and voice.name else ""
                                is_female_by_name = "female" in name_lower or "女孩" in name_lower or "女声" in name_lower
                                is_female_by_gender = hasattr(voice, 'gender') and voice.gender and voice.gender.lower() == 'female'
                                is_female = is_female_by_name or is_female_by_gender
                                if is_female:
                                    chosen_voice_id = voice.id
                                    chosen_voice_name = voice.name
                                    logger.info(f"TTS speak_text_in_thread:  => 通用选择：找到女性语音 '{chosen_voice_name}' (ID: {chosen_voice_id}) (可能非中文)")
                                    break
                
                # 3.最后的后备逻辑：如果以上都没有选定语音
                if not chosen_voice_id:
                    logger.info("TTS speak_text_in_thread: 未通过特定名称或性别/语言组合找到语音。尝试通用后备方案...")
                    if voices: # 如果有任何可用语音
                        # 可以选择第一个，或者对于macOS，尝试系统默认（但pyttsx3不直接暴露这个）
                        # 简单起见，我们用第一个作为最终后备
                        chosen_voice_id = voices[0].id
                        chosen_voice_name = voices[0].name if hasattr(voices[0], 'name') else '[未知名称]'
                        logger.info(f"TTS speak_text_in_thread:  => 后备选择：使用第一个可用语音 '{chosen_voice_name}' (ID: {chosen_voice_id})")
                    else:
                        logger.error("TTS speak_text_in_thread: 严重错误 - 无任何可用TTS语音!")
                        return # 无法继续

                logger.info(f"TTS speak_text_in_thread: --- 语音选择完毕 ---")
                if chosen_voice_id:
                    logger.info(f"TTS speak_text_in_thread: 最终设置语音为: '{chosen_voice_name}' (ID: {chosen_voice_id})")
                    tts_engine.setProperty('voice', chosen_voice_id)
                else:
                    logger.warning("TTS speak_text_in_thread: 未能选择任何语音，将使用驱动默认语音（如果有）。")
                
                tts_engine.setProperty('rate', 180) # 您可以根据需要调整语速
                logger.info(f"TTS speak_text_in_thread: 准备朗读文本 (长度: {len(text_to_speak)} chars): '{text_to_speak[:100]}...'")
                tts_engine.say(text_to_speak)
                logger.info("TTS speak_text_in_thread: engine.say() 已调用。")
                tts_engine.runAndWait()
                logger.info("TTS speak_text_in_thread: engine.runAndWait() 已完成。")
        except Exception as e:
            logger.error(f"TTS speak_text_in_thread: 文本转语音时发生错误: {e}", exc_info=True)
            # 如果发生错误，尝试重置引擎以便下次使用
            with tts_lock:
                try:
                    if tts_engine is not None:
                        logger.info("TTS speak_text_in_thread: 发生错误后尝试重置TTS引擎")
                        tts_engine = None
                except:
                    pass

    tts_thread = threading.Thread(target=speak)
    tts_thread.daemon = True # 主程序退出时，线程也退出
    tts_thread.start()

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
        image_path = app_path("images", "guochao", f"{character_name}.png")
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
            launch_kwargs = getattr(interface, "_launch_kwargs", {})
            interface.launch(
                server_name="0.0.0.0",
                server_port=target_port, # 如果 None, Gradio 会自动选择
                share=True,
                prevent_thread_lock=True, # 确保非阻塞
                **launch_kwargs
            )
            logger.info("Gradio `interface.launch()` 已调用。服务应在后台线程启动。")
            logger.info("请检查控制台输出，Gradio通常会打印访问URL (本地和共享链接，如果share=True成功)。")

        except Exception as e:
            logger.error(f"启动Gradio服务时出错: {e}")

    server_thread = threading.Thread(target=run_server)
    server_thread.daemon = True  # 设置为守护线程，主程序退出时自动退出
    server_thread.start()
    
    return server_thread

_TRIGGER_KEYWORDS = {
    "学业压力": ("考试", "成绩", "作业", "学习", "上课", "老师", "升学"),
    "人际关系": ("同学", "朋友", "家人", "父母", "关系", "吵架", "冲突"),
    "自我期待": ("目标", "计划", "未来", "担心", "焦虑", "压力", "比较"),
    "身体状态": ("失眠", "疲惫", "头痛", "不舒服", "生病", "累", "困"),
    "环境变化": ("转学", "搬家", "新环境", "变化", "陌生", "适应"),
}

_DEFAULT_TRIGGER_TAGS = {
    "happy": ["积极体验", "关系支持"],
    "sad": ["情绪低落", "压力积累"],
    "angry": ["冲突压力", "期待落差"],
    "surprise": ["突发变化", "信息冲击"],
    "neutral": ["日常波动", "状态平稳"],
    "fear": ["未知担忧", "安全感不足"],
}

_DAILY_SUGGESTIONS = {
    "happy": "记录今天让你开心的一个瞬间，并把这份积极感受分享给一个信任的人。",
    "sad": "给自己 10 分钟安静时间，做 3 次深呼吸，再写下一个可马上完成的小目标。",
    "angry": "先暂停 1 分钟离开冲突现场，缓和呼吸后再表达你的真实需求。",
    "surprise": "把这次意外感受写成一句话，分清“事实”和“想法”，再决定下一步。",
    "neutral": "保持当前节奏，今晚固定一个放松时段，巩固这份平稳状态。",
    "fear": "把担心拆成“可控制/不可控制”两部分，先执行一件可控制的小行动。",
}

_INPUT_MODE_LABELS = {
    "text": "文字",
    "voice": "录音",
    "pc_camera": "摄像头",
}


def _env_int(name, default):
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
        return value if value > 0 else default
    except ValueError:
        return default


def _env_float(name, default):
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        value = float(raw)
        return value if value > 0 else default
    except ValueError:
        return default


def _normalize_rgb_image(image):
    if image is None:
        return None
    arr = np.asarray(image)
    if arr.size == 0:
        return None

    if arr.dtype != np.uint8:
        arr = arr.astype(np.float32)
        if arr.max() <= 1.0:
            arr = arr * 255.0
        arr = np.clip(arr, 0, 255).astype(np.uint8)

    if arr.ndim == 2:
        return cv2.cvtColor(arr, cv2.COLOR_GRAY2RGB)
    if arr.ndim != 3:
        return None
    if arr.shape[2] == 4:
        return cv2.cvtColor(arr, cv2.COLOR_RGBA2RGB)
    if arr.shape[2] == 3:
        return arr
    return None


class CameraPhotoRejectError(ValueError):
    def __init__(self, code, message, retry_hint=None):
        self.code = code
        self.message = message
        self.retry_hint = retry_hint or "请正对镜头、保证光线充足后重新拍摄。"
        super().__init__(f"{code}: {message}")

    def to_client_message(self):
        return f"[{self.code}] {self.message} {self.retry_hint}"


class AppLogic:
    def __init__(self):
        self.cache_dir = app_path("cache")
        self.history_cache_file = app_path("cache", "history_summary.json")
        self.cache_lock = threading.Lock()
        self.max_history_items = max(10, _env_int("PC_HISTORY_MAX_ITEMS", 60))
        self.latest_analysis_request_id = None
        self._ensure_history_cache_ready()

    @staticmethod
    def _box_iou(box_a, box_b):
        ax, ay, aw, ah = box_a
        bx, by, bw, bh = box_b
        ax2, ay2 = ax + aw, ay + ah
        bx2, by2 = bx + bw, by + bh

        inter_x1 = max(ax, bx)
        inter_y1 = max(ay, by)
        inter_x2 = min(ax2, bx2)
        inter_y2 = min(ay2, by2)

        inter_w = max(0, inter_x2 - inter_x1)
        inter_h = max(0, inter_y2 - inter_y1)
        inter_area = inter_w * inter_h
        if inter_area <= 0:
            return 0.0

        area_a = aw * ah
        area_b = bw * bh
        union = area_a + area_b - inter_area
        if union <= 0:
            return 0.0
        return inter_area / union

    @staticmethod
    def _dedupe_overlapped_faces(faces, iou_threshold):
        kept = []
        for box in sorted(faces, key=lambda item: item[2] * item[3], reverse=True):
            if all(AppLogic._box_iou(box, existing) < iou_threshold for existing in kept):
                kept.append(box)
        return kept

    @staticmethod
    def _detect_eye_count(eye_cascade, gray, face_box):
        x, y, w, h = face_box
        roi = gray[y : y + h, x : x + w]
        if roi.size == 0:
            return 0
        eyes = eye_cascade.detectMultiScale(
            roi,
            scaleFactor=1.1,
            minNeighbors=4,
            minSize=(max(10, w // 12), max(10, h // 12)),
        )
        return int(len(eyes))

    def _validate_camera_photo(self, image):
        image_rgb = _normalize_rgb_image(image)
        if image_rgb is None:
            raise CameraPhotoRejectError(
                code="FACE_IMAGE_INVALID",
                message="图片无效，请重新拍摄。",
            )

        gray = cv2.cvtColor(image_rgb, cv2.COLOR_RGB2GRAY)
        gray = cv2.GaussianBlur(gray, (3, 3), 0)
        gray = cv2.equalizeHist(gray)

        face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
        eye_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_eye.xml")

        raw_faces = face_cascade.detectMultiScale(
            gray,
            scaleFactor=1.1,
            minNeighbors=6,
            minSize=(40, 40),
        )

        image_area = float(gray.shape[0] * gray.shape[1])
        min_candidate_ratio = _env_float("FACE_MIN_CANDIDATE_AREA_RATIO", 0.01)
        candidate_faces = []
        for (x, y, w, h) in raw_faces:
            area_ratio = (w * h) / image_area if image_area > 0 else 0.0
            if area_ratio >= min_candidate_ratio:
                candidate_faces.append((int(x), int(y), int(w), int(h)))

        dedupe_iou = _env_float("FACE_DEDUPE_IOU_THRESHOLD", 0.3)
        faces = self._dedupe_overlapped_faces(candidate_faces, dedupe_iou)
        if len(faces) == 0:
            raise CameraPhotoRejectError(
                code="FACE_NOT_FOUND",
                message="没有检测到人脸，请保证自拍时正脸入镜。",
            )

        min_presence_eye_count = _env_int("FACE_MIN_PRESENCE_EYE_COUNT", 1)
        high_area_presence_ratio = _env_float("FACE_HIGH_AREA_PRESENCE_RATIO", 0.08)

        valid_faces = []
        face_eye_count = {}
        face_area_ratio_map = {}
        for box in faces:
            x, y, w, h = box
            area_ratio = (w * h) / image_area if image_area > 0 else 0.0
            eye_count = self._detect_eye_count(eye_cascade, gray, box)
            face_area_ratio_map[box] = area_ratio
            face_eye_count[box] = eye_count
            if eye_count >= min_presence_eye_count or area_ratio >= high_area_presence_ratio:
                valid_faces.append(box)

        if len(valid_faces) == 0:
            raise CameraPhotoRejectError(
                code="FACE_NOT_FOUND",
                message="没有检测到清晰正脸，请重拍。",
            )

        valid_faces = sorted(valid_faces, key=lambda item: item[2] * item[3], reverse=True)
        (x, y, w, h) = valid_faces[0]
        face_area_ratio = face_area_ratio_map.get((x, y, w, h), 0.0)
        min_face_area_ratio = _env_float("FACE_MIN_AREA_RATIO", 0.022)
        if face_area_ratio < min_face_area_ratio:
            if face_eye_count.get((x, y, w, h), 0) <= 0:
                raise CameraPhotoRejectError(
                    code="FACE_NOT_FOUND",
                    message="没有检测到清晰正脸，请重拍。",
                )
            raise CameraPhotoRejectError(
                code="FACE_TOO_SMALL",
                message="人脸区域过小，请靠近镜头后重拍。",
            )

        primary_area = float(w * h)
        multi_min_ratio = _env_float("FACE_MULTI_MIN_RATIO", 0.8)
        min_secondary_area_ratio = min_face_area_ratio * _env_float(
            "FACE_MULTI_SECONDARY_ABS_RATIO_FACTOR", 0.75
        )
        significant_secondary = [
            box
            for box in valid_faces[1:]
            if (
                primary_area > 0
                and ((box[2] * box[3]) / primary_area) >= multi_min_ratio
                and face_area_ratio_map.get(box, 0.0) >= min_secondary_area_ratio
                and face_eye_count.get(box, 0) >= min_presence_eye_count
            )
        ]
        if significant_secondary:
            raise CameraPhotoRejectError(
                code="FACE_MULTI_FOUND",
                message="检测到多人入镜，请仅保留单人自拍。",
            )

        roi = gray[y : y + h, x : x + w]
        if roi.size == 0:
            raise CameraPhotoRejectError(
                code="FACE_IMAGE_INVALID",
                message="图片无效，请重新拍摄。",
            )

        min_brightness = _env_float("FACE_MIN_BRIGHTNESS", 50.0)
        brightness = float(np.mean(roi))
        if brightness < min_brightness:
            raise CameraPhotoRejectError(
                code="FACE_TOO_DARK",
                message="光线过暗，请在更明亮环境重新拍摄。",
            )

        min_laplacian_var = _env_float("FACE_MIN_LAPLACIAN_VAR", 30.0)
        laplacian_var = float(cv2.Laplacian(roi, cv2.CV_64F).var())
        if laplacian_var < min_laplacian_var:
            raise CameraPhotoRejectError(
                code="FACE_TOO_BLUR",
                message="图片模糊，请保持稳定后重新拍摄。",
            )

        return image_rgb

    def _ensure_history_cache_ready(self):
        os.makedirs(self.cache_dir, exist_ok=True)
        if not os.path.exists(self.history_cache_file):
            with open(self.history_cache_file, "w", encoding="utf-8") as f:
                json.dump([], f, ensure_ascii=False, indent=2)

    def _load_history_items(self):
        self._ensure_history_cache_ready()
        with self.cache_lock:
            try:
                with open(self.history_cache_file, "r", encoding="utf-8") as f:
                    payload = json.load(f)
                if isinstance(payload, list):
                    return payload
                logger.warning("历史缓存格式异常，已重置为空列表。")
            except json.JSONDecodeError:
                logger.warning("历史缓存 JSON 解析失败，已重置为空列表。")
            except Exception as exc:
                logger.error(f"读取历史缓存失败: {exc}")
                return []
        self._save_history_items([])
        return []

    def _save_history_items(self, items):
        self._ensure_history_cache_ready()
        with self.cache_lock:
            with open(self.history_cache_file, "w", encoding="utf-8") as f:
                json.dump(items, f, ensure_ascii=False, indent=2)

    @staticmethod
    def _truncate_text(text, max_len):
        source = (text or "").strip()
        if len(source) <= max_len:
            return source
        return source[: max(0, max_len - 1)] + "…"

    @staticmethod
    def _to_display_time(iso_text):
        try:
            normalized = (iso_text or "").replace("Z", "+00:00")
            dt = datetime.fromisoformat(normalized)
            return dt.astimezone().strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            return iso_text or "-"

    @staticmethod
    def _describe_input_modes(input_modes):
        labels = [_INPUT_MODE_LABELS.get(mode, mode) for mode in (input_modes or [])]
        return " / ".join(labels) if labels else "未知"

    def _build_secondary_emotions(self, primary_emotion, emotion_weights):
        ranked = sorted(
            (
                (emotion_code, score)
                for emotion_code, score in (emotion_weights or {}).items()
                if emotion_code != primary_emotion and score > 0
            ),
            key=lambda item: item[1],
            reverse=True,
        )
        result = []
        for emotion_code, _ in ranked[:2]:
            result.append(
                {
                    "code": emotion_code,
                    "label": culture_manager.translate_emotion(emotion_code),
                }
            )
        return result

    def _build_emotion_overview(self, primary_emotion_cn, text_emotion, face_emotion, speech_emotion):
        source_labels = []
        if text_emotion:
            source_labels.append("文本")
        if face_emotion:
            source_labels.append("图像")
        if speech_emotion:
            source_labels.append("语音")
        source_text = "、".join(source_labels) if source_labels else "当前输入"
        return f"综合{source_text}信号，当前以“{primary_emotion_cn}”为主。"

    def _infer_trigger_tags(self, text, primary_emotion):
        text_value = (text or "").strip().lower()
        tags = []
        if text_value:
            for tag, keywords in _TRIGGER_KEYWORDS.items():
                if any(keyword in text_value for keyword in keywords):
                    tags.append(tag)

        if not tags:
            tags.extend(_DEFAULT_TRIGGER_TAGS.get(primary_emotion, _DEFAULT_TRIGGER_TAGS["neutral"]))

        deduped = []
        for tag in tags:
            if tag not in deduped:
                deduped.append(tag)
        return deduped[:3]

    def _append_history_item(self, item):
        items = self._load_history_items()
        items.insert(0, item)
        items = items[: self.max_history_items]
        self._save_history_items(items)

    def _find_history_item(self, request_id):
        if not request_id:
            return None
        items = self._load_history_items()
        for item in items:
            if item.get("request_id") == request_id:
                return item
        return None

    def _build_history_dropdown_choices(self, items):
        choices = []
        for item in items:
            request_id = item.get("request_id")
            if not request_id:
                continue
            primary_label = (
                item.get("primary_emotion", {}).get("label")
                or culture_manager.translate_emotion(item.get("primary_emotion", {}).get("code", "neutral"))
            )
            mode_text = self._describe_input_modes(item.get("input_modes", []))
            mail_text = "已发邮件" if item.get("mail_sent") else "未发邮件"
            analyzed_at = self._to_display_time(item.get("analyzed_at"))
            label = f"{analyzed_at} | {primary_label} | {mode_text} | {mail_text}"
            choices.append((label, request_id))
        return choices

    def show_history_detail(self, request_id):
        if not request_id:
            return "请选择一条历史记录。"
        item = self._find_history_item(request_id)
        if not item:
            return "未找到该历史记录，建议刷新列表。"

        primary = item.get("primary_emotion", {})
        secondary = item.get("secondary_emotions", [])
        secondary_text = "、".join(x.get("label", "-") for x in secondary if isinstance(x, dict)) or "无"
        trigger_tags = item.get("trigger_tags", [])
        trigger_text = "、".join(trigger_tags) if trigger_tags else "未标注"
        detail = (
            f"分析时间：{self._to_display_time(item.get('analyzed_at'))}\n"
            f"输入类型：{self._describe_input_modes(item.get('input_modes', []))}\n"
            f"主情绪：{primary.get('label', '-')} ({primary.get('code', '-')})\n"
            f"补充情绪：{secondary_text}\n"
            f"情绪概述：{item.get('emotion_overview_summary', '-')}\n"
            f"触发标签：{trigger_text}\n"
            f"诗词摘要：{item.get('poem_response_summary', '-')}\n"
            f"国潮角色：{item.get('guochao_name', '-')}\n"
            f"建议摘要：{item.get('daily_suggestion_summary', '-')}\n"
            f"是否已发送邮件：{'是' if item.get('mail_sent') else '否'}\n"
            f"请求ID：{item.get('request_id', '-')}"
        )
        return detail

    def _history_panel_payload(self, selected_request_id=None, status_text=None):
        items = self._load_history_items()
        choices = self._build_history_dropdown_choices(items)
        if not choices:
            return gr.update(choices=[], value=None), "暂无本地历史记录。", (status_text or "暂无历史。")

        available_request_ids = [value for _, value in choices]
        if selected_request_id not in available_request_ids:
            selected_request_id = available_request_ids[0]

        detail_text = self.show_history_detail(selected_request_id)
        return (
            gr.update(choices=choices, value=selected_request_id),
            detail_text,
            status_text or "已加载历史记录。",
        )

    def refresh_history_panel(self, selected_request_id=None):
        return self._history_panel_payload(selected_request_id=selected_request_id, status_text="历史已刷新。")

    def clear_history_panel(self):
        self._save_history_items([])
        self.latest_analysis_request_id = None
        return gr.update(choices=[], value=None), "暂无本地历史记录。", "已清空本地历史缓存。"

    def _mark_mail_sent(self, request_id):
        if not request_id:
            return False
        items = self._load_history_items()
        changed = False
        for item in items:
            if item.get("request_id") == request_id:
                if not item.get("mail_sent"):
                    item["mail_sent"] = True
                    changed = True
                break
        if changed:
            self._save_history_items(items)
        return changed

    def check_camera_availability(self):
        capture = None
        try:
            capture = cv2.VideoCapture(0)
            if not capture or not capture.isOpened():
                return "未检测到可用摄像头，请检查设备权限后重试。"
            ok, _ = capture.read()
            if not ok:
                return "摄像头已连接但拍照失败，请重试。"
            return "摄像头可用，可以拍照。"
        except Exception as exc:
            logger.error(f"检查摄像头可用性失败: {exc}")
            return "摄像头检测失败，请检查系统权限后重试。"
        finally:
            if capture is not None:
                capture.release()

    def confirm_camera_photo(self, camera_image, existing_confirmed_image=None):
        if camera_image is None:
            camera_msg = self.check_camera_availability()
            return (
                existing_confirmed_image,
                existing_confirmed_image,
                f"尚未检测到拍照结果。{camera_msg}",
            )

        try:
            validated_image = self._validate_camera_photo(camera_image)
            return validated_image, validated_image, "拍照确认成功，可提交分析。"
        except CameraPhotoRejectError as exc:
            logger.warning(f"摄像头照片校验未通过: {exc.code} - {exc.message}")
            return (
                existing_confirmed_image,
                existing_confirmed_image,
                exc.to_client_message(),
            )
        except Exception as exc:
            logger.error(f"摄像头照片校验异常: {exc}", exc_info=True)
            return (
                existing_confirmed_image,
                existing_confirmed_image,
                "摄像头照片校验失败，请重新拍摄。",
            )

    def clear_camera_confirmation(self):
        return None, None, None, "已清除确认照片，请重新拍照并确认。"

    def process_analysis(self, text_input, image_input, audio_input=None):
        """
        主分析函数：
        输入: 文本输入, 摄像头确认图像, 语音输入
        输出: 情绪文本结果, 诗词文字与解读, 文人静态图像, 国潮形象, 安抚文案, 状态与历史
        """
        text_value = (text_input or "").strip()
        logger.info(
            f"接收到分析请求: 文本长度={len(text_value)}, 图像存在={image_input is not None}, 音频存在={audio_input is not None}"
        )

        status_notes = []
        input_modes = []

        # 拍照输入：再次校验保证分析前质量达标（不依赖前端状态）
        processed_image_input = None
        face_emotion = None
        if image_input is not None:
            try:
                validated_image = self._validate_camera_photo(image_input)
                processed_image_input = process_image(validated_image)
                face_emotion = detect_face_emotion(processed_image_input)
                input_modes.append("pc_camera")
                logger.info(f"面部情绪识别结果: {face_emotion}")
            except CameraPhotoRejectError as exc:
                status_notes.append(exc.to_client_message())
                logger.warning(f"分析前图像校验未通过: {exc.code} - {exc.message}")
            except Exception as exc:
                status_notes.append("摄像头照片校验失败，已忽略本次图像输入。")
                logger.error(f"分析前图像校验异常: {exc}", exc_info=True)

        # 文本情感分析
        text_emotion = None
        if text_value:
            input_modes.append("text")
            text_emotion = analyze_text_sentiment(text_value)
            if text_emotion:
                translated_text_emotion = culture_manager.translate_emotion(text_emotion)
                logger.info(f"文本情感分析结果 (原始): {text_emotion}, 翻译为: {translated_text_emotion}")
            else:
                logger.info("文本情感分析结果: 未能识别出明确情绪")

        # 语音输入：先做基础校验，失败可重录，且不影响其他输入
        speech_emotion = None
        if audio_input:
            valid_audio, audio_error = validate_audio_input(audio_input)
            if not valid_audio:
                status_notes.append(f"[VOICE_INVALID] {audio_error} 可重录，或直接改用文字输入。")
            else:
                speech_emotion = analyze_speech_emotion(audio_input)
                if speech_emotion:
                    input_modes.append("voice")
                    logger.info(f"语音情感分析结果: {speech_emotion}")
                else:
                    status_notes.append("[VOICE_RETRY] 录音识别失败，请重录；已有文本/拍照输入不会丢失。")

        if not text_value and processed_image_input is None and speech_emotion is None:
            analysis_status = "请至少提供一种有效输入（文字、录音、确认拍照）后再分析。"
            if status_notes:
                analysis_status = "；".join(status_notes + [analysis_status])
            history_update, history_detail, history_status = self._history_panel_payload(
                selected_request_id=self.latest_analysis_request_id,
                status_text="未写入历史：输入不足。",
            )
            return (
                "",
                "",
                None,
                "",
                None,
                analysis_status,
                history_update,
                history_detail,
                history_status,
            )

        # 情绪融合
        emotion_weights = {
            "happy": 0.0,
            "sad": 0.0,
            "angry": 0.0,
            "surprise": 0.0,
            "neutral": 0.0,
            "fear": 0.0,
        }

        if text_value and text_emotion:
            emotion_weights[text_emotion] += 0.5
            if face_emotion == text_emotion:
                emotion_weights[text_emotion] += 0.2
            if speech_emotion == text_emotion:
                emotion_weights[text_emotion] += 0.2
        else:
            if face_emotion:
                emotion_weights[face_emotion] += 0.4
            if speech_emotion:
                emotion_weights[speech_emotion] += 0.4

        if face_emotion and face_emotion != text_emotion:
            emotion_weights[face_emotion] += 0.2
        if speech_emotion and speech_emotion != text_emotion:
            emotion_weights[speech_emotion] += 0.2

        if all(weight == 0.0 for weight in emotion_weights.values()):
            chosen_emotion = "neutral"
            logger.info("没有检测到明确情绪，使用 neutral 作为默认值")
        else:
            chosen_emotion = max(emotion_weights.items(), key=lambda x: x[1])[0]
            logger.info(f"情绪权重分布: {emotion_weights}")
            logger.info(f"选择权重最高的情绪: {chosen_emotion}")

        poet, poem_text = get_poem_for_emotion(chosen_emotion)
        rich_poem_interpretation = get_rich_poem_interpretation(poet, poem_text, chosen_emotion)

        poet_pil_image = get_poet_image(poet)
        poet_image_np = np.array(poet_pil_image) if poet_pil_image else None

        guochao_pil_image, character_name = get_guochao_image(chosen_emotion)
        guochao_image_np = np.array(guochao_pil_image) if guochao_pil_image else None

        comfort = comfort_text.get(chosen_emotion, comfort_text["neutral"])
        guochao_response = f"{character_name}：\n{comfort}"

        emotion_cn = culture_manager.translate_emotion(chosen_emotion)
        emotion_result = f"检测到的情绪: {emotion_cn}"

        # 语音播报
        full_speech_text = ""
        if rich_poem_interpretation:
            full_speech_text += f"请听诗词与解读：\n{rich_poem_interpretation}\n\n"
        if guochao_response:
            full_speech_text += f"接下来，是来自国潮伙伴的慰藉：\n{guochao_response}"
        if full_speech_text:
            speak_text_in_thread(full_speech_text)

        # 本地轻量历史写入（仅摘要，不存原始媒体）
        request_id = f"pc_{uuid.uuid4().hex[:12]}"
        analyzed_at = datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
        secondary_emotions = self._build_secondary_emotions(chosen_emotion, emotion_weights)
        emotion_overview = self._build_emotion_overview(
            primary_emotion_cn=emotion_cn,
            text_emotion=text_emotion,
            face_emotion=face_emotion,
            speech_emotion=speech_emotion,
        )
        trigger_tags = self._infer_trigger_tags(text_value, chosen_emotion)
        daily_suggestion = _DAILY_SUGGESTIONS.get(chosen_emotion, _DAILY_SUGGESTIONS["neutral"])

        history_item = {
            "history_id": f"his_{uuid.uuid4().hex[:12]}",
            "request_id": request_id,
            "analyzed_at": analyzed_at,
            "input_modes": input_modes,
            "primary_emotion": {
                "code": chosen_emotion,
                "label": emotion_cn,
            },
            "secondary_emotions": secondary_emotions,
            "emotion_overview_summary": self._truncate_text(emotion_overview, 180),
            "trigger_tags": trigger_tags,
            "poem_response_summary": self._truncate_text(rich_poem_interpretation, 120),
            "guochao_name": character_name,
            "daily_suggestion_summary": self._truncate_text(daily_suggestion, 120),
            "mail_sent": False,
        }
        self._append_history_item(history_item)
        self.latest_analysis_request_id = request_id

        analysis_status = "分析完成。"
        if status_notes:
            analysis_status = f"{analysis_status} {'；'.join(status_notes)}"

        history_update, history_detail, history_status = self._history_panel_payload(
            selected_request_id=request_id,
            status_text="分析摘要已写入本地历史。",
        )

        return (
            emotion_result,
            rich_poem_interpretation,
            poet_image_np,
            guochao_response,
            guochao_image_np,
            analysis_status,
            history_update,
            history_detail,
            history_status,
        )

    def send_email_function(self, to_email, thoughts, user_photo_np, poet_image_np, poem, guochao_image_np, comfort):
        logger.info(f"请求发送邮件到: {to_email}")
        selected_request_id = self.latest_analysis_request_id

        if not to_email or "@" not in to_email or "." not in to_email:
            logger.warning("无效的邮箱地址。")
            history_update, history_detail, history_status = self._history_panel_payload(
                selected_request_id=selected_request_id,
                status_text="邮件未发送：邮箱地址无效。",
            )
            return "邮箱地址无效，请输入正确的邮箱。", history_update, history_detail, history_status

        try:
            success, message = send_analysis_email(
                to_email=to_email,
                thoughts=thoughts,
                user_photo_np=user_photo_np,
                poet_image_np=poet_image_np,
                poem=poem,
                guochao_image_np=guochao_image_np,
                comfort=comfort,
            )
            if success:
                logger.info(f"邮件发送成功: {message}")
                self._mark_mail_sent(selected_request_id)
                history_update, history_detail, history_status = self._history_panel_payload(
                    selected_request_id=selected_request_id,
                    status_text="邮件发送成功，历史状态已更新。",
                )
                return message, history_update, history_detail, history_status

            logger.error(f"邮件发送失败: {message}")
            history_update, history_detail, history_status = self._history_panel_payload(
                selected_request_id=selected_request_id,
                status_text="邮件发送失败，可直接重试，不影响当前结果。",
            )
            return message, history_update, history_detail, history_status
        except Exception as exc:
            logger.error(f"调用 send_analysis_email 时发生意外错误: {exc}", exc_info=True)
            history_update, history_detail, history_status = self._history_panel_payload(
                selected_request_id=selected_request_id,
                status_text="邮件发送异常，可重试。",
            )
            return f"发送邮件过程中发生意外错误: {str(exc)}", history_update, history_detail, history_status

# 实例化应用逻辑
app_logic = AppLogic()

# 将 AppLogic 实例的 process_analysis 方法传递给 create_ui
# ui.py 中的 main_app_func 将是 app_logic 实例
# 这样 ui.py 就可以调用 app_logic.send_email_function
iface = create_ui(app_logic)

def ensure_image_directories():
    """确保图像目录存在"""
    required_dirs = [
        app_path("images"),
        app_path("images", "tangsong"),
        app_path("images", "guochao")
    ]
    
    for directory in required_dirs:
        if not os.path.exists(directory):
            logger.info(f"创建目录: {directory}")
            os.makedirs(directory)
            
    # 检查图像文件是否存在
    tangsong_dir = app_path("images", "tangsong")
    guochao_dir = app_path("images", "guochao")
    tangsong_images = os.listdir(tangsong_dir) if os.path.exists(tangsong_dir) else []
    guochao_images = os.listdir(guochao_dir) if os.path.exists(guochao_dir) else []
    
    if not tangsong_images:
        logger.warning("唐宋八大家图片目录为空，将使用空白图片代替")
    
    if not guochao_images:
        logger.warning("国潮卡通形象目录为空，将使用空白图片代替")

if __name__ == "__main__":
    try:
        logger.info("="*50)
        logger.info("准备启动青少年情绪识别与文化心理疏导系统...")
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
            # 清理TTS引擎资源
            with tts_lock:
                if tts_engine is not None:
                    try:
                        logger.info("正在清理TTS引擎资源...")
                        tts_engine = None
                    except Exception as e:
                        logger.error(f"清理TTS引擎时出错: {e}")
    
    except Exception as e:
        logger.error(f"程序运行过程中出错: {e}")
        # 确保在任何情况下都清理TTS引擎
        with tts_lock:
            if tts_engine is not None:
                try:
                    logger.info("紧急情况：正在清理TTS引擎资源...")
                    tts_engine = None
                except:
                    pass
        sys.exit(1) 
