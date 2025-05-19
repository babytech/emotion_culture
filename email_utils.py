import smtplib
import os
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from dotenv import load_dotenv
from PIL import Image # 新增 for NumPy to Image conversion
import numpy as np # 新增 for type hinting
import tempfile # 新增 for temporary files
import io # 新增 for PIL saving to bytes

load_dotenv() # Load environment variables from .env file

# 新增辅助函数
def _save_numpy_image_to_tempfile(image_np: np.ndarray, prefix: str = "img_") -> str | None:
    """
    Saves a NumPy array as a temporary PNG image file.

    Args:
        image_np (np.ndarray): The NumPy array representing the image.
        prefix (str): Prefix for the temporary file name.

    Returns:
        str | None: The path to the temporary image file, or None if an error occurs.
    """
    if image_np is None:
        return None
    try:
        pil_img = Image.fromarray(image_np.astype(np.uint8))
        
        # Create a temporary file
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".png", prefix=prefix)
        temp_file_path = temp_file.name
        temp_file.close() # Close it so PIL can write to it
        
        pil_img.save(temp_file_path, format='PNG')
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

def send_email(recipient_email, subject, html_body, image_attachments=None):
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

    if not all([sender_email, sender_password, smtp_server, smtp_port]):
        return False, "Email configuration missing. Please set EMAIL_SENDER_ADDRESS, EMAIL_SENDER_PASSWORD, SMTP_SERVER_HOST, and SMTP_SERVER_PORT environment variables."

    try:
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
                        msg_root.attach(msg_image)
                except FileNotFoundError:
                    print(f"Warning: Image file not found at {path}, skipping attachment.")
                except Exception as e:
                    print(f"Warning: Could not attach image {path}. Error: {e}")


        # Send the email
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()  # Secure the connection
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
def send_analysis_email(to_email, thoughts, user_photo_np, poet_image_np, poem, guochao_image_np, comfort):
    """
    Prepares and sends the analysis email with all content and images.
    """
    subject = '来自"青少年情绪识别与文化心理疏导系统"的分析结果'
    
    temp_image_paths = [] # To store paths of temporary images for cleanup

    # Prepare image attachments by saving numpy arrays to temp files
    image_attachments_for_email = {}

    user_photo_path = _save_numpy_image_to_tempfile(user_photo_np, "user_photo_")
    if user_photo_path:
        image_attachments_for_email['user_photo_cid'] = user_photo_path
        temp_image_paths.append(user_photo_path)

    poet_image_path = _save_numpy_image_to_tempfile(poet_image_np, "poet_image_")
    if poet_image_path:
        image_attachments_for_email['poet_image_cid'] = poet_image_path
        temp_image_paths.append(poet_image_path)

    guochao_image_path = _save_numpy_image_to_tempfile(guochao_image_np, "guochao_image_")
    if guochao_image_path:
        image_attachments_for_email['guochao_image_cid'] = guochao_image_path
        temp_image_paths.append(guochao_image_path)

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
        image_attachments=image_attachments_for_email
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
    os.makedirs("images/tangsong", exist_ok=True)
    os.makedirs("images/guochao", exist_ok=True)
    dummy_poet_path = "images/tangsong/dummy_poet.png"
    dummy_guochao_path = "images/guochao/dummy_guochao.png"

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