import cv2
import numpy as np

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
