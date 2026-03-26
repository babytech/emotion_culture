import smtplib
import os
import time
import mimetypes
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from email.mime.base import MIMEBase
from email import encoders
from dotenv import load_dotenv
from PIL import Image # 新增 for NumPy to Image conversion
import numpy as np # 新增 for type hinting
import tempfile # 新增 for temporary files

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def app_path(*parts):
    """构建基于当前应用目录的绝对路径。"""
    return os.path.join(BASE_DIR, *parts)

load_dotenv(app_path(".env"))
load_dotenv(os.path.abspath(os.path.join(BASE_DIR, "..", "..", ".env")))

# 新增辅助函数
def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
        return value if value > 0 else default
    except ValueError:
        return default


def _save_numpy_image_to_tempfile(
    image_np: np.ndarray,
    prefix: str = "img_",
    *,
    max_edge: int = 960,
    jpeg_quality: int = 76,
) -> str | None:
    """
    Saves a NumPy array as a temporary compressed JPEG image file.

    Args:
        image_np (np.ndarray): The NumPy array representing the image.
        prefix (str): Prefix for the temporary file name.

    Returns:
        str | None: The path to the temporary image file, or None if an error occurs.
    """
    if image_np is None:
        return None
    try:
        pil_img = Image.fromarray(image_np.astype(np.uint8)).convert("RGB")

        # Resize huge images to reduce email payload and rendering latency.
        width, height = pil_img.size
        longest = max(width, height)
        if max_edge > 0 and longest > max_edge:
            scale = float(max_edge) / float(longest)
            resized = (max(1, int(width * scale)), max(1, int(height * scale)))
            resampling = getattr(getattr(Image, "Resampling", Image), "LANCZOS", Image.BILINEAR)
            pil_img = pil_img.resize(resized, resampling)

        jpeg_quality = max(40, min(92, int(jpeg_quality)))

        # Create a temporary file
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".jpg", prefix=prefix)
        temp_file_path = temp_file.name
        temp_file.close() # Close it so PIL can write to it

        pil_img.save(
            temp_file_path,
            format="JPEG",
            quality=jpeg_quality,
            optimize=True,
            progressive=True,
        )
        return temp_file_path
    except Exception as e:
        print(f"Error saving NumPy array to temporary image file ({prefix}): {e}")
        # Attempt to clean up if file was created but save failed
        if 'temp_file_path' in locals() and os.path.exists(temp_file_path):
            try:
                os.remove(temp_file_path)
            except Exception as e_clean:
                print(f"Error cleaning up temp file {temp_file_path} after save failure: {e_clean}")
        return None

def _build_audio_attachment_name(audio_path: str) -> str:
    ext = os.path.splitext(audio_path or "")[1].strip().lower()
    allowed = {".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg", ".webm"}
    if ext not in allowed:
        ext = ".mp3"
    return f"user_voice{ext}"


def send_email(
    recipient_email,
    subject,
    html_body,
    image_attachments=None,
    file_attachments=None,
):
    """
    Sends an email with HTML content and optional image attachments.

    Args:
        recipient_email (str): The recipient's email address.
        subject (str): The subject of the email.
        html_body (str): The HTML content of the email body.
        image_attachments (dict): A dictionary where keys are image cid (for inline display)
                                  and values are image file paths. Example: {'image1': 'path/to/image.jpg'}

    Returns:
        tuple: (bool, str) indicating success status and a message.
    """
    sender_email = os.getenv("EMAIL_SENDER_ADDRESS")
    sender_password = os.getenv("EMAIL_SENDER_PASSWORD")
    smtp_server = os.getenv("SMTP_SERVER_HOST", "smtp.gmail.com") # Default to Gmail
    smtp_port = int(os.getenv("SMTP_SERVER_PORT", 587)) # Default to Gmail TLS port
    print(f"Sender email: {sender_email}")
    print(f"SMTP server: {smtp_server}, SMTP port: {smtp_port}")

    if not all([sender_email, sender_password, smtp_server, smtp_port]):
        return False, "Email configuration missing. Please set EMAIL_SENDER_ADDRESS, EMAIL_SENDER_PASSWORD, SMTP_SERVER_HOST, and SMTP_SERVER_PORT environment variables."

    try:
        smtp_timeout = _env_int("SMTP_TIMEOUT_SEC", 20)
        # Create the root message and fill in the from, to, and subject headers
        msg_root = MIMEMultipart('related')
        msg_root['From'] = sender_email
        msg_root['To'] = recipient_email
        msg_root['Subject'] = subject

        # Encapsulate the plain and HTML versions of the message body in an 'alternative' part
        # so message agents can decide which they want to display.
        msg_alternative = MIMEMultipart('alternative')
        msg_root.attach(msg_alternative)

        msg_text = MIMEText('This is an HTML email. Please use an HTML-compatible email client to view it.')
        msg_alternative.attach(msg_text)

        msg_html = MIMEText(html_body, 'html', 'utf-8')
        msg_alternative.attach(msg_html)

        # Attach images
        if image_attachments:
            for cid, path in image_attachments.items():
                try:
                    with open(path, 'rb') as fp:
                        msg_image = MIMEImage(fp.read())
                        msg_image.add_header('Content-ID', f'<{cid}>')
                        msg_image.add_header('Content-Disposition', 'inline', filename=f"{cid}.jpg")
                        msg_root.attach(msg_image)
                except FileNotFoundError:
                    print(f"Warning: Image file not found at {path}, skipping attachment.")
                except Exception as e:
                    print(f"Warning: Could not attach image {path}. Error: {e}")


        # Attach generic files (e.g. user voice recording) as downloadable attachments.
        if file_attachments:
            for attachment in file_attachments:
                if not isinstance(attachment, dict):
                    continue
                path = attachment.get("path")
                filename = attachment.get("filename")
                if not path:
                    continue
                if not filename:
                    filename = os.path.basename(path)
                try:
                    with open(path, "rb") as fp:
                        content = fp.read()
                    mime_type, _ = mimetypes.guess_type(filename)
                    if mime_type and "/" in mime_type:
                        maintype, subtype = mime_type.split("/", 1)
                    else:
                        maintype, subtype = "application", "octet-stream"
                    part = MIMEBase(maintype, subtype)
                    part.set_payload(content)
                    encoders.encode_base64(part)
                    part.add_header("Content-Disposition", "attachment", filename=filename)
                    msg_root.attach(part)
                except FileNotFoundError:
                    print(f"Warning: Attachment file not found at {path}, skipping.")
                except Exception as e:
                    print(f"Warning: Could not attach file {path}. Error: {e}")

        # Send the email
        if smtp_port == 587:
            with smtplib.SMTP(smtp_server, smtp_port, timeout=smtp_timeout) as server:
                server.starttls()  # Secure the connection
                server.login(sender_email, sender_password)
                server.sendmail(sender_email, recipient_email, msg_root.as_string())
        elif smtp_port == 465:
            with smtplib.SMTP_SSL(smtp_server, smtp_port, timeout=smtp_timeout) as server:
                server.login(sender_email, sender_password)
                server.sendmail(sender_email, recipient_email, msg_root.as_string())
        else:
            with smtplib.SMTP(smtp_server, smtp_port, timeout=smtp_timeout) as server:
                server.login(sender_email, sender_password)
                server.sendmail(sender_email, recipient_email, msg_root.as_string())
        
        return True, "邮件发送成功！"
    except smtplib.SMTPAuthenticationError:
        return False, "邮件发送失败：SMTP认证错误。请检查发件人邮箱地址和密码/应用专用密码。"
    except smtplib.SMTPServerDisconnected:
        return False, "邮件发送失败：SMTP服务器意外断开连接。"
    except smtplib.SMTPConnectError:
        return False, f"邮件发送失败：无法连接到SMTP服务器 {smtp_server}:{smtp_port}。"
    except Exception as e:
        return False, f"邮件发送失败：发生未知错误 - {str(e)}"

# 新增：特定于应用邮件发送逻辑的函数
def send_analysis_email(
    to_email,
    thoughts,
    user_photo_np,
    poet_image_np,
    poem,
    guochao_image_np,
    comfort,
    user_audio_path=None,
):
    """
    Prepares and sends the analysis email with all content and images.
    """
    subject = '来自"青少年情绪识别与文化心理疏导系统"的分析结果'
    
    temp_image_paths = [] # To store paths of temporary images for cleanup

    # Prepare image attachments by saving numpy arrays to temp files
    image_attachments_for_email = {}
    t0 = time.perf_counter()
    user_photo_path = _save_numpy_image_to_tempfile(
        user_photo_np,
        "user_photo_",
        max_edge=_env_int("EMAIL_USER_IMAGE_MAX_EDGE", 960),
        jpeg_quality=_env_int("EMAIL_USER_IMAGE_QUALITY", 72),
    )
    if user_photo_path:
        image_attachments_for_email['user_photo_cid'] = user_photo_path
        temp_image_paths.append(user_photo_path)

    poet_image_path = _save_numpy_image_to_tempfile(
        poet_image_np,
        "poet_image_",
        max_edge=_env_int("EMAIL_POET_IMAGE_MAX_EDGE", 820),
        jpeg_quality=_env_int("EMAIL_POET_IMAGE_QUALITY", 78),
    )
    if poet_image_path:
        image_attachments_for_email['poet_image_cid'] = poet_image_path
        temp_image_paths.append(poet_image_path)

    guochao_image_path = _save_numpy_image_to_tempfile(
        guochao_image_np,
        "guochao_image_",
        max_edge=_env_int("EMAIL_GUOCHAO_IMAGE_MAX_EDGE", 820),
        jpeg_quality=_env_int("EMAIL_GUOCHAO_IMAGE_QUALITY", 78),
    )
    if guochao_image_path:
        image_attachments_for_email['guochao_image_cid'] = guochao_image_path
        temp_image_paths.append(guochao_image_path)
    print(f"[email] image_prepare_ms={int((time.perf_counter() - t0) * 1000)}")

    file_attachments_for_email = []
    if user_audio_path:
        file_attachments_for_email.append(
            {
                "path": user_audio_path,
                "filename": _build_audio_attachment_name(user_audio_path),
            }
        )

    # Pre-process poem and comfort for HTML
    poem_for_html = poem.replace("\n", "<br>") if poem else "暂无诗词回应。"
    comfort_for_html = comfort.replace("\n", "<br>") if comfort else "暂无慰藉话语。"

    # Construct HTML body
    html_body = f"""
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 20px; padding: 0; background-color: #f4f4f4; color: #333; }}
            .container {{ background-color: #fff; padding: 20px; border-radius: 8px; box-shadow: 0 0 10px rgba(0,0,0,0.1); }}
            h2 {{ color: #FF4500; }}
            h3 {{ color: #0056b3; }}
            p {{ line-height: 1.6; }}
            .image-container {{ text-align: center; margin-bottom: 20px; }}
            img {{ max-width: 100%; height: auto; border-radius: 4px; border: 1px solid #ddd; }} /* Ensure images are responsive */
            .footer {{ font-size: 0.9em; color: #777; margin-top: 20px; text-align: center; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h2>青少年情绪识别与文化心理疏导结果</h2>
            
            <h3>您的想法与感受：</h3>
            <p>{thoughts if thoughts else "您没有输入想法或感受。"}</p>
    """

    if 'user_photo_cid' in image_attachments_for_email:
        html_body += """
            <h3>您提供的照片：</h3>
            <div class="image-container"><img src="cid:user_photo_cid" alt="用户照片"></div>
        """
    else:
        html_body += "<p>您没有提供照片。</p>"

    html_body += f"""
            <h3>唐宋八大家与诗词回应：</h3>
            <div class="image-container">
                {'<img src="cid:poet_image_cid" alt="唐宋八大家">' if 'poet_image_cid' in image_attachments_for_email else '<p>未能加载唐宋八大家图片。</p>'}
            </div>
            <p>{poem_for_html}</p>

            <h3>国潮伙伴与慰藉：</h3>
            <div class="image-container">
                {'<img src="cid:guochao_image_cid" alt="国潮伙伴">' if 'guochao_image_cid' in image_attachments_for_email else '<p>未能加载国潮伙伴图片。</p>'}
            </div>
            <p>{comfort_for_html}</p>
            <h3>你的录音：</h3>
            <p>{'已附在邮件附件中（可下载回听）。' if file_attachments_for_email else '本次未附带录音。'}</p>
            
            <hr>
            <p class="footer">感谢使用本系统！</p>
        </div>
    </body>
    </html>
    """

    # Send the email using the generic function
    success, message = send_email(
        recipient_email=to_email,
        subject=subject,
        html_body=html_body,
        image_attachments=image_attachments_for_email,
        file_attachments=file_attachments_for_email,
    )

    # Clean up temporary image files
    for path in temp_image_paths:
        try:
            if os.path.exists(path):
                os.remove(path)
        except Exception as e:
            print(f"Error deleting temporary image file {path}: {e}")
            
    return success, message

if __name__ == '__main__':
    # Example Usage (for testing)
    # Make sure to set your environment variables:
    # EMAIL_SENDER_ADDRESS, EMAIL_SENDER_PASSWORD
    # And optionally SMTP_SERVER_HOST, SMTP_SERVER_PORT if not using Gmail defaults.
    # For Gmail, you might need to enable "Less secure app access" or use an "App Password".

    print("Attempting to send a test email...")
    # Create a dummy html_content and image files for testing
    dummy_html = """
    <html>
        <body>
            <h1>测试邮件</h1>
            <p>这是一封来自青少年情绪识别与文化心理疏导系统的测试邮件。</p>
            <p>情绪诗词图片:</p>
            <img src="cid:poet_image_cid" alt="诗人图片" width="200">
            <p>国潮伙伴图片:</p>
            <img src="cid:guochao_image_cid" alt="国潮伙伴图片" width="200">
        </body>
    </html>
    """
    # Create dummy image files for testing
    os.makedirs(app_path("images", "tangsong"), exist_ok=True)
    os.makedirs(app_path("images", "guochao"), exist_ok=True)
    dummy_poet_path = app_path("images", "tangsong", "dummy_poet.png")
    dummy_guochao_path = app_path("images", "guochao", "dummy_guochao.png")

    try:
        from PIL import Image, ImageDraw
        img_poet = Image.new('RGB', (100, 100), color = 'red')
        d_poet = ImageDraw.Draw(img_poet)
        d_poet.text((10,10), "Poet", fill=(255,255,0))
        img_poet.save(dummy_poet_path)

        img_guochao = Image.new('RGB', (100, 100), color = 'blue')
        d_guochao = ImageDraw.Draw(img_guochao)
        d_guochao.text((10,10), "Guochao", fill=(255,255,0))
        img_guochao.save(dummy_guochao_path)
        print(f"Dummy images created: {dummy_poet_path}, {dummy_guochao_path}")

        images_to_attach = {
            'poet_image_cid': dummy_poet_path,
            'guochao_image_cid': dummy_guochao_path
        }
        
        # Replace with a real recipient email for testing
        test_recipient = os.getenv("TEST_RECIPIENT_EMAIL", "your_test_recipient@example.com") 
        
        if test_recipient == "your_test_recipient@example.com" and not os.getenv("TEST_RECIPIENT_EMAIL"):
            print("Please set the TEST_RECIPIENT_EMAIL environment variable to your email address for testing.")
        else:
            success, message = send_email(
                recipient_email=test_recipient,
                subject="[测试] 青少年情绪识别系统邮件",
                html_body=dummy_html,
                image_attachments=images_to_attach
            )
            print(f"Test email send status: {success}")
            print(f"Message: {message}")

    except ImportError:
        print("Pillow library is not installed. Skipping dummy image creation. pip install Pillow")
    except Exception as e:
        print(f"Error during test email setup: {e}")
    finally:
        # Clean up dummy files
        if os.path.exists(dummy_poet_path):
            os.remove(dummy_poet_path)
        if os.path.exists(dummy_guochao_path):
            os.remove(dummy_guochao_path)
        print("Dummy files cleaned up.") 
