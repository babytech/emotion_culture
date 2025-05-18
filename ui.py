"""
用户界面模块 - 处理网页显示和CSS设置等前端代码
"""

import gradio as gr

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

/* 语音输入按钮样式 */
.audio-input-btn {
    background-color: var(--secondary-color) !important;
    color: var(--text-color) !important;
    font-weight: bold !important;
    border: 2px solid var(--border-color) !important;
}

.audio-input-btn:hover {
    background-color: #e6c300 !important;
}
"""

def create_ui(main_app_func):
    """
    创建Gradio用户界面
    
    参数:
        main_app_func: 主应用函数，处理用户输入并返回结果
        
    返回:
        Gradio界面对象
    """
    with gr.Blocks(title="儿童情绪识别与文化心理疏导系统", css=css) as iface:
        with gr.Row(elem_classes="fade-in"):
            gr.Markdown("# 儿童情绪识别与文化心理疏导系统")
        
        gr.HTML('<div class="chinese-pattern"></div>')
        gr.Markdown("通过面部表情、文本和语音分析儿童情绪，提供诗词和文化形象进行心理疏导。")
        
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
                
                # 添加语音输入组件
                with gr.Row():
                    audio_input = gr.Audio(
                        label="或使用语音输入",
                        type="filepath",
                        sources=["microphone"],
                        elem_classes="audio-input"
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
            fn=main_app_func,
            inputs=[text_input, image_input, audio_input],
            outputs=[emotion_output, poem_output, poet_image_output, comfort_output, guochao_image_output]
        )
    
    return iface 