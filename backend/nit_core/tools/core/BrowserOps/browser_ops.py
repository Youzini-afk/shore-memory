import httpx
from bs4 import BeautifulSoup

try:
    from services.interaction.browser_bridge_service import browser_bridge_service
except ImportError:
    from backend.services.interaction.browser_bridge_service import (
        browser_bridge_service,
    )


async def _wrap_result_with_content(result: dict) -> str:
    """帮助函数：将当前页面内容附加到命令结果中。"""
    content = browser_bridge_service.get_current_page_markdown()

    # 构造 NIT 格式的反馈：先给出执行状态，再给出页面内容供 AI 下一步决策
    status = result.get("status", "unknown")
    if status == "success":
        msg = "✅ 执行成功。"
    else:
        error_msg = result.get("error", "未知错误")
        msg = f"❌ 执行失败: {error_msg}"

    output = f"{msg}\n\n"
    output += "--- 当前页面内容 (简化 Markdown) ---\n"
    output += content
    return output


async def browser_fetch_text(url: str, **kwargs) -> str:
    """
    使用轻量级 HTTP 客户端获取网页内容并返回文本。
    用于快速阅读文章或静态页面，无需视觉交互。
    """
    if not url.startswith("http"):
        url = "https://" + url

    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        async with httpx.AsyncClient(follow_redirects=True, timeout=30.0) as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()

            # 编码
            if response.encoding is None:
                response.encoding = "utf-8"  # 默认回退

            soup = BeautifulSoup(response.text, "html.parser")

            # 移除垃圾内容
            for script in soup(
                ["script", "style", "nav", "footer", "header", "iframe", "noscript"]
            ):
                script.decompose()

            text = soup.get_text()

            # 清理文本
            lines = (line.strip() for line in text.splitlines())
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            text = "\n".join(chunk for chunk in chunks if chunk)

            return f"### 来自 {url} 的内容\n\n{text[:20000]}" + (
                "\n...[Truncated]" if len(text) > 20000 else ""
            )

    except Exception as e:
        return f"Error fetching URL: {str(e)}"


async def browser_open_url(url: str = None, target: str = None, **kwargs) -> str:
    """
    控制连接的浏览器打开指定的 URL。

    参数:
        url (str): 要打开的 URL。
        target (str): url 的别名，用于兼容性。

    返回:
        str: 执行状态和新页面内容。
    """
    # 兼容性处理：如果缺少 url 但提供了 target
    final_url = url or target
    if not final_url:
        return "❌ 错误: 请提供 URL (参数 'url' or 'target')。"

    if not final_url.startswith("http"):
        final_url = "https://" + final_url

    result = await browser_bridge_service.send_command("open_url", url=final_url)
    return await _wrap_result_with_content(result)


async def _retry_command(
    command: str, max_retries: int = 3, delay: float = 1.0, **kwargs
) -> dict:
    """帮助函数：重试可能因时序问题（如元素未就绪）而失败的命令。"""
    import asyncio

    last_result = {"status": "error", "error": "未知错误"}

    for i in range(max_retries):
        last_result = await browser_bridge_service.send_command(command, **kwargs)
        if last_result.get("status") == "success":
            return last_result

        # 最后一次尝试不休眠
        if i < max_retries - 1:
            await asyncio.sleep(delay)

    return last_result


async def browser_click(target: str, **kwargs) -> str:
    """
    点击当前页面上的元素（按钮、链接等）。

    Args:
        target (str): 要点击的元素的文本或标识符。

    Returns:
        str: 执行状态和更新后的页面内容。
    """
    # 点击操作使用重试逻辑，因为元素可能动态加载
    result = await _retry_command("click", target=target)
    return await _wrap_result_with_content(result)


async def browser_type(target: str, text: str, **kwargs) -> str:
    """
    在输入框中输入文本。

    Args:
        target (str): 输入字段的标签、占位符或标识符。
        text (str): 要输入的文本。

    Returns:
        str: 执行状态和更新后的页面内容。
    """
    # 输入操作使用重试逻辑，因为元素可能动态加载
    result = await _retry_command("type", target=target, text=text)
    return await _wrap_result_with_content(result)


async def browser_get_content(**kwargs) -> str:
    """
    从连接的浏览器获取当前页面内容。

    Returns:
        str: 当前页面的简化 Markdown 内容。
    """
    content = browser_bridge_service.get_current_page_markdown()
    if content.startswith("Error:"):
        return f"❌ {content}"
    return content


async def browser_scroll(direction: str = "down", **kwargs) -> str:
    """
    向上或向下滚动当前页面。

    Args:
        direction (str): "up" 或 "down"。默认为 "down"。

    Returns:
        str: 执行状态和更新后的页面内容。
    """
    result = await browser_bridge_service.send_command("scroll", text=direction)
    return await _wrap_result_with_content(result)


async def browser_back(**kwargs) -> str:
    """
    返回历史记录中的上一页。

    Returns:
        str: 执行状态和更新后的页面内容。
    """
    result = await browser_bridge_service.send_command("back")
    return await _wrap_result_with_content(result)


async def browser_refresh(**kwargs) -> str:
    """
    刷新当前页面。

    Returns:
        str: 执行状态和更新后的页面内容。
    """
    result = await browser_bridge_service.send_command("refresh")
    return await _wrap_result_with_content(result)
