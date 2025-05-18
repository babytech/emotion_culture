"""
简化版 - 儿童情绪识别与文化心理疏导系统
使用最少的依赖，主要功能包括：
- 简单的面部检测（使用OpenCV）
- 基于亮度的简单情绪估计
- 诗词响应
- 唐宋八大家Q版形象生成
- 简单的Gradio界面
"""

import os
import cv2
import numpy as np
import gradio as gr
import random
from PIL import Image

# 导入Q版卡通形象生成模块 - 优先使用静态图像生成，避免diffusers库的兼容性问题
CARTOON_ENABLED = True
try:
    # 优先使用静态图像生成模块
    import static_cartoon
    get_poet_image = static_cartoon.get_poet_image
    print("使用静态图像生成模块")
except ImportError as e:
    print(f"无法导入静态图像生成模块: {e}")
    # 如果静态模块导入失败，尝试导入diffusers模块
    try:
        from cartoon_generator import get_poet_image
        print("使用diffusers图像生成模块")
    except ImportError as e:
        print(f"无法导入卡通形象生成模块: {e}")
        CARTOON_ENABLED = False

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

# -------- 主函数 --------
def main_app(text_input, image_input):
    """
    简化版主函数：
    输入: 文本输入, 摄像头图像
    输出: 表情结果, 诗词文字, 文人卡通形象
    """
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
    poem = f"{poet}《{poem_text}》"
    
    # 获取文人卡通形象
    poet_image = None
    if CARTOON_ENABLED:
        try:
            # 生成与情绪匹配的卡通形象
            poet_image = get_poet_image(poet, chosen_emotion)
            # 将PIL图像转换为numpy数组用于Gradio展示
            poet_image = np.array(poet_image)
        except Exception as e:
            print(f"生成卡通形象失败: {e}")
            poet_image = np.ones((256, 256, 3), dtype=np.uint8) * 255
    else:
        # 如果卡通形象功能不可用，创建空白图像
        poet_image = np.ones((256, 256, 3), dtype=np.uint8) * 255
        cv2.putText(poet_image, f"{poet}", 
                   (20, 128), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 0), 2)
    
    # 在图像上显示情绪
    if image_input is not None:
        # 复制图像以不覆盖原图
        output_image = image_input.copy()
        # 添加文本
        cv2.putText(output_image, f"情绪: {chosen_emotion}", 
                   (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
    else:
        # 创建空白图像
        output_image = np.ones((300, 400, 3), dtype=np.uint8) * 255
        cv2.putText(output_image, f"情绪: {chosen_emotion}", 
                   (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
    
    return output_image, poem, poet_image

# -------- Gradio 前端界面 --------
iface = gr.Interface(
    fn=main_app,
    inputs=[
        gr.Textbox(label="请输入文本描述您的感受"),
        gr.Image(label="或使用摄像头")
    ],
    outputs=[
        gr.Image(label="情绪识别结果"),
        gr.Textbox(label="诗词回应"),
        gr.Image(label="文人卡通形象")
    ],
    title="儿童情绪识别与文化心理疏导系统",
    description="通过面部表情和文本分析儿童情绪，提供诗词和唐宋八大家Q版形象进行文化心理疏导。",
    examples=[
        ["我今天很开心", None],
        ["我感到非常悲伤", None],
        ["我现在很生气", None],
        ["我被吓到了", None]
    ]
)

if __name__ == "__main__":
    print("\n" + "="*50)
    print("准备启动Gradio界面，请稍等...")
    print("="*50 + "\n")
    # 强制刷新输出缓冲区
    import sys
    sys.stdout.flush()
    
    try:
        print("开始启动Gradio服务...")
        sys.stdout.flush()
        # 将server_port设为None让Gradio自动选择可用端口
        iface.launch(server_name="0.0.0.0", server_port=None, share=True)
        print("Gradio服务已启动！")
    except Exception as e:
        print(f"启动Gradio服务出错: {e}")
        sys.stdout.flush() 