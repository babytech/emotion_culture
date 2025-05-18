"""
简化版 - 儿童情绪识别与文化心理疏导系统
使用最少的依赖，主要功能包括：
- 简单的面部检测（使用OpenCV）
- 基于亮度的简单情绪估计
- 诗词响应
- 唐宋八大家静态形象显示
- 简单的Gradio界面
"""

import os
import cv2
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

# -------- 情绪翻译字典 --------
emotion_translation = {
    "happy": "高兴",
    "sad": "悲伤",
    "angry": "愤怒",
    "surprise": "惊讶",
    "neutral": "平静",
    "fear": "恐惧"
}

# -------- 诗词背景信息字典 --------
poem_background = {
    "韩愈": {
        "野老与人争席罢，海鸥何事更相疑。": "这是《潮州西湖寄谢三十五使君》中的诗句，描述了人与自然和谐相处的景象，表达了作者愉悦的心情和对简单、自然生活的向往。韩愈被贬潮州时所作，虽身处逆境却保持乐观。",
        "云横秦岭家何在？雪拥蓝关马不前。": "这是《左迁至蓝关示侄孙湘》中的诗句，描述了韩愈被贬谪时的凄凉处境，表达了对家人的思念和对前途的担忧。写于唐宪宗元和十四年（819年）。",
        "昨夜星辰昨夜风，画楼西畔桂堂东。": "这是《题张十一旅舍》中的诗句，表达了诗人对友人的思念之情和惊喜之感。韩愈写这首诗时可能是在长安任职期间与友人相遇的情景。",
        "劝君更尽一杯酒，西出阳关无故人。": "这实际上是王维《送元二使安西》中的诗句，描述了送别友人时的不舍和对远行者的美好祝愿。唐代边塞诗的代表作之一。",
        "欲为圣明除弊事，肯将衰朽惜残年！": "这是《论史》中的诗句，表达了诗人忧国忧民、为国尽忠的决心和勇气。韩愈任职谏官时期所作，反映了他的爱国情怀。",
        "山石荦确行径微，黄昏到寺蝙蝠飞。": "这是《山石》中的诗句，描述了黄昏时分行走在山间小路上的情景，表达了诗人面对自然的敬畏之心。可能是韩愈被贬潮州途中所作。"
    },
    "柳宗元": {
        "好风胧月清明夜，碧砌红轩刺史家。": "这是《与浩初上人同看山寄京华亲故》中的诗句，描绘了风和月明的清明夜景，表达了作者对友人的思念和对美好生活的向往。作于柳宗元贬谪永州时期。",
        "登高壮观天地间，大江茫茫去不还。": "这是《登柳州城楼寄漳汀封连四州》中的诗句，描述了诗人登高远望时的感受，表达了对远方友人的思念和对人生无常的感悟。柳宗元晚年被贬柳州时所作。",
        "千山鸟飞绝，万径人踪灭。": "这是《江雪》中的诗句，描绘了冬日江边的寂静景象，表达了诗人内心的孤独和超脱。柳宗元贬居永州时所作，是其代表作之一。",
        "孤舟蓑笠翁，独钓寒江雪。": "这是《江雪》后两句，与前两句合为一首经典绝句，描绘了一位老渔翁在雪中独钓的画面，意境深远，暗示诗人的精神追求和人生态度。",
        "朱门酒肉臭，路有冻死骨。": "这是《寒食》中的诗句，是对社会不公的直接批判，表达了诗人对社会现实的忧愤和对底层百姓的同情。柳宗元贬居时期所作。",
        "惊风乱飐芙蓉水，密雨斜侵薜荔墙。": "出自《酬曹侍御过象县见寄》，描述了风雨中的自然景象，表达了诗人在贬谪生活中的复杂情感。柳宗元在永州任职时期所写。"
    },
    "欧阳修": {
        "把酒祝东风，且共从容。": "出自《採桑子·把酒祝东风》，表达了诗人豁达开朗的人生态度和对美好生活的向往。欧阳修晚年在颍州任职时所作。",
        "南朝四百八十寺，多少楼台烟雨中。": "出自《江南好》，描绘了江南烟雨朦胧中的古寺景象，抒发了对历史兴衰的感慨。欧阳修任扬州通判时所作。",
        "雨霁风光，春山如黛。": "出自《阮郎归·南楼别后》，描绘了雨后春山如黛的美丽景色，表达了对曾经欢聚之地的留恋。欧阳修任翰林学士时期创作。",
        "平芜尽处是春山，行人更在春山外。": "出自《踏莎行·候馆梅残》，描绘了春天旅途中的景色，表达了诗人的思乡之情。欧阳修贬谪时期所作。",
        "漫卷诗书喜欲狂，恍如身入名山游。": "出自《读书》，表达了诗人读书时的喜悦和沉醉之情。欧阳修好学不倦，这首诗反映了他对知识的热爱。"
    }
}

# -------- 情绪安抚文案 --------
comfort_text = {
    "happy": "看到你这么开心，真是太好了！快乐是生活中最美好的礼物，希望你能一直保持这份愉悦的心情。记得把这份快乐分享给身边的每一个人哦！",
    "sad": "每个人都会有情绪低落的时候，这很正常。请记住，悲伤只是暂时的，就像下雨过后总会有彩虹。如果感到难过，不妨深呼吸几次，或者和亲人朋友聊聊天，分享你的感受会让你感觉好些。",
    "angry": "生气的时候，不妨先停下来，数到十，深呼吸几次。愤怒是正常的情绪，但不要让它控制你。你可以尝试换个角度思考问题，或者做些你喜欢的事情来转移注意力，等心情平静下来再处理让你生气的事情。",
    "surprise": "惊奇是发现新事物的开始！保持这种好奇心和探索精神，世界会向你展示更多奇妙的一面。每一次的惊讶都是一次新的体验和成长的机会。",
    "neutral": "平静的心态是一种智慧。在这种状态下，你可以更清晰地思考和感受世界。享受这份宁静，它能帮助你更好地应对生活中的各种挑战。",
    "fear": "害怕是自我保护的一种方式，每个人都会感到害怕。面对恐惧，可以尝试把注意力放在呼吸上，告诉自己\"我很安全\"。记住，勇敢不是没有恐惧，而是尽管害怕仍然前行。如果需要，随时寻求家人或朋友的帮助。"
}

# -------- 国潮卡通形象匹配 --------
guochao_characters = {
    "happy": ["国潮女孙小美", "国潮男小帅", "国潮女红金锁", "国潮女如花"],
    "sad": ["国潮女绿金锁", "国潮男知书", "国潮女闭月", "国潮男修花"],
    "angry": ["国潮男淘气", "国潮女钱小美", "国潮男顽皮"],
    "surprise": ["国潮女兰亭妹", "国潮女兰花妹", "国潮女拨浪鼓"],
    "neutral": ["国潮男达理", "国潮女新疆妹", "国潮女似玉"],
    "fear": ["国潮女绿金锁", "国潮男知书", "国潮女闭月"]
}

# -------- 面部表情情绪识别 --------
def detect_face_emotion(image):
    """
    使用OpenCV检测人脸和面部特征来判断情绪，结合多种特征分析。
    """
    try:
        if image is None:
            return "neutral"
        
        # 转换为灰度图
        gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
        
        # 对图像进行均衡化处理，增强对比度
        equalized_gray = cv2.equalizeHist(gray)
        
        # 加载各种级联分类器
        face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
        smile_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_smile.xml')
        eye_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_eye.xml')
        
        # 检测人脸
        faces = face_cascade.detectMultiScale(equalized_gray, 1.1, 4)
        
        # 如果检测到人脸
        if len(faces) > 0:
            # 初始化情绪概率
            emotion_scores = {
                'happy': 0,
                'sad': 0,
                'angry': 0,
                'surprise': 0,
                'neutral': 0,
                'fear': 0
            }
            
            for (x, y, w, h) in faces:
                # 提取人脸区域
                roi_gray = equalized_gray[y:y+h, x:x+w]
                roi_color = image[y:y+h, x:x+w]
                
                # 计算人脸区域的直方图特征
                hist = cv2.calcHist([roi_gray], [0], None, [256], [0, 256])
                hist_norm = hist / hist.sum()  # 归一化直方图
                
                # 1. 检测笑容 - 直接与快乐情绪相关
                smiles = smile_cascade.detectMultiScale(roi_gray, 1.8, 20)
                if len(smiles) > 0:
                    # 根据笑容大小和位置给予快乐情绪分数
                    smile_size = sum(w*h for (_, _, w, h) in smiles)
                    smile_ratio = smile_size / (roi_gray.shape[0] * roi_gray.shape[1])
                    emotion_scores['happy'] += 0.7 * min(smile_ratio * 10, 1.0)
                
                # 2. 检测眼睛 - 用于判断惊讶、恐惧和悲伤
                eyes = eye_cascade.detectMultiScale(roi_gray, 1.1, 3)
                eye_count = len(eyes)
                
                if eye_count >= 2:
                    # 计算眼睛大小和位置
                    eye_sizes = [w*h for (_, _, w, h) in eyes]
                    avg_eye_size = sum(eye_sizes) / len(eye_sizes)
                    eye_size_ratio = avg_eye_size / (roi_gray.shape[0] * roi_gray.shape[1])
                    
                    # 眼睛大意味着可能是惊讶
                    if eye_size_ratio > 0.03:  # 阈值需要根据实际情况调整
                        emotion_scores['surprise'] += 0.6
                    
                    # 上半部区域（眉毛和眼睛区域）的分析 - 用于检测愤怒
                    upper_half = roi_gray[0:int(h/2), :]
                    
                    # 计算上半部分的边缘密度，愤怒时眉头会紧皱
                    edges = cv2.Canny(upper_half, 100, 200)
                    edge_density = np.sum(edges > 0) / (upper_half.shape[0] * upper_half.shape[1])
                    
                    # 边缘密度高意味着眉头可能皱起，愤怒的迹象
                    if edge_density > 0.1:  # 阈值需要根据实际情况调整
                        emotion_scores['angry'] += 0.5
                
                # 3. 嘴部区域分析 - 用于判断悲伤和中性
                mouth_region = roi_gray[int(2*h/3):h, :]
                
                # 计算嘴部区域的梯度
                sobelx = cv2.Sobel(mouth_region, cv2.CV_64F, 1, 0, ksize=3)
                sobely = cv2.Sobel(mouth_region, cv2.CV_64F, 0, 1, ksize=3)
                abs_sobelx = cv2.convertScaleAbs(sobelx)
                abs_sobely = cv2.convertScaleAbs(sobely)
                grad = cv2.addWeighted(abs_sobelx, 0.5, abs_sobely, 0.5, 0)
                
                # 计算嘴部区域的梯度强度
                mouth_grad_mean = np.mean(grad)
                
                # 如果没有笑容且嘴部梯度强度高，可能是悲伤
                if len(smiles) == 0 and mouth_grad_mean > 20:
                    emotion_scores['sad'] += 0.4
                
                # 4. 整体人脸暗度和对比度分析 - 作为辅助判断，但不是主要依据
                avg_intensity = np.mean(roi_gray)
                contrast = np.std(roi_gray)
                
                # 如果其他情绪得分都不高，使用强度和对比度作为辅助
                if max(emotion_scores.values()) < 0.3:
                    if contrast > 60:  # 高对比度可能表示情绪波动
                        emotion_scores['neutral'] += 0.2
                    else:
                        emotion_scores['neutral'] += 0.4
            
            # 如果所有情绪分数都很低，增加中性情绪的权重
            if max(emotion_scores.values()) < 0.3:
                emotion_scores['neutral'] = 0.5
            
            # 根据情绪分数确定最终情绪
            max_emotion = max(emotion_scores.items(), key=lambda x: x[1])
            if max_emotion[1] > 0:
                return max_emotion[0]
            else:
                return 'neutral'
        else:
            return 'neutral'  # 如果没有检测到人脸，返回中性
    except Exception as e:
        print(f"面部情绪识别错误: {e}")
        return 'neutral'

# -------- 文本情感分析 --------
def analyze_text_sentiment(text):
    """
    极简文本情感分析 - 基于关键词匹配
    """
    if not text:
        return None
    
    positive_words = ['高兴', '开心', '快乐', '愉快', '好', '棒', '喜欢', '爱']
    negative_words = ['悲伤', '难过', '伤心', '痛苦', '不好', '讨厌', '厌恶', '恨']
    
    positive_count = sum(1 for word in positive_words if word in text)
    negative_count = sum(1 for word in negative_words if word in text)
    
    if positive_count > negative_count:
        return 'happy'
    elif negative_count > positive_count:
        return 'sad'
    else:
        return 'neutral'

# -------- 诗词情绪响应库 --------
poem_dict = {
    "happy": {
        "韩愈": "野老与人争席罢，海鸥何事更相疑。",
        "柳宗元": "好风胧月清明夜，碧砌红轩刺史家。",
        "欧阳修": "把酒祝东风，且共从容。",
        "苏洵": "烟消日出不见人，欸乃一声山水绿。",
        "苏轼": "竹外桃花三两枝，春江水暖鸭先知。",
        "苏辙": "细草微风岸，危樯独夜舟。",
        "王安石": "一水护田将绿绕，两山排闼送青来。",
        "曾巩": "百啭千声随意移，山花红紫树高低。"
    },
    "sad": {
        "韩愈": "云横秦岭家何在？雪拥蓝关马不前。",
        "柳宗元": "登高壮观天地间，大江茫茫去不还。",
        "欧阳修": "南朝四百八十寺，多少楼台烟雨中。",
        "苏洵": "此地别燕丹，壮士发冲冠。",
        "苏轼": "明月几时有？把酒问青天。",
        "苏辙": "夜深人物不相管，我独形影相嬉娱。",
        "王安石": "春风又绿江南岸，明月何时照我还？",
        "曾巩": "涧影见松竹，潭香闻芰荷。"
    },
    "surprise": {
        "韩愈": "昨夜星辰昨夜风，画楼西畔桂堂东。",
        "柳宗元": "千山鸟飞绝，万径人踪灭。",
        "欧阳修": "雨霁风光，春山如黛。",
        "苏洵": "疏星淡月，照远客孤舟。",
        "苏轼": "黑云翻墨未遮山，白雨跳珠乱入船。",
        "苏辙": "回首东南望，春风几万里。",
        "王安石": "不畏浮云遮望眼，自缘身在最高层。",
        "曾巩": "海浪如云去却回，北风吹起数声雷。"
    },
    "neutral": {
        "韩愈": "劝君更尽一杯酒，西出阳关无故人。",
        "柳宗元": "孤舟蓑笠翁，独钓寒江雪。",
        "欧阳修": "平芜尽处是春山，行人更在春山外。",
        "苏洵": "晚雨纤纤变玉霙，小庵高卧有余清。",
        "苏轼": "水光潋滟晴方好，山色空蒙雨亦奇。",
        "苏辙": "水流无限似侬愁，暮雨朝云去不休。",
        "王安石": "飞阁连云带雨晴，青冥缥缈与心清。",
        "曾巩": "四顾山光接水光，凭栏十里芰荷香。"
    },
    "angry": {
        "韩愈": "欲为圣明除弊事，肯将衰朽惜残年！",
        "柳宗元": "朱门酒肉臭，路有冻死骨。",
        "欧阳修": "漫卷诗书喜欲狂，恍如身入名山游。",
        "苏洵": "千锤万凿出深山，烈火焚烧若等闲。",
        "苏轼": "人生到处知何似，应似飞鸿踏雪泥。",
        "苏辙": "汉水波浪远，襄阳城郭新。",
        "王安石": "当时迦叶无尘染，何事阌乡有土思。",
        "曾巩": "磻溪向我发清浊，洞庭从来见涨枯。"
    },
    "fear": {
        "韩愈": "山石荦确行径微，黄昏到寺蝙蝠飞。",
        "柳宗元": "惊风乱飐芙蓉水，密雨斜侵薜荔墙。",
        "欧阳修": "夜闻归雁生乡思，病入新年感物华。",
        "苏洵": "雷霆入地建溪险，星斗逼人梨岭高。",
        "苏轼": "安能摧眉折腰事权贵，使我不得开心颜。",
        "苏辙": "暮霭生深树，寒声满浅滩。",
        "王安石": "谁言寸草心，报得三春晖。",
        "曾巩": "岩扉松径长寂寥，昼阴如夜空山道。"
    }
}

def get_poem_for_emotion(emotion):
    """根据情绪随机返回对应诗人的诗词"""
    emotion_poems = poem_dict.get(emotion, poem_dict["neutral"])
    poet, poem = random.choice(list(emotion_poems.items()))
    return poet, poem

# -------- 静态图片加载函数 --------
def get_poet_image(poet_name):
    """
    从静态图片文件夹加载对应诗人的图片并缩小为原来的一半大小
    """
    try:
        image_path = os.path.join("images", "tangsong", f"{poet_name}.png")
        if os.path.exists(image_path):
            img = Image.open(image_path)
            # 缩小为原来的一半大小
            width, height = img.size
            try:
                # 尝试使用LANCZOS（新版Pillow中可能已重命名）
                img = img.resize((width // 2, height // 2), Image.LANCZOS)
            except AttributeError:
                # 如果LANCZOS不可用，尝试使用Lanczos或BICUBIC
                try:
                    img = img.resize((width // 2, height // 2), Image.Resampling.LANCZOS)
                except AttributeError:
                    img = img.resize((width // 2, height // 2), Image.BICUBIC)
            return img
        else:
            print(f"找不到{poet_name}的图片")
            # 创建一个带有诗人名字的空白图片
            blank_img = Image.new('RGB', (300, 300), color=(255, 255, 255))
            return blank_img
    except Exception as e:
        print(f"加载诗人图片出错: {e}")
        return Image.new('RGB', (300, 300), color=(255, 255, 255))

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
    # 情绪解读
    emotion_cn = emotion_translation.get(emotion, emotion)
    emotion_intro = f"检测到您当前的情绪是：{emotion_cn}。"
    
    # 获取诗词背景信息
    background = ""
    if poet in poem_background and poem_text in poem_background[poet]:
        background = poem_background[poet][poem_text]
    else:
        background = f"这是{poet}的一首经典诗作，意境优美，耐人寻味。"
    
    # 组合完整解读
    rich_interpretation = f"{emotion_intro}\n\n{poet}的诗句「{poem_text}」\n\n{background}"
    
    return rich_interpretation

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
def main_app(text_input, image_input):
    """
    简化版主函数：
    输入: 文本输入, 摄像头图像
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
        print(f"文本情感分析结果: {text_emotion}")
    
    # 决定使用的情绪
    chosen_emotion = face_emotion if face_emotion else None
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
    emotion_cn = emotion_translation.get(chosen_emotion, chosen_emotion)
    emotion_result = f"检测到的情绪: {emotion_cn}"
    
    return emotion_result, rich_poem_interpretation, poet_image, guochao_response, guochao_image

# -------- 国风CSS样式 --------
css = """
:root {
    --main-color: #e60000;
    --secondary-color: #ffd700;
    --text-color: #333;
    --background-color: #f5f5f5;
    --border-color: #d4a017;
}

body {
    background-color: var(--background-color);
    background-image: url('https://img.freepik.com/free-vector/chinese-cloud-pattern-background-red_53876-135689.jpg');
    background-size: cover;
    background-repeat: no-repeat;
    background-attachment: fixed;
    font-family: 'Ma Shan Zheng', cursive, sans-serif;
}

.gradio-container {
    max-width: 95% !important;
    margin: 0 auto;
    background-color: rgba(255, 255, 255, 0.9);
    border-radius: 15px;
    box-shadow: 0 4px 30px rgba(0, 0, 0, 0.1);
    backdrop-filter: blur(5px);
    border: 2px solid var(--border-color);
    padding: 20px;
}

h1 {
    color: var(--main-color) !important;
    text-align: center;
    font-size: 2.5em !important;
    margin-bottom: 20px !important;
    text-shadow: 2px 2px 4px rgba(0, 0, 0, 0.2);
    border-bottom: 2px solid var(--border-color);
    padding-bottom: 10px;
}

button {
    background-color: var(--main-color) !important;
    color: white !important;
    border: none !important;
    border-radius: 5px !important;
    padding: 8px 16px !important;
    cursor: pointer !important;
    transition: all 0.3s ease !important;
    font-weight: bold !important;
    box-shadow: 0 2px 5px rgba(0, 0, 0, 0.2) !important;
}

button:hover {
    background-color: #b30000 !important;
    transform: translateY(-2px) !important;
    box-shadow: 0 4px 8px rgba(0, 0, 0, 0.3) !important;
}

.label {
    color: var(--main-color) !important;
    font-weight: bold !important;
    font-size: 1.1em !important;
    margin-bottom: 5px !important;
}

input, textarea {
    border: 1px solid var(--border-color) !important;
    border-radius: 5px !important;
    padding: 8px !important;
    background-color: rgba(255, 255, 255, 0.9) !important;
}

.image-preview {
    border: 3px solid var(--border-color) !important;
    border-radius: 10px !important;
    overflow: hidden !important;
    box-shadow: 0 4px 8px rgba(0, 0, 0, 0.2) !important;
}

.textbox-container {
    border: 1px solid var(--border-color) !important;
    border-radius: 10px !important;
    padding: 10px !important;
    background-color: #fffaf0 !important;
    box-shadow: 0 2px 5px rgba(0, 0, 0, 0.1) !important;
}

.footer {
    text-align: center;
    margin-top: 20px;
    color: var(--text-color);
    font-size: 0.9em;
}

/* 动画效果 */
@keyframes fadeIn {
    from { opacity: 0; }
    to { opacity: 1; }
}

.fade-in {
    animation: fadeIn 1s ease-in-out;
}

/* 添加一些中国传统元素的装饰 */
.chinese-pattern {
    background-image: url('https://png.pngtree.com/png-vector/20190726/ourlarge/pngtree-chinese-style-border-png-image_1610935.jpg');
    background-size: contain;
    background-repeat: repeat-x;
    height: 30px;
    margin: 20px 0;
}
"""

# -------- Gradio 前端界面 --------
with gr.Blocks(title="儿童情绪识别与文化心理疏导系统", css=css) as iface:
    with gr.Row(elem_classes="fade-in"):
        gr.Markdown("# 儿童情绪识别与文化心理疏导系统")
    
    gr.HTML('<div class="chinese-pattern"></div>')
    gr.Markdown("通过面部表情和文本分析儿童情绪，提供诗词和文化形象进行心理疏导。")
    
    with gr.Row():
        # 左侧栏 - 输入区域
        with gr.Column(scale=1):
            text_input = gr.Textbox(label="请输入文本描述您的感受", elem_classes="textbox-container")
            
            # 示例放在文本框下方
            gr.Examples(
                examples=[
                    ["我今天很开心"],
                    ["我感到非常悲伤"],
                    ["我现在很生气"],
                    ["我被吓到了"]
                ],
                inputs=[text_input]
            )
            
            image_input = gr.Image(label="或使用摄像头", elem_classes="image-preview")
            submit_btn = gr.Button("提交", variant="primary")
            # 情绪识别结果显示在左侧提交按钮下方
            emotion_output = gr.Textbox(label="情绪识别结果", elem_classes="textbox-container")
        
        # 右侧栏 - 输出区域
        with gr.Column(scale=2):
            # 上方两个图像并排
            with gr.Row():
                poet_image_output = gr.Image(label="文人静态形象", elem_classes="image-preview")
                guochao_image_output = gr.Image(label="国潮卡通形象", elem_classes="image-preview")
            
            # 下方两个文本框
            with gr.Row():
                with gr.Column():
                    poem_output = gr.Textbox(label="诗词回应与解读", lines=8, elem_classes="textbox-container")
                with gr.Column():
                    comfort_output = gr.Textbox(label="安抚文案", lines=8, elem_classes="textbox-container")
    
    gr.HTML('<div class="chinese-pattern"></div>')
    gr.HTML('<div class="footer">© 2023 儿童情绪识别与文化心理疏导系统 | 传统文化与现代科技的融合</div>')
    
    # 设置提交按钮功能
    submit_btn.click(
        fn=main_app,
        inputs=[text_input, image_input],
        outputs=[emotion_output, poem_output, poet_image_output, comfort_output, guochao_image_output]
    )

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