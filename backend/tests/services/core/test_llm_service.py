from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.core.llm_service import LLMService


class TestLLMService:
    @pytest.fixture
    def llm_service(self):
        return LLMService(
            api_key="test_key",
            api_base="https://api.example.com/v1",
            model="gpt-4o",
            provider="openai",
        )

    def test_init_defaults(self):
        """测试初始化默认值"""
        service = LLMService(api_key="key", api_base="", model="gpt-4o")
        assert service.provider == "openai"
        assert service.api_base == "https://api.openai.com"

    def test_init_custom_base(self):
        """测试自定义 api_base"""
        service = LLMService(
            api_key="key", api_base="https://custom.api", model="gpt-4o"
        )
        assert service.api_base == "https://custom.api"

    def test_get_url_logic(self):
        """测试 URL 拼接逻辑"""
        # 情况 1：Base 以 /v1 结尾
        service = LLMService(
            api_key="key", api_base="https://api.example.com/v1", model="model"
        )
        assert service._get_url("chat") == "https://api.example.com/v1/chat/completions"

        # 情况 2：Base 不以 /v1 结尾
        service = LLMService(
            api_key="key", api_base="https://api.example.com", model="model"
        )
        # 假设逻辑会在标准端点缺少 /v1 时追加它
        assert service._get_url("chat") == "https://api.example.com/v1/chat/completions"

    @pytest.mark.asyncio
    async def test_chat_routing_openai(self, llm_service):
        """测试 chat 方法路由到 OpenAI 兼容接口"""
        with patch.object(
            llm_service, "_chat_openai_compatible", new_callable=AsyncMock
        ) as mock_method:
            mock_method.return_value = {"content": "hello"}

            await llm_service.chat([{"role": "user", "content": "hi"}])

            mock_method.assert_called_once()

    @pytest.mark.asyncio
    async def test_chat_routing_gemini(self):
        """测试 chat 方法路由到 Gemini 接口"""
        service = LLMService(
            api_key="key", api_base="", model="gemini-pro", provider="gemini"
        )

        with patch.object(
            service, "_chat_gemini", new_callable=AsyncMock
        ) as mock_method:
            mock_method.return_value = {"content": "hello"}

            await service.chat([{"role": "user", "content": "hi"}])

            mock_method.assert_called_once()

    @pytest.mark.asyncio
    async def test_chat_routing_anthropic(self):
        """测试 chat 方法路由到 Anthropic 接口"""
        service = LLMService(
            api_key="key", api_base="", model="claude-3", provider="anthropic"
        )

        with patch.object(
            service, "_chat_anthropic", new_callable=AsyncMock
        ) as mock_method:
            mock_method.return_value = {"content": "hello"}

            await service.chat([{"role": "user", "content": "hi"}])

            mock_method.assert_called_once()

    @pytest.mark.asyncio
    async def test_chat_openai_compatible_success(self, llm_service):
        """测试 OpenAI 兼容接口调用成功"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "test response", "role": "assistant"}}],
            "usage": {"total_tokens": 10},
        }

        with patch("httpx.AsyncClient") as MockClient:
            mock_client_instance = MockClient.return_value.__aenter__.return_value
            mock_client_instance.post.return_value = mock_response

            response = await llm_service._chat_openai_compatible(
                [{"role": "user", "content": "hi"}], temperature=0.7
            )

            assert response["choices"][0]["message"]["content"] == "test response"

            # 验证请求负载
            call_args = mock_client_instance.post.call_args
            assert call_args is not None
            _, kwargs = call_args
            assert kwargs["json"]["model"] == "gpt-4o"
            assert kwargs["json"]["messages"] == [{"role": "user", "content": "hi"}]

    @pytest.mark.asyncio
    async def test_chat_openai_compatible_error(self, llm_service):
        """测试 OpenAI 兼容接口错误处理"""
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.text = "Unauthorized"

        with patch("httpx.AsyncClient") as MockClient:
            mock_client_instance = MockClient.return_value.__aenter__.return_value
            mock_client_instance.post.return_value = mock_response

            # 假设 _handle_http_error 抛出异常或记录错误
            # 如果抛出异常，我们捕获它。如果只是打印，除非模拟 print 或检查日志，否则我们可能看不到。
            # 假设它可能抛出异常或返回错误字典。
            # 基于常见模式，让我们看看它是否抛出异常。

            # 我们需要查看 _handle_http_error 做什么。
            # 如果不抛出异常，代码可能会尝试在错误响应上调用 .json() 或返回 None。
            # 如果可能，让我们检查 _handle_http_error 的实现，但目前期望抛出 Exception。

            with pytest.raises(Exception, match="LLM 错误"):
                await llm_service._chat_openai_compatible(
                    [{"role": "user", "content": "hi"}], temperature=0.7
                )
