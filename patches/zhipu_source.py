# This file was originally created to adapt to glm-4v-flash, which only supports one image in the context.
# It is no longer specifically adapted to Zhipu's models. To ensure compatibility, this


from typing import Any

from ..register import register_provider_adapter
from .openai_source import ProviderOpenAIOfficial


@register_provider_adapter("zhipu_chat_completion", "智谱 Chat Completion 提供商适配器")
class ProviderZhipu(ProviderOpenAIOfficial):
    def __init__(
        self,
        provider_config: dict,
        provider_settings: dict,
    ) -> None:
        super().__init__(provider_config, provider_settings)

    def _apply_provider_specific_request_overrides(
        self,
        payloads: dict[str, Any],
        extra_body: dict[str, Any],
    ) -> None:
        super()._apply_provider_specific_request_overrides(payloads, extra_body)
        # [本地补丁] GLM-5 系列默认开"深度思考"：回复又慢、思考还吃 max_tokens。
        # 智谱 OpenAI 兼容接口支持 thinking 参数，这里每次请求都关掉。
        extra_body["thinking"] = {"type": "disabled"}
