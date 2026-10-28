"""语音她自己决定。

AstrBot 自带的 TTS 是概率触发（随机 33% 全转语音），不看内容。
这里改成她判断：回复末尾写 [[语音]] 暗号 → 整条回复转成语音；不写就是纯文字。
暗号在 on_llm_response 里删掉，转换在 on_decorating_result 里做。
合成直接调阿里云百炼 qwen3-tts-flash（Momo），不依赖 AstrBot 的 TTS 管线。
"""

import json
import uuid
from pathlib import Path

import httpx

from astrbot.api import logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.message_components import Plain, Record
from astrbot.api.provider import LLMResponse
from astrbot.api.star import Context, Star, register

_MARK = "[[语音]]"
_API = "https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation"
_TEMP = Path("/AstrBot/data/temp")


def _get_key() -> str:
    try:
        cfg = json.load(open("/AstrBot/data/cmd_config.json", encoding="utf-8-sig"))
        for s in cfg.get("provider_sources", []):
            if s.get("id") == "dashscope_tts":
                k = s.get("api_key", "")
                return k[0] if isinstance(k, list) and k else str(k)
    except Exception:
        pass
    return ""


@register("fish_voice", "local", "语音她自己决定", "1.0.0")
class FishVoice(Star):
    def __init__(self, context: Context):
        super().__init__(context)

    @filter.on_llm_response()
    async def catch_mark(self, event: AstrMessageEvent, resp: LLMResponse):
        text = resp.completion_text or ""
        if _MARK not in text:
            return
        resp.completion_text = text.replace(_MARK, "").rstrip()
        event.set_extra("fish_voice", True)
        logger.info("[fish_voice] 她想说话，这条转语音")

    @filter.on_decorating_result()
    async def speak(self, event: AstrMessageEvent):
        if not event.get_extra("fish_voice", False):
            return
        result = event.get_result()
        if result is None or not result.chain:
            return

        texts = [c.text.strip() for c in result.chain if isinstance(c, Plain) and c.text.strip()]
        if not texts:
            return
        # 整条回复合成一段语音（跟大肥鱼配置包的做法一致）
        speech = "\n".join(texts)
        wav = await self._tts(speech)
        if wav is None:
            logger.warning("[fish_voice] 合成失败，这条照常发文字")
            return
        result.chain = [Record.fromFileSystem(str(wav))]
        event.set_result(result)

    async def _tts(self, text: str) -> Path | None:
        key = _get_key()
        if not key:
            return None
        body = {
            "model": "qwen3-tts-flash",
            "input": {"text": text[:600], "voice": "Bella", "language_type": "Chinese"},
        }
        try:
            async with httpx.AsyncClient(timeout=45) as cli:
                r = await cli.post(_API, headers={"Authorization": "Bearer " + key}, json=body)
                data = r.json()
                url = (data.get("output") or {}).get("audio", {}).get("url")
                if not url:
                    logger.warning(f"[fish_voice] 合成返回异常: {str(data)[:150]}")
                    return None
                audio = await cli.get(url, timeout=60)
        except Exception as e:
            logger.warning(f"[fish_voice] 合成请求失败: {type(e).__name__}: {e}")
            return None
        _TEMP.mkdir(parents=True, exist_ok=True)
        path = _TEMP / f"fish_voice_{uuid.uuid4().hex[:8]}.wav"
        path.write_bytes(audio.content)
        return path
