"""
用户界面模块 - 处理网页显示和CSS设置等前端代码
"""

import gradio as gr

# -------- 国风CSS样式 --------
css = """
:root {
    --main-color: #e60000; /* 这个红色主要用于旧版按钮，会被新规则覆盖 */
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
    color: #0000FF !important; /* 蓝色 (Blue) */
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
    height: 20px; /* 略微减小分割线高度 */
    margin: 10px 0; /* 调整分割线上下的间距 */
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

/* 自定义按钮颜色 */
#submit_button_custom {
    background-color: #4CAF50 !important; /* 鲜绿色 */
}
#submit_button_custom:hover {
    background-color: #367c39 !important; /* 深绿色 */
}

#reset_button_custom {
    background-color: #FFA500 !important; /* 橙色 */
}
#reset_button_custom:hover {
    background-color: #cc8400 !important; /* 深橙色 */
}

/* 摄像头图像上传区域背景色 */
.image-preview div[data-testid="image-upload-box"],
.image-preview div[role="button"],
.image-preview .contain /* Gradio <4 may use this for the dropzone wrapper */
{
    background-color: #f0f0f0 !important; /* 浅灰色 */
    border: 2px dashed #ccc !important; /* 添加一个虚线边框以更好地区分 */
}

/* 语音输入组件内部的录制/停止等按钮 */
.custom-audio-input button[class*="icon-button"],
.custom-audio-input button.record-button, /* 假设Gradio内部可能有此类名 */
.custom-audio-input button[aria-label*="Record"],
.custom-audio-input button[title*="Record"],
.custom-audio-input button[aria-label*="Stop"],
.custom-audio-input button[title*="Stop"] {
    background-color: #4CAF50 !important; /* 绿色 */
    color: white !important; /* 白色文字以确保可见性 */
    border: none !important;
}
.custom-audio-input button[class*="icon-button"]:hover,
.custom-audio-input button.record-button:hover,
.custom-audio-input button[aria-label*="Record"]:hover,
.custom-audio-input button[title*="Record"]:hover,
.custom-audio-input button[aria-label*="Stop"]:hover,
.custom-audio-input button[title*="Stop"]:hover {
    background-color: #367c39 !important; /* 深绿色 */
}

/* 减少特定行之间的垂直间距 */
.compact-row {
    margin-top: 5px !important;  /* 减少上方外边距 */
    margin-bottom: 5px !important; /* 减少下方外边距 */
    padding-top: 0 !important; /* 减少上方内边距 */
    padding-bottom: 0 !important; /* 减少下方内边距 */
}

body {
    background-color: var(--background-color);
    background-image: url('https://img.freepik.com/free-vector/chinese-cloud-pattern-background-red_53876-135689.jpg');
    background-size: cover;
    background-repeat: no-repeat;
    background-attachment: fixed;
    font-family: 'Ma Shan Zheng', cursive, sans-serif;
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
    with gr.Blocks(title="青少年情绪识别与文化心理疏导系统", css=css) as iface:
        # 全局标题
        with gr.Row(elem_classes="fade-in"):
            gr.Markdown("# 青少年情绪识别与文化心理疏导系统")
        
        # 顶部区域：描述、文本输入
        with gr.Column(): 
            gr.Markdown("通过面部表情、文本和语音分析儿童情绪，提供诗词和文化形象进行心理疏导。")
            text_input = gr.Textbox(label="请输入文本描述您的感受", elem_classes="textbox-container")

        # 例子和语音输入在同一行
        with gr.Row():
            with gr.Column(scale=2): # 例子占较大比例
                gr.Markdown("### 例子")
                gr.Examples(
                    examples=[
                        ["我今天很开心，阳光明媚！"],
                        ["有点难过，考试没考好。"],
                        ["气死我了，他怎么能这样！"],
                        ["哇，太惊喜了！这是给我的吗？"],
                        ["没什么特别的感觉，很平静。"],
                        ["看了一部恐怖片，现在还有点害怕。"],
                        ["对未来感到有些迷茫和担忧。"],
                        ["今天完成了一个大项目，很有成就感！"],
                        ["感觉有点孤单，想找人聊聊天。"],
                        ["收到了朋友的礼物，心里暖暖的。"]
                    ],
                    inputs=[text_input]
                )
            with gr.Column(scale=1): # 语音输入占较小比例
                audio_input = gr.Audio(
                    label="或使用语音输入",
                    type="filepath",
                    sources=["microphone"],
                    elem_classes="custom-audio-input" # 添加自定义类以便CSS定位
                )

        gr.HTML('<div class="chinese-pattern"></div>') # 分割线

        # 中间三栏图像区域 - 添加自定义class以控制间距
        with gr.Row(elem_classes="compact-row"): 
            with gr.Column(scale=1):
                image_input = gr.Image(label="使用摄像头", elem_classes="image-preview") 
            with gr.Column(scale=1):
                poet_image_output = gr.Image(label="唐宋八大家", elem_classes="image-preview")
            with gr.Column(scale=1):
                guochao_image_output = gr.Image(label="国潮卡通形象", elem_classes="image-preview")

        # 下方对应三栏的输出和控制区域
        with gr.Row():
            # 左栏：摄像头下的控制和输出
            with gr.Column(scale=1):
                with gr.Row():
                    reset_btn = gr.Button("重置", elem_id="reset_button_custom")
                    submit_btn = gr.Button("提交", variant="primary", elem_id="submit_button_custom")
                emotion_output = gr.Textbox(label="情绪识别结果", elem_classes="textbox-container")
            
            # 中栏：唐宋八大家下的诗词解读
            with gr.Column(scale=1):
                poem_output = gr.Textbox(label="诗词回应与解读", lines=10, elem_classes="textbox-container")
            
            # 右栏：国潮卡通形象下的安抚文案
            with gr.Column(scale=1):
                comfort_output = gr.Textbox(label="安抚文案", lines=10, elem_classes="textbox-container")
        
        gr.HTML('<div class="chinese-pattern"></div>') # 底部分割线
        gr.HTML('<div class="footer">© 2023 儿童情绪识别与文化心理疏导系统 | 传统文化与现代科技的融合</div>')
        
        # 定义重置函数
        def reset_all():
            # 清除所有输入和输出
            # 输入：text_input, image_input, audio_input
            # 输出：emotion_output, poem_output, poet_image_output, comfort_output, guochao_image_output
            return None, None, None, "", "", None, "", None

        # 设置重置按钮功能
        reset_btn.click(
            fn=reset_all,
            inputs=None, # 重置函数不需要输入
            outputs=[
                text_input, 
                image_input, 
                audio_input, 
                emotion_output, 
                poem_output, 
                poet_image_output, 
                comfort_output, 
                guochao_image_output
            ]
        )
        
        # 设置提交按钮功能
        submit_btn.click(
            fn=main_app_func,
            inputs=[text_input, image_input, audio_input],
            outputs=[emotion_output, poem_output, poet_image_output, comfort_output, guochao_image_output]
        )
    
    return iface 