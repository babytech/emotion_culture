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
        
        # 1. 预处理：高斯模糊去噪
        blurred_gray = cv2.GaussianBlur(gray, (5, 5), 0)
        
        # 2. 预处理：自适应直方图均衡化 (CLAHE) 以改善局部对比度和光照
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        enhanced_gray = clahe.apply(blurred_gray)
        
        # 加载各种级联分类器
        face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
        smile_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_smile.xml')
        eye_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_eye.xml')
        
        # 检测人脸 - 调整参数
        # scaleFactor: 图像在每个比例下的缩减量。较小的值（如1.05）会增加检测时间，但可能提高检测率。
        # minNeighbors: 每个候选矩形应该拥有的邻居数量。较高的值可以减少误报，但可能会漏检。
        # minSize: 最小可能对象大小。小于此值的对象将被忽略。
        faces = face_cascade.detectMultiScale(enhanced_gray, scaleFactor=1.05, minNeighbors=5, minSize=(30, 30))
        
        # 如果检测到人脸
        if len(faces) > 0:
            # 初始化情绪概率
            emotion_scores = {
                'happy': 0.0, # 使用浮点数以便更精细地调整
                'sad': 0.0,
                'angry': 0.0,
                'surprise': 0.0,
                'neutral': 0.1, # 默认给一点中性分
                'fear': 0.0
            }
            
            # 通常只处理最大的人脸
            (x, y, w, h) = max(faces, key=lambda item: item[2] * item[3])
            
            # 提取人脸区域
            roi_gray = enhanced_gray[y:y+h, x:x+w]
            # roi_color = image[y:y+h, x:x+w] # roi_color 似乎未使用，注释掉

            # 1. 检测笑容 - 主要与快乐情绪相关
            # minNeighbors 调整：较高的值意味着对笑容的检测更为严格
            smiles = smile_cascade.detectMultiScale(roi_gray, scaleFactor=1.7, minNeighbors=22, minSize=(25, 25))
            if len(smiles) > 0:
                emotion_scores['happy'] += 0.8 # 笑容是快乐的强特征
                emotion_scores['neutral'] -= 0.2 # 有笑容时减少中性分
            
            # 2. 检测眼睛 - 用于判断惊讶、恐惧
            # minNeighbors 调整：适当增加以减少误报
            eyes = eye_cascade.detectMultiScale(roi_gray, scaleFactor=1.1, minNeighbors=10, minSize=(20,20))
            eye_count = len(eyes)
            
            if eye_count >= 2:
                # 计算眼睛的平均睁开程度（近似，基于眼睛区域的高度相对于人脸高度）
                avg_eye_height_ratio = sum(eh / h for (_, ey, ew, eh) in eyes) / eye_count if eye_count > 0 else 0
                
                # 眼睛睁得很大可能是惊讶或恐惧
                if avg_eye_height_ratio > 0.15: # 阈值需要实验调整
                    emotion_scores['surprise'] += 0.6
                    emotion_scores['fear'] += 0.3 # 睁大眼睛也可能与恐惧有关
                elif avg_eye_height_ratio < 0.08 and len(smiles) == 0: # 眼睛较小且无笑容，可能偏向悲伤
                    emotion_scores['sad'] += 0.3

                # 眉毛区域分析 (简化版：分析眼睛上部区域的特征)
                # 我们假设眉毛在眼睛上方。取眼睛区域的上半部分作为眉毛区域的代理。
                # 这个区域的纹理和边缘可以间接反映眉毛状态。
                for (ex, ey, ew, eh) in eyes:
                    eyebrow_roi_y_start = max(0, ey - eh // 2) # 眼睛区域上方
                    eyebrow_roi_y_end = ey
                    eyebrow_region = roi_gray[eyebrow_roi_y_start:eyebrow_roi_y_end, ex:ex+ew]
                    if eyebrow_region.size > 0:
                        # 愤怒时眉毛通常会皱紧，导致边缘增多
                        edges_eyebrow = cv2.Canny(eyebrow_region, 50, 150)
                        eyebrow_edge_density = np.sum(edges_eyebrow > 0) / (eyebrow_region.size + 1e-6) # 避免除以零
                        if eyebrow_edge_density > 0.2: # 阈值需要实验调整
                            emotion_scores['angry'] += 0.5
                            emotion_scores['neutral'] -= 0.1
            elif eye_count == 0 and len(faces) > 0: # 没有检测到睁开的眼睛，但检测到了人脸
                emotion_scores['sad'] += 0.2 # 可能是闭眼或者非常悲伤
                emotion_scores['neutral'] += 0.1

            # 3. 嘴部区域分析 (当没有检测到笑容时)
            if len(smiles) == 0:
                # 近似嘴部区域（人脸下半部分）
                mouth_roi_y_start = y + h // 2
                mouth_region = enhanced_gray[mouth_roi_y_start:y+h, x:x+w]
                if mouth_region.size > 0:
                    # 悲伤时嘴部可能下撇，可以通过分析水平边缘来粗略判断
                    # 使用 Sobel 算子检测水平边缘
                    sobel_y = cv2.Sobel(mouth_region, cv2.CV_64F, 0, 1, ksize=5)
                    # 悲伤时嘴部下撇，可能导致强烈的负向垂直梯度（即水平边缘）
                    # 这里简化为分析梯度强度，更复杂的形状分析需要轮廓检测
                    mean_abs_sobel_y = np.mean(np.abs(sobel_y))
                    if mean_abs_sobel_y > 30: # 阈值需要实验调整
                        emotion_scores['sad'] += 0.4
                        emotion_scores['neutral'] -= 0.1
            
            # 4. 对愤怒情绪的进一步判断：结合眉毛和无笑容
            if emotion_scores['angry'] > 0.3 and len(smiles) == 0:
                emotion_scores['angry'] += 0.2 # 如果有皱眉迹象且无笑容，更可能是愤怒
            else: # 如果有笑容，则不太可能是愤怒
                emotion_scores['angry'] *= 0.5


            # 5. 光照和对比度作为辅助（主要用于区分中性）
            # 全局直方图均衡化已经尝试改善光照，这里不再重复计算强度和对比度，
            # 因为CLAHE处理后的图像对比度可能已经较高。
            # 主要通过其他特征是否显著来判断是否为中性。

            # 规范化情绪分数，使得总和为1 (可选，但有助于比较)
            # total_score = sum(emotion_scores.values())
            # if total_score > 0:
            #     for k in emotion_scores:
            #         emotion_scores[k] /= total_score
            
            # 如果所有其他特定情绪分数都很低，则更倾向于中性
            specific_emotion_scores = [emotion_scores[k] for k in emotion_scores if k != 'neutral']
            if max(specific_emotion_scores) < 0.3: # 如果没有明显的情绪特征
                emotion_scores['neutral'] += 0.3 # 增加中性情绪的权重
            
            # 找到分数最高的情绪
            # 如果最高分过低，或者与第二高分差距不大，也可以偏向 neutral
            sorted_emotions = sorted(emotion_scores.items(), key=lambda item: item[1], reverse=True)
            
            best_emotion, best_score = sorted_emotions[0]
            
            # 最终决策逻辑:
            # 如果最高分显著高于其他（特别是高于0.3的基础置信度），则采纳
            # 否则，如果中性分数也比较高，或者没有特别突出的情绪，则为中性
            if best_score < 0.35 and emotion_scores['neutral'] > 0.2: # 如果最高分不够自信，且中性有一定分数
                return 'neutral'
            if best_score < 0.25: # 如果最高分实在太低
                 return 'neutral'

            return best_emotion
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
    
    # 扩展词汇
    positive_words = [
        '高兴', '开心', '快乐', '愉快', '好', '棒', '喜欢', '爱', '惊喜', '幸运', '满足', '幸福', '完美', '顺利',
        '成就感', '成功', '太棒了', '棒极了', '赞', '优秀', '太好了', 
        '暖暖的', '温馨', '感动', '舒心', '甜甜的', '美好', '愉快' # 新增更多积极和温馨词汇
    ]
    negative_words = [
        '悲伤', '难过', '伤心', '痛苦', '不好', '讨厌', '厌恶', '恨', '失望', '郁闷', '烦恼', '糟糕', '倒霉', '失败', 
        '不开心', '不快乐', '不顺利', '不满意', '生气', '愤怒', '沮丧', '担忧', '害怕', '恐惧',
        '没考好', '考砸了', '考得不好', '成绩差', '不舒服'
    ]
    surprise_words = ['惊喜', '惊讶', '哇', '竟然', '居然']
    angry_words = ['生气', '愤怒', '气死', '怒', '火大']
    fear_words = ['害怕', '恐惧', '担心', '恐怖', '吓']

    text_lower = text.lower() # 转换为小写以匹配更多可能

    positive_count = sum(1 for word in positive_words if word in text_lower)
    negative_count = sum(1 for word in negative_words if word in text_lower)
    surprise_count = sum(1 for word in surprise_words if word in text_lower)
    angry_count = sum(1 for word in angry_words if word in text_lower)
    fear_count = sum(1 for word in fear_words if word in text_lower)
    
    # 调试信息，可以根据需要取消注释
    # print(f"文本: '{text_lower}'")
    # print(f"Positive: {positive_count}, Negative: {negative_count}, Surprise: {surprise_count}, Angry: {angry_count}, Fear: {fear_count}")

    # 优先处理更具体的情绪
    if angry_count > 0 and angry_count >= positive_count and angry_count >= negative_count:
        return 'angry'
    if fear_count > 0 and fear_count >= positive_count and fear_count >= negative_count:
        return 'fear' 
    # Surprise 通常与 happy 有重叠，如果同时有 happy 词，可能更偏向 happy
    if surprise_count > 0 and positive_count == 0 and negative_count == 0: # 纯粹的惊讶
        return 'surprise'
    
    # 然后是主要的积极和消极判断
    if positive_count > negative_count:
        # 如果有惊喜词，并且积极词占优，也可以认为是 happy (惊喜的一种)
        if surprise_count > 0:
             return 'happy' # 或者 'surprise' 如果希望更突出惊喜
        return 'happy'
    elif negative_count > positive_count:
        return 'sad' # "难过" 和 "有点难过" 都会落在这里
    elif surprise_count > 0: # 如果正负词一样多（比如都是0），但有惊喜词
        return 'surprise'
    else:
        return 'neutral'
