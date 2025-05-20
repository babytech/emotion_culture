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
import pyttsx3
import platform

# 导入UI模块
from ui import create_ui

# 导入emotion模块中的函数和变量
from emotion import comfort_text, guochao_characters, detect_face_emotion, analyze_text_sentiment

# 导入语音情绪识别模块
from speech import analyze_speech_emotion

# 导入 email_utils 中的邮件发送函数
from email_utils import send_analysis_email, send_email

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

class AppLogic:
    def __init__(self):
        # 移除 SMTP 服务器配置，这些现在由 email_utils.py 通过 .env 文件处理
        # self.smtp_server = os.environ.get("SMTP_SERVER", "smtp.example.com")
        # self.smtp_port = int(os.environ.get("SMTP_PORT", 587))
        # self.smtp_sender_email = os.environ.get("SMTP_SENDER_EMAIL", "your_email@example.com")
        # self.smtp_sender_password = os.environ.get("SMTP_SENDER_PASSWORD", "your_password_or_app_key")
        pass # __init__ 目前不需要做任何事，但保留以备将来扩展

    def process_analysis(self, text_input, image_input, audio_input=None):
        """
        主分析函数：
        输入: 文本输入, 摄像头图像, 语音输入
        输出: 情绪文本结果, 诗词文字与解读, 文人静态图像, 国潮形象, 安抚文案
        """
        logger.info(f"接收到分析请求: 文本='{text_input}', 图像存在={image_input is not None}, 音频存在={audio_input is not None}")
        # 处理图像尺寸
        processed_image_input = None
        if image_input is not None:
            processed_image_input = process_image(image_input)
            
        # 面部表情识别
        face_emotion = None
        if processed_image_input is not None:
            face_emotion = detect_face_emotion(processed_image_input)
            logger.info(f"面部情绪识别结果: {face_emotion}")
            
        # 文本情感分析
        text_emotion = None
        if text_input:
            text_emotion = analyze_text_sentiment(text_input)
            if text_emotion:
                translated_text_emotion = culture_manager.translate_emotion(text_emotion)
                logger.info(f"文本情感分析结果 (原始): {text_emotion}, 翻译为: {translated_text_emotion}")
            else:
                logger.info(f"文本情感分析结果: 未能识别出明确情绪")
        
        # 语音情绪分析
        speech_emotion = None
        if audio_input:
            speech_emotion = analyze_speech_emotion(audio_input)
            logger.info(f"语音情感分析结果: {speech_emotion}")
        
        # 决定使用的情绪 - 优先级：面部 > 语音 > 文本
        chosen_emotion = face_emotion if face_emotion else None
        if not chosen_emotion and speech_emotion:
            chosen_emotion = speech_emotion
        if not chosen_emotion and text_emotion:
            chosen_emotion = text_emotion
        if not chosen_emotion:
            chosen_emotion = "neutral"
        logger.info(f"最终选择的情绪: {chosen_emotion}")
        
        # 诗词情绪响应
        poet, poem_text = get_poem_for_emotion(chosen_emotion)
        
        # 生成丰富的诗词解读
        rich_poem_interpretation = get_rich_poem_interpretation(poet, poem_text, chosen_emotion)
        
        # 获取文人静态图片
        poet_pil_image = get_poet_image(poet) # PIL Image
        poet_image_np = np.array(poet_pil_image) if poet_pil_image else None
        
        # 获取国潮卡通形象
        guochao_pil_image, character_name = get_guochao_image(chosen_emotion) # PIL Image, name
        guochao_image_np = np.array(guochao_pil_image) if guochao_pil_image else None
        
        # 获取情绪安抚文案
        comfort = comfort_text.get(chosen_emotion, comfort_text["neutral"])
        guochao_response = f"{character_name}：\n{comfort}"
        
        # 返回情绪识别结果文本（中文翻译）
        emotion_cn = culture_manager.translate_emotion(chosen_emotion)
        emotion_result = f"检测到的情绪: {emotion_cn}"

        # 统一组织所有需要播报的文本内容，作为一个完整的内容进行单次播报
        full_speech_text = ""
        if rich_poem_interpretation:
            full_speech_text += f"请听诗词与解读：\n{rich_poem_interpretation}\n\n"
        if guochao_response:
            full_speech_text += f"接下来，是来自国潮伙伴的慰藉：\n{guochao_response}"
        
        if full_speech_text:
            speak_text_in_thread(full_speech_text)
            
        return emotion_result, rich_poem_interpretation, poet_image_np, guochao_response, guochao_image_np

    def send_email_function(self, to_email, thoughts, user_photo_np, poet_image_np, poem, guochao_image_np, comfort):
        logger.info(f"请求发送邮件到: {to_email}")
        if not to_email or "@" not in to_email or "." not in to_email:
            logger.warning("AppLogic: 无效的邮箱地址。")
            return "邮箱地址无效，请输入正确的邮箱。"

        # 调用 email_utils 中的函数来处理邮件发送
        try:
            success, message = send_analysis_email(
                to_email=to_email,
                thoughts=thoughts,
                user_photo_np=user_photo_np,
                poet_image_np=poet_image_np,
                poem=poem,
                guochao_image_np=guochao_image_np,
                comfort=comfort
            )
            if success:
                logger.info(f"邮件发送成功，来自 email_utils 的消息: {message}")
            else:
                logger.error(f"邮件发送失败，来自 email_utils 的消息: {message}")
            return message
        except Exception as e:
            logger.error(f"调用 send_analysis_email 时发生意外错误: {e}", exc_info=True)
            return f"发送邮件过程中发生意外错误: {str(e)}"

# 实例化应用逻辑
app_logic = AppLogic()

# 将 AppLogic 实例的 process_analysis 方法传递给 create_ui
# ui.py 中的 main_app_func 将是 app_logic 实例
# 这样 ui.py 就可以调用 app_logic.send_email_function
iface = create_ui(app_logic)

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