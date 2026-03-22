import pyttsx3
import platform

def run_tts_test():
    print("开始 TTS 测试...")
    engine = None # 初始化为 None
    try:
        print("尝试初始化 TTS 引擎 (默认驱动)...")
        engine = pyttsx3.init()
        # engine.proxy 存在，但 _driverName 可能不存在
        # 我们可以尝试获取 driverName 通过 engine.getProperty('driver') 但这可能也不通用
        # 所以我们主要依赖 platform.system() 进行平台特定处理
        system_platform = platform.system()
        print(f"当前操作系统: {system_platform}")
        if system_platform == 'Darwin':
             print("检测到 macOS。pyttsx3 通常使用 NSSpeechSynthesizer (nsss)。")
        elif system_platform == 'Windows':
             print("检测到 Windows。pyttsx3 通常使用 SAPI5。")
        elif system_platform == 'Linux':
             print("检测到 Linux。pyttsx3 通常使用 eSpeak。")
        else:
            print(f"未知操作系统平台: {system_platform}")

        voices = engine.getProperty('voices')
        print(f"\n找到 {len(voices)} 个可用语音:")
        if not voices:
            print("警告: 未找到任何可用语音。请检查您的 TTS 引擎是否正确安装和配置。")
            print("在 macOS 上，请检查 系统设置 -> 辅助功能 -> 语音内容 -> 系统声音 是否有可用的声音，并确保已下载。")
            print("在 Windows 上，请检查 控制面板 -> 语音识别 -> 文本到语音转换 是否有可用的声音。")
            print("在 Linux 上，请确保 eSpeak 或其他兼容 TTS 引擎已安装。")
            return # 如果没有语音，后续测试无意义

        for i, voice in enumerate(voices):
            try:
                lang_str = ", ".join(voice.languages) if hasattr(voice, 'languages') and voice.languages else "N/A"
                gender_str = voice.gender if hasattr(voice, 'gender') and voice.gender else "N/A"
                age_str = voice.age if hasattr(voice, 'age') and voice.age else "N/A"
                print(f"  语音 {i}: ID='{voice.id}'")
                print(f"    名称: {voice.name}")
                print(f"    性别: {gender_str}")
                print(f"    语言: {lang_str}")
                print(f"    年龄: {age_str}")
            except Exception as e_voice_attr:
                # 即使某些属性获取失败，至少打印ID和名称
                voice_id_str = getattr(voice, 'id', '[ID不可读]')
                voice_name_str = getattr(voice, 'name', '[名称不可读]')
                print(f"  语音 {i}: ID='{voice_id_str}', 名称: '{voice_name_str}' (获取部分详细属性失败: {e_voice_attr})")
        print("-"*30) # 分隔符，方便查看语音列表结束

        chosen_voice_name = "未选择"
        female_voice_id = None

        # 新增：首先尝试精确查找名为 "月" 或 "Yue" 的语音
        preferred_voice_names = ["月", "Yue"]
        print(f"\n尝试精确查找首选语音 (名称包含: {', '.join(preferred_voice_names)})... ")
        for voice in voices:
            if hasattr(voice, 'name') and voice.name:
                for preferred_name in preferred_voice_names:
                    if preferred_name.lower() in voice.name.lower():
                        female_voice_id = voice.id
                        chosen_voice_name = voice.name
                        print(f"  => 精确匹配成功: 找到指定语音 '{chosen_voice_name}' (ID: {female_voice_id})")
                        break # 找到一个匹配就停止内层循环
            if female_voice_id: # 如果内层循环已找到，则停止外层循环
                break
        
        if female_voice_id:
            print(f"首选语音 '{chosen_voice_name}' 已找到并选中。")
        else:
            print("未能通过精确名称查找到首选语音 '月' 或 'Yue'。继续通用选择逻辑...")
            # ---- 原有的通用女性和中文语音选择逻辑 ----
            for voice in voices:
                name_lower = voice.name.lower() if hasattr(voice, 'name') and voice.name else ""
                is_female_by_name = "female" in name_lower or "女孩" in name_lower or "女声" in name_lower
                is_female_by_gender = hasattr(voice, 'gender') and voice.gender and voice.gender.lower() == 'female'
                is_female = is_female_by_name or is_female_by_gender

                supports_chinese_by_lang = hasattr(voice, 'languages') and voice.languages and any('zh' in lang.lower() for lang in voice.languages)
                supports_chinese_by_name = "ting-ting" in name_lower or "mei-jia" in name_lower or "sin-ji" in name_lower
                supports_chinese = supports_chinese_by_lang or supports_chinese_by_name

                if is_female and supports_chinese:
                    female_voice_id = voice.id
                    chosen_voice_name = voice.name
                    print(f"  => 通用选择：找到支持中文的女性语音 '{chosen_voice_name}' (ID: {female_voice_id})")
                    break
            
            if not female_voice_id:
                for voice in voices:
                    name_lower = voice.name.lower() if hasattr(voice, 'name') and voice.name else ""
                    is_female_by_name = "female" in name_lower or "女孩" in name_lower or "女声" in name_lower
                    is_female_by_gender = hasattr(voice, 'gender') and voice.gender and voice.gender.lower() == 'female'
                    is_female = is_female_by_name or is_female_by_gender
                    if is_female:
                        female_voice_id = voice.id
                        chosen_voice_name = voice.name
                        print(f"  => 通用选择：找到女性语音 '{chosen_voice_name}' (ID: {female_voice_id}) (可能非中文)")
                        break
            
            if not female_voice_id and system_platform == 'Darwin':
                mac_chinese_voices = ["ting-ting", "mei-jia", "sin-ji"]
                for voice_name_part in mac_chinese_voices:
                    for voice in voices:
                        name_lower = voice.name.lower() if hasattr(voice, 'name') and voice.name else ""
                        if voice_name_part in name_lower:
                            female_voice_id = voice.id
                            chosen_voice_name = voice.name
                            print(f"  => macOS 特定查找：找到可能为中文的语音 '{chosen_voice_name}' (ID: {female_voice_id})")
                            break
                    if female_voice_id:
                        break
            
            if not female_voice_id and len(voices) > 1:
                female_voice_id = voices[1].id # Fallback to the second voice
                chosen_voice_name = voices[1].name if hasattr(voices[1], 'name') else '[未知名称]'
                print(f"  => 后备选择：使用第二个可用语音 '{chosen_voice_name}' (ID: {female_voice_id})")
            elif not female_voice_id and voices: # Fallback to the first voice if only one or still not found
                 female_voice_id = voices[0].id
                 chosen_voice_name = voices[0].name if hasattr(voices[0], 'name') else '[未知名称]'
                 print(f"  => 后备选择：使用第一个可用语音 '{chosen_voice_name}' (ID: {female_voice_id})")

        print("-"*30) # 分隔符
        if female_voice_id:
            print(f"最终尝试设置语音为: '{chosen_voice_name}' (ID: {female_voice_id})")
            engine.setProperty('voice', female_voice_id)
        else:
            print("警告: 未能找到或选择任何可用语音。请检查TTS安装和系统语音设置。")

        engine.setProperty('rate', 180) # 稍微调整语速
        test_text = "你好，世界！这是一个语音测试。Hello world, this is a voice test."
        print(f"\n准备朗读文本: '{test_text}'")
        engine.say(test_text)
        print("调用 engine.say() 完成。")
        engine.runAndWait()
        print("调用 engine.runAndWait() 完成。您听到声音了吗？")

    except Exception as e:
        print(f"TTS 测试过程中发生严重错误: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if engine:
            print("尝试停止引擎 (如果正在运行)...")
            # engine.stop() # engine.stop() 有时会导致后续无法再次使用，尤其是在某些驱动上，一般不需要显式调用，runAndWait()会处理。 
            # 如果确实需要，确保了解其影响。
            pass
        print("TTS 测试结束。")

if __name__ == '__main__':
    run_tts_test() 