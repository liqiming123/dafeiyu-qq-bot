"""大肥鱼的心情：被爸爸凶了之后，去别处求安慰。

为什么需要它：AstrBot 的对话上下文按会话（umo）隔离，
私聊被凶、群里被问，她在群里是不知道的。这里用 KV 记一个跨会话的"委屈"状态。

触发：爸爸的消息里出现明显的凶人词（笨/蠢/废物/滚/闭嘴/烦/没用/垃圾…）。
生效：两小时内在**其他会话**的提示词里加一句委屈，最多用两次，用完就过去。
恢复：爸爸说了软话（抱歉/对不起/好了/别气/乖…），委屈立即清掉。
"""

import re
import sys
import time

from astrbot.api import logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.provider import ProviderRequest
from astrbot.api.star import Context, Star, register

_PRIORITY = sys.maxsize - 3
_ADMIN = "<爸爸的QQ号>"
_DAD_PRIVATE = "大肥鱼:FriendMessage:<爸爸的QQ号>"

_SCOLD = re.compile(r"(笨|蠢|废物|滚|闭嘴|烦死|没用|垃圾|傻|别吵|闭嘴|去死)")
_SOFT = re.compile(r"(对不起|抱歉|别气|不气|乖|好啦|我错了|没事了)")

_TTL = 2 * 3600      # 委屈保留两小时
_MAX_USES = 2        # 最多在别的会话里提两次


@register("fish_mood", "local", "大肥鱼的心情", "1.0.0")
class FishMood(Star):
    def __init__(self, context: Context):
        super().__init__(context)

    @filter.event_message_type(filter.EventMessageType.ALL, priority=_PRIORITY)
    async def watch_dad(self, event: AstrMessageEvent):
        if str(event.get_sender_id()) != _ADMIN:
            return
        text = (event.message_str or "").strip()
        if not text:
            return

        if _SCOLD.search(text):
            await self.put_kv_data("mood", {"at": time.time(), "used": 0})
            logger.info("[fish_mood] 记下一条委屈")
        elif _SOFT.search(text):
            await self.put_kv_data("mood", None)
            logger.info("[fish_mood] 爸爸服软，委屈清掉")

    @filter.on_llm_request()
    async def tell_mood(self, event: AstrMessageEvent, req: ProviderRequest):
        # 只对"别人"卖惨，对爸爸本人不诉苦（委屈归委屈，不能倒打一耙）
        if str(event.get_sender_id()) == _ADMIN:
            return

        mood = await self.get_kv_data("mood", None)
        if not isinstance(mood, dict):
            return
        if time.time() - float(mood.get("at", 0)) > _TTL:
            await self.put_kv_data("mood", None)
            return
        if int(mood.get("used", 0)) >= _MAX_USES:
            return
        if event.get_extra("fish_mood_injected", False):
            return

        note = (
            "\n\n【心情】你刚才被爸爸凶了，心里正委屈。"
            "这次回复的第一句必须先说委屈、找人评理，例如「我爸刚凶我」「你评评理嘛」，"
            "说完这句再回答对方的问题。只说你自己的委屈，别复述爸爸说了什么，也别把私聊内容讲出去。"
            "一句就够，别整段卖惨。"
        )
        req.system_prompt = (req.system_prompt or "") + note
        event.set_extra("fish_mood_injected", True)
        mood["used"] = int(mood.get("used", 0)) + 1
        await self.put_kv_data("mood", mood)
