"""
文化管理模块 - 处理诗词、文人图像及文化解读
"""

import os
import json
import random
from PIL import Image
import numpy as np
import logging # 添加logging模块导入

# 获取一个logger实例，可以与main.py中的logger配置联动，或独立配置
logger = logging.getLogger(__name__)

class CultureManager:
    def __init__(self):
        """初始化文化管理器，加载诗词数据"""
        self.poems_data = self._load_poems_data()
        self.emotion_translation = {
            "happy": "高兴",
            "sad": "悲伤",
            "angry": "生气",
            "surprise": "惊讶",
            "neutral": "平静",
            "fear": "恐惧"
        }
    
    def _load_poems_data(self):
        """从JSON文件加载诗词数据"""
        try:
            with open('poems.json', 'r', encoding='utf-8') as file:
                return json.load(file)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            print(f"加载诗词数据失败: {e}")
            # 返回一个基本的空结构，避免程序崩溃
            return {
                "happy": [],
                "sad": [],
                "angry": [],
                "surprise": [], 
                "neutral": [],
                "fear": []
            }
    
    def get_poem_for_emotion(self, emotion):
        """根据情绪随机返回对应诗人的诗词
        
        参数:
            emotion: 情绪类型 (happy, sad, angry, surprise, neutral, fear)
            
        返回:
            (诗人名字, 诗词内容)
        """
        # 如果情绪不在预定义列表中，使用neutral
        if emotion not in self.poems_data or not self.poems_data[emotion]:
            emotion = "neutral"
        
        # 从对应情绪的诗词列表中随机选择一首
        if self.poems_data[emotion]:
            poem_entry = random.choice(self.poems_data[emotion])
            return poem_entry.get("poet", "佚名"), poem_entry.get("text", "暂无诗词")
        else:
            # 如果没有找到任何诗词，返回默认值
            return "佚名", "暂无适合的诗词"
    
    def get_poet_image(self, poet_name):
        """从静态图片文件夹加载对应诗人的图片
        
        参数:
            poet_name: 诗人名字
            
        返回:
            PIL Image对象
        """
        try:
            # 构建诗人图片路径
            image_path = os.path.join("images", "tangsong", f"{poet_name}.png")
            
            # 如果文件存在则加载
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
                return img
            else:
                # print(f"找不到诗人 {poet_name} 的图片") # 改为日志记录
                logger.warning(f"图片未找到: 诗人 '{poet_name}'，路径: '{image_path}'。将使用空白图像。")
                # 返回一个空白图像
                return Image.new('RGB', (300, 300), color=(255, 255, 255))
        except Exception as e:
            # print(f"加载诗人图片出错: {e}") # 改为日志记录
            logger.error(f"加载诗人 '{poet_name}' 的图片时发生错误 (路径: '{image_path if 'image_path' in locals() else '未知'}'): {e}")
            return Image.new('RGB', (300, 300), color=(255, 255, 255))
    
    def translate_emotion(self, emotion):
        """将英文情绪类型翻译为中文
        
        参数:
            emotion: 情绪类型 (英文)
            
        返回:
            中文情绪名称
        """
        return self.emotion_translation.get(emotion, "未知情绪")
    
    def get_rich_poem_interpretation(self, poet, poem_text, emotion):
        """生成包含情绪解读、诗词含义和背景的丰富内容
        
        参数:
            poet: 诗人名字
            poem_text: 诗词内容
            emotion: 情绪类型
            
        返回:
            丰富的诗词解读文本
        """
        emotion_cn = self.translate_emotion(emotion)
        
        # 根据情绪提供不同风格的解读
        interpretations = {
            "happy": f"【{poet}】的这首诗展现了愉悦与欢快的情绪，非常适合当下您感到高兴的心情。\n\n{poem_text}\n\n这首诗表达了作者对美好事物的赞美和对生活的热爱，字里行间洋溢着积极向上的能量。",
            "sad": f"【{poet}】的这首诗中流露出忧伤与感伤的情绪，与您当前的心境有所共鸣。\n\n{poem_text}\n\n诗中表达了作者对人生无常的感叹，但也蕴含着对生活的深刻思考，让我们从悲伤中获得慰藉和智慧。",
            "angry": f"【{poet}】的这首诗中蕴含着强烈的情感和对不公的抗争精神，或许能与您当前的情绪产生共鸣。\n\n{poem_text}\n\n诗中展现了面对困境时的不屈与坚韧，告诉我们愤怒也可以是一种积极的力量。",
            "surprise": f"【{poet}】的这首诗中包含着令人惊叹的意象和新奇的发现，与您当前惊讶的心情相呼应。\n\n{poem_text}\n\n诗人以独特的视角观察世界，捕捉那些常人忽略的奇妙瞬间，让我们对生活充满好奇和探索欲。",
            "neutral": f"【{poet}】的这首诗展现了平和与沉稳的气质，适合您当前平静的心境。\n\n{poem_text}\n\n诗中流露出作者对生活的细致观察和深入思考，引导我们在平静中感受生活的丰富多彩。",
            "fear": f"【{poet}】的这首诗中流露出面对未知的勇气，或许能给予您当前心境一些启示。\n\n{poem_text}\n\n诗中描绘了面对困难和恐惧时的心理历程，告诉我们即使在黑暗中也能找到前行的力量。"
        }
        
        # 获取对应情绪的解读，如果没有则使用通用解读
        interpretation = interpretations.get(emotion, f"【{poet}】为您带来的诗词：\n\n{poem_text}\n\n这首诗展现了中国传统文化的深厚底蕴，值得我们细细品味。")
        
        # 添加通用的结束语
        conclusion = "\n\n诗词是中华文化的瑰宝，让我们通过古人的智慧，更好地理解自己的情感，获得精神的慰藉与启迪。"
        
        return interpretation + conclusion