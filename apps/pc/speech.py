"""
语音情绪识别模块 - 处理用户语音输入并分析情绪
"""

import os
import numpy as np
import librosa
import logging

# 配置日志
logger = logging.getLogger(__name__)

def extract_audio_features(audio_path):
    """
    从音频文件中提取基本特征
    
    参数:
        audio_path: 音频文件路径
        
    返回:
        提取的特征字典
    """
    try:
        # 加载音频文件
        y, sr = librosa.load(audio_path, sr=None)
        
        # 提取基本特征
        # 1. 音频能量 - 情绪高涨时能量通常较高
        energy = np.sum(y**2) / len(y)
        
        # 2. 使用更安全的方式计算音高特征
        # 避免使用可能导致兼容性问题的librosa.piptrack
        f0, voiced_flag, voiced_probs = librosa.pyin(y, 
                                                    fmin=librosa.note_to_hz('C2'), 
                                                    fmax=librosa.note_to_hz('C7'),
                                                    sr=sr)
        pitch_mean = 0.0
        if voiced_flag.any():
            # 只考虑被识别为有声音的帧
            valid_pitches = f0[voiced_flag]
            if len(valid_pitches) > 0:
                pitch_mean = np.mean(valid_pitches)
        
        # 3. 音频速率 - 通过过零率估计
        zero_crossing_rate = np.mean(librosa.feature.zero_crossing_rate(y))
        
        # 4. 梅尔频率倒谱系数(MFCC) - 音色特征
        mfccs = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=13)
        mfcc_mean = np.mean(mfccs, axis=1)
        
        # 5. 音频持续时间
        duration = librosa.get_duration(y=y, sr=sr)
        
        # 返回特征字典
        features = {
            'energy': float(energy),
            'pitch_mean': float(pitch_mean),
            'zero_crossing_rate': float(zero_crossing_rate),
            'mfcc_mean': mfcc_mean.tolist(),
            'duration': float(duration)
        }
        
        return features
    
    except Exception as e:
        logger.error(f"提取音频特征时出错: {e}")
        return None

def analyze_speech_emotion(audio_path):
    """
    分析语音情绪
    
    参数:
        audio_path: 音频文件路径
        
    返回:
        检测到的情绪标签: happy, sad, angry, surprise, neutral, fear
    """
    if not audio_path or not os.path.exists(audio_path):
        logger.warning(f"音频文件不存在: {audio_path}")
        return None
    
    try:
        # 提取音频特征
        features = extract_audio_features(audio_path)
        
        if not features:
            return None
        
        # 基于特征的简单规则判断情绪
        energy = features['energy']
        pitch_mean = features['pitch_mean']
        zero_crossing_rate = features['zero_crossing_rate']
        
        # 简单规则判断
        # 这里使用简化的规则，实际应用中应该使用训练好的模型
        
        # 高能量 + 高音高 + 高过零率 通常表示快乐或惊讶
        if energy > 0.05 and pitch_mean > 200 and zero_crossing_rate > 0.1:
            if pitch_mean > 300:  # 非常高的音高可能表示惊讶
                return "surprise"
            else:
                return "happy"
        
        # 高能量 + 中等音高 + 高过零率 可能表示愤怒
        elif energy > 0.05 and 150 < pitch_mean < 250 and zero_crossing_rate > 0.08:
            return "angry"
        
        # 低能量 + 低音高 通常表示悲伤
        elif energy < 0.02 and pitch_mean < 200:
            return "sad"
        
        # 低能量 + 中等音高 + 低过零率 可能表示恐惧
        elif energy < 0.03 and 150 < pitch_mean < 250 and zero_crossing_rate < 0.06:
            return "fear"
        
        # 其他情况视为中性
        else:
            return "neutral"
    
    except Exception as e:
        logger.error(f"分析语音情绪时出错: {e}")
        return "neutral"  # 出错时默认返回中性 