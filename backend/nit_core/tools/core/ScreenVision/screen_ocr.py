import base64
import io
import os
import platform
import tempfile

# 可选导入
try:
    import pyautogui
except ImportError:
    pyautogui = None


def _is_server_mode():
    return os.environ.get("PERO_ENV") == "server" or platform.system() != "Windows"


def get_screenshot_base64():
    """获取当前屏幕截图并返回 base64 编码的字符串"""
    if _is_server_mode() or not pyautogui:
        return "错误: 服务器模式或缺少依赖。"

    try:
        screenshot = pyautogui.screenshot()
        buffered = io.BytesIO()
        screenshot.save(buffered, format="PNG")
        img_str = base64.b64encode(buffered.getvalue()).decode()
        return img_str
    except Exception as e:
        return f"获取截图失败: {str(e)}"


def save_screenshot():
    """获取当前屏幕截图并保存到临时文件，返回文件路径"""
    if _is_server_mode() or not pyautogui:
        return None

    try:
        # [重构] 统一移动到 backend/data/temp_vision
        backend_dir = os.path.dirname(
            os.path.dirname(
                os.path.dirname(
                    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                )
            )
        )
        data_dir = os.environ.get("PERO_DATA_DIR", os.path.join(backend_dir, "data"))
        temp_dir = os.path.join(data_dir, "temp_vision")
        os.makedirs(temp_dir, exist_ok=True)

        with tempfile.NamedTemporaryFile(
            suffix=".png", dir=temp_dir, delete=False
        ) as temp_file:
            temp_path = temp_file.name

        screenshot = pyautogui.screenshot()
        screenshot.save(temp_path)
        return temp_path
    except Exception as e:
        print(f"保存截图错误: {e}")
        return None


def take_screenshot(count: int = 1):
    """
    这是一个占位函数。实际的截图获取和注入逻辑在 agent_service.py 中处理。
    """
    return f"已请求获取 {count} 张截图。"


# 已移除: easyocr 相关功能 (screen_ocr, find_text_coordinates, warm_up)
# 原因: easyocr 体积大、依赖重，实际用途有限 (2026-03-20)
