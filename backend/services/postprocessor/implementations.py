from typing import Any, AsyncIterable, Dict

from nit_core.dispatcher import NITStreamFilter, remove_nit_tags

from .base import BasePostprocessor


class ThinkingFilterPostprocessor(BasePostprocessor):
    """
    从全文中过滤掉 Thinking 块（例如 【Thinking:...】），
    但在流中允许它们（以便用户可以看到过程）。
    """

    @property
    def name(self) -> str:
        return "ThinkingFilter"

    async def process(self, content: str, context: Dict[str, Any]) -> str:
        """
        通过 Thinking 块（不再过滤它们），以便可以将它们存储在记忆中
        并按要求显示给用户。
        但在社交模式下，我们根据 context 进行过滤。
        """
        if context.get("source") == "social":
            import re
            # 移除 【Thinking:...】, [Thinking:...], (Thinking:...) 等块
            # 这种非流式处理使用简单的正则
            content = re.sub(r"【Thinking:.*?】", "", content, flags=re.DOTALL | re.IGNORECASE)
            content = re.sub(r"\[Thinking:.*?\]", "", content, flags=re.DOTALL | re.IGNORECASE)
            content = re.sub(r"\(Thinking:.*?\)", "", content, flags=re.DOTALL | re.IGNORECASE)
            
            # [兼容性保留] 移除旧版 【Monologue:...】 等块，确保历史记录或意外输出不溢出到社交平台
            content = re.sub(r"【Monologue:.*?】", "", content, flags=re.DOTALL | re.IGNORECASE)
            content = re.sub(r"\[Monologue:.*?\]", "", content, flags=re.DOTALL | re.IGNORECASE)
            content = re.sub(r"\(Monologue:.*?\)", "", content, flags=re.DOTALL | re.IGNORECASE)
        
        return content

    async def process_stream(
        self, stream: AsyncIterable[str], context: Dict[str, Any]
    ) -> AsyncIterable[str]:
        """
        在社交模式下过滤思考块。
        """
        if context.get("source") == "social":
            from nit_core.dispatcher import ThinkingBlockStreamFilter
            thinking_filter = ThinkingBlockStreamFilter()
            async for chunk in stream:
                filtered = thinking_filter.filter(chunk)
                if filtered:
                    yield filtered
            
            # Flush
            remaining = thinking_filter.flush()
            if remaining:
                yield remaining
            return

        async for chunk in stream:
            yield chunk


class NITFilterPostprocessor(BasePostprocessor):
    """
    过滤掉 NIT 协议标记（例如 [[[NIT_CALL]]], [START]...[END]）
    从批处理内容和流式输出中。
    """

    @property
    def name(self) -> str:
        return "NITFilter"

    async def process(self, content: str, context: Dict[str, Any]) -> str:
        """
        从全文中移除 NIT 块。
        """
        if context.get("skip_nit_filter"):
            return content

        return remove_nit_tags(content)

    async def process_stream(
        self, stream: AsyncIterable[str], context: Dict[str, Any]
    ) -> AsyncIterable[str]:
        """
        使用 NITStreamFilter 从流中过滤 NIT 块。
        """
        if context.get("skip_nit_filter"):
            async for chunk in stream:
                yield chunk
            return

        # 为此流实例化一个新的过滤器
        nit_filter = NITStreamFilter()

        async for chunk in stream:
            # 过滤器返回可以安全显示的文本（在 NIT 块之外）
            filtered_chunk = nit_filter.filter(chunk)
            if filtered_chunk:
                yield filtered_chunk

        # 在流结束时刷新所有剩余缓冲区
        remaining = nit_filter.flush()
        if remaining:
            yield remaining
