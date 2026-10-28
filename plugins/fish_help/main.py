"""被冒犯时 @爸爸求助。

流程：
  1. 人格约定：她判断"别人说话让她不舒服"时，在回复末尾写一行隐藏暗号 [[求助]]。
  2. on_llm_response：把暗号从正文里删掉（不让人看见、也不留在对话记忆里），
     并在事件上打一个标记。
  3. on_decorating_result：如果打了标记、且当前是群聊，就往消息开头插一个真正的
     @爸爸（At 消息段），这样群里能看到她当众喊爸。
"""

from astrbot.api import logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.message_components import At, Plain
from astrbot.api.provider import LLMResponse
from astrbot.api.star import Context, Star, register

_ADMIN = "<爸爸的QQ号>"
_MARK = "[[求助]]"


@register("fish_help", "local", "被冒犯时 @爸爸", "1.0.0")
class FishHelp(Star):
    def __init__(self, context: Context):
        super().__init__(context)

    @filter.on_llm_response()
    async def strip_mark(self, event: AstrMessageEvent, resp: LLMResponse):
        text = resp.completion_text or ""
        if _MARK not in text:
            return
        cleaned = text.replace(_MARK, "").rstrip()
        if cleaned.strip() == "":
            cleaned = "爸，你看他"
        resp.completion_text = cleaned
        event.set_extra("fish_help_needed", True)
        logger.info(f"[fish_help] 触发求助 group={event.get_group_id()}")

    @filter.on_decorating_result()
    async def add_at(self, event: AstrMessageEvent):
        if not event.get_extra("fish_help_needed", False):
            return
        if event.is_private_chat():
            return
        # 爸爸本人在说话，就没有"叫爸爸"的必要
        if str(event.get_sender_id()) == _ADMIN:
            return

        result = event.get_result()
        if not result or not result.chain:
            return
        if any(isinstance(c, At) and str(getattr(c, "qq", "")) == _ADMIN for c in result.chain):
            return
        result.chain.insert(0, At(qq=_ADMIN))
        result.chain.insert(1, Plain(" "))
        event.set_result(result)
