"""
用户界面模块 - 处理网页显示和CSS设置等前端代码
"""

import gradio as gr
import inspect

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

/* 为 Examples 中的示例添加不同背景色 */
/* Base style for buttons within the custom examples area */
#custom_examples_area div[data-testid="dataset"] button {
    background-image: none !important; /* Override global button background images/gradients */
    border: 1px solid var(--border-color) !important;
    border-radius: 5px !important;
    padding: 8px 12px !important;
    margin-bottom: 5px !important;
    font-weight: normal !important; /* Override bold from global button if desired */
    box-shadow: 0 1px 3px rgba(0,0,0,0.1) !important; /* Softer shadow than global button */
}

/* Odd-numbered example buttons within the custom examples area */
#custom_examples_area div[data-testid="dataset"] button:nth-child(odd) {
    background-color: #e6f7ff !important; /* 淡蓝色 */
    color: #333333 !important; /* 深色文字，确保可读性 */
}

/* Even-numbered example buttons within the custom examples area */
#custom_examples_area div[data-testid="dataset"] button:nth-child(even) {
    background-color: #fff0e6 !important; /* 淡橙色 */
    color: #333333 !important; /* 深色文字，确保可读性 */
}

/* Hover effect for odd example buttons */
#custom_examples_area div[data-testid="dataset"] button:nth-child(odd):hover {
    background-color: #d0eefc !important; /* 略深的淡蓝色 */
    color: #000000 !important; /* 确保悬停时文字仍清晰 */
    filter: none !important; /* Remove general hover filter if it causes issues */
    transform: translateY(-1px) !important;
}

/* Hover effect for even example buttons */
#custom_examples_area div[data-testid="dataset"] button:nth-child(even):hover {
    background-color: #ffe0cc !important; /* 略深的淡橙色 */
    color: #000000 !important; /* 确保悬停时文字仍清晰 */
    filter: none !important;
    transform: translateY(-1px) !important;
}

/* 修改 "语音输入 (可选)" Accordion 标题的背景色 */
.custom-audio-accordion .label-wrap > .label, /* Gradio 较新版本可能使用这种结构 */
.custom-audio-accordion > button, /* Gradio 某些版本Accordion标题是button */
.custom-audio-accordion > div[role="button"], /* 或者是一个带role=button的div */
.custom-audio-accordion summary /* HTML5 details/summary 结构 */
{
    background-color: #28a745 !important; /* 绿色 */
    color: white !important; /* 白色文字以确保可见性 */
    border-radius: 5px !important;
    padding: 8px 12px !important; /* 调整内边距 */
    border: none !important; /* 移除边框，如果需要 */
}

.custom-audio-accordion .label-wrap > .label:hover,
.custom-audio-accordion > button:hover,
.custom-audio-accordion > div[role="button"]:hover,
.custom-audio-accordion summary:hover {
    background-color: #218838 !important; /* 深一点的绿色 */
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

UI_THEME = gr.themes.Soft(primary_hue="red", secondary_hue="orange")
BLOCKS_LAUNCH_PARAMS = inspect.signature(gr.Blocks.launch).parameters
BLOCKS_INIT_KWARGS = {}

if "theme" not in BLOCKS_LAUNCH_PARAMS:
    BLOCKS_INIT_KWARGS["theme"] = UI_THEME
if "css" not in BLOCKS_LAUNCH_PARAMS:
    BLOCKS_INIT_KWARGS["css"] = css

def build_launch_kwargs():
    """在 Gradio 6 及以上版本通过 launch() 注入主题与样式。"""
    launch_kwargs = {}
    if "theme" in BLOCKS_LAUNCH_PARAMS:
        launch_kwargs["theme"] = UI_THEME
    if "css" in BLOCKS_LAUNCH_PARAMS:
        launch_kwargs["css"] = css
    return launch_kwargs

def create_ui(main_app_func):
    """
    创建Gradio用户界面
    
    参数:
        main_app_func: 主应用函数，处理用户输入并返回结果
        
    返回:
        gr.Blocks: Gradio界面实例
    """
    with gr.Blocks(**BLOCKS_INIT_KWARGS) as iface:
        gr.Markdown("<h1 style='text-align: center; color: #FF4500;'>青少年情绪识别与文化心理疏导系统</h1>")
        
        with gr.Row():
            with gr.Column(scale=2):
                gr.Markdown("### 步骤 1: 输入信息")
                text_input = gr.Textbox(lines=6, label="写下你的想法或感受:", placeholder="例如：今天我感到很开心！")
                
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
                    inputs=[text_input],
                    label="或者试试这些例子：",
                    elem_id="custom_examples_area"
                )
                
                with gr.Accordion("🎤 语音输入 (可选)", open=False, elem_classes="custom-audio-accordion"):
                    audio_input = gr.Audio(sources=["microphone"], type="filepath", label="或者，说出你的感受:", elem_classes="custom-audio-input")

                emotion_output = gr.Textbox(label="情绪识别结果:", interactive=False, elem_classes="textbox-container")
                
                gr.Markdown("### 步骤 2: 上传或拍摄照片 (可选)")
                image_input = gr.Image(sources=["upload", "webcam"], type="numpy", label="上传图片或使用摄像头", height=300, elem_classes="image-preview")
                
            with gr.Column(scale=3):
                gr.Markdown("### 步骤 3: 查看结果 ✨")
                
                with gr.Row():
                    with gr.Column(scale=11):
                        poet_image_output = gr.Image(label="唐宋八大家", type="numpy", interactive=False, height=330, elem_classes="image-preview")
                    with gr.Column(scale=19):
                        poem_output = gr.Textbox(label="诗词与解读:", lines=10, interactive=False, elem_classes="textbox-container")

                with gr.Row():
                    with gr.Column(scale=11):
                        guochao_image_output = gr.Image(label="国潮伙伴", type="numpy", interactive=False, height=330, elem_classes="image-preview")
                    with gr.Column(scale=19):
                        comfort_output = gr.Textbox(label="来自国潮伙伴的慰藉:", lines=5, interactive=False, elem_classes="textbox-container")
                
                # 新增：步骤 4 - 发送电子邮件
                gr.Markdown("### 步骤 4: 发送电子邮件 (可选)")
                email_input = gr.Textbox(label="请输入您的邮箱地址:", placeholder="your_email@example.com", elem_id="email_input_custom")
                send_email_button = gr.Button("发送到邮箱", elem_id="send_email_button_custom")
                email_status_output = gr.Textbox(label="邮件发送状态:", interactive=False, elem_classes="textbox-container")

            
        # 分割线
        gr.Markdown("<div class='chinese-pattern'></div>", elem_classes="fade-in")

        with gr.Row(elem_classes="compact-row"):
            submit_button = gr.Button("提交分析", variant="primary", elem_id="submit_button_custom")
            reset_button = gr.Button("重置所有", variant="secondary", elem_id="reset_button_custom")

        # 页脚
        gr.Markdown("<p class='footer'>© 2024 青少年情绪识别与文化心理疏导系统. </p>")
        
        # 定义清除函数
        def reset_all():
            # 清除所有输入和输出
            # 输入：text_input, image_input, audio_input
            # 输出：emotion_output, poem_output, poet_image_output, comfort_output, guochao_image_output
            # 新增：email_input, email_status_output
            return (
                "",  # text_input
                None, # image_input
                None, # audio_input
                "",   # emotion_output
                "",   # poem_output
                None, # poet_image_output
                "",   # comfort_output
                None, # guochao_image_output
                "", # email_input
                ""  # email_status_output
            )

        # 绑定提交按钮的点击事件
        submit_button.click(
            fn=main_app_func.process_analysis,
            inputs=[text_input, image_input, audio_input],
            outputs=[emotion_output, poem_output, poet_image_output, comfort_output, guochao_image_output]
        )
        
        # 新增：绑定发送邮件按钮的点击事件
        # 注意：send_email_function 需要在 main.py 中定义并传递给 create_ui
        # 目前我们先假设它会被传递进来
        if hasattr(main_app_func, 'send_email_function') and callable(main_app_func.send_email_function):
            send_email_button.click(
                fn=main_app_func.send_email_function,
                inputs=[
                    email_input,            # 邮箱地址
                    text_input,             # 步骤1 用户写下的想法与感受
                    image_input,            # 步骤2 用户上传或拍摄照片
                    poet_image_output,      # 步骤3 唐宋八大家卡通人物图片
                    poem_output,            # 步骤3 诗词回应
                    guochao_image_output,   # 步骤3 为用户生成的卡通形象 (国潮伙伴)
                    comfort_output          # 步骤3 安抚情绪鼓励的话语 (来自国潮伙伴的慰藉)
                ],
                outputs=[email_status_output]
            )
        else:
            # 如果没有提供邮件发送函数，则按钮点击时显示提示信息
            def show_email_feature_not_implemented():
                return "邮件发送功能暂未实现。"
            send_email_button.click(
                fn=show_email_feature_not_implemented,
                inputs=[],
                outputs=[email_status_output]
            )

        # 绑定重置按钮的点击事件
        reset_button.click(
            fn=reset_all,
            inputs=[], # 无需输入
            outputs=[
                text_input, image_input, audio_input,
                emotion_output, poem_output, poet_image_output, comfort_output, guochao_image_output,
                email_input, email_status_output # 新增重置项
            ]
        )
        
    iface._launch_kwargs = build_launch_kwargs()
    return iface

if __name__ == '__main__':
    # 这是一个用于测试UI模块的简单示例
    # 在实际应用中，main_app_func 会从 main.py 导入
    
    def mock_main_app(text, image, audio):
        print(f"测试文本: {text}")
        print(f"测试图像形状: {image.shape if image is not None else '无图像'}")
        print(f"测试音频路径: {audio if audio else '无音频'}")
        
        # 模拟返回一些数据
        emotion_res = "情绪: 开心"
        poem_res = "《登高》\n杜甫\n风急天高猿啸哀，渚清沙白鸟飞回。\n无边落木萧萧下，不尽长江滚滚来。\n万里悲秋常作客，百年多病独登台。\n艰难苦恨繁霜鬓，潦倒新停浊酒杯。"
        
        # 模拟图像输出 (创建空白图像)
        import numpy as np
        from PIL import Image
        
        blank_image_data_poet = np.array(Image.new('RGB', (300, 400), color = 'skyblue'))
        blank_image_data_guochao = np.array(Image.new('RGB', (350, 350), color = 'lightgreen'))
        
        comfort_res = "开心牛牛：\n今天真是美好的一天！"
        
        return emotion_res, poem_res, blank_image_data_poet, comfort_res, blank_image_data_guochao

    # 为了测试邮件功能，我们需要一个模拟的 main_app_func 对象，它有一个 send_email_function 方法
    class MockMainApp:
        def __call__(self, text, image, audio):
            return mock_main_app(text, image, audio)

        def send_email_function(self, email, thoughts, user_photo, poet_img, poem, guochao_img, comfort):
            print(f"模拟发送邮件到: {email}")
            print(f"想法: {thoughts}")
            print(f"用户照片: {'有' if user_photo is not None else '无'}")
            print(f"诗人图片: {'有' if poet_img is not None else '无'}")
            print(f"诗词: {poem}")
            print(f"国潮形象: {'有' if guochao_img is not None else '无'}")
            print(f"慰藉语: {comfort}")
            if not email:
                return "请输入邮箱地址。"
            if "@" not in email or "." not in email: # 简单邮箱格式校验
                return "邮箱格式不正确。"
            return f"邮件已发送到 {email} (模拟)。"

    iface = create_ui(MockMainApp()) # 使用新的 MockMainApp 实例
    iface.launch(server_name="0.0.0.0", server_port=7860, **getattr(iface, "_launch_kwargs", {}))
