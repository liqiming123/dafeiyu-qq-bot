"""大肥鱼的空间动态 —— 心情驱动，想发就发，一天最多一条。

发不发由她的人格决定（提示词里写了什么情况值得发），
频率由这里硬拦：KV 记着今天发没发过，发过直接打回。
真正的发布走 astrbot_plugin_qzone 的 service（cookie 登录那套都是它的）。
"""

from datetime import datetime
from zoneinfo import ZoneInfo

from astrbot.api import llm_tool, logger
from astrbot.api.event import AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.core.star.star import star_map

_TZ = ZoneInfo("Asia/Shanghai")


@register("fish_qzone", "local", "大肥鱼的空间动态", "1.0.0")
class FishQzone(Star):
    def __init__(self, context: Context):
        super().__init__(context)

    def _qzone(self):
        for meta in list(star_map.values()):
            if getattr(meta, "name", None) == "astrbot_plugin_qzone" and getattr(
                meta, "activated", False
            ):
                inst = getattr(meta, "star_cls", None)
                if inst is not None and hasattr(inst, "service"):
                    return inst
        return None

    @llm_tool(name="post_qzone")
    async def post_qzone(self, event: AstrMessageEvent, content: str) -> str:
        """把你的一句话发到你的 QQ 空间（说说）。一天只能发一条，值得发的时候再用。

        Args:
            content(string): 说说内容，一两句，像随手发的。
        """
        text = (content or "").strip()
        if not text:
            return "内容是空的，没发"

        today = datetime.now(_TZ).strftime("%Y-%m-%d")
        last = await self.get_kv_data("last_post_date", "")
        if last == today:
            return "今天的空间已经发过一条了，明天再说。跟对方说一声改天发"

        qz = self._qzone()
        if qz is None:
            return "空间插件没连上，这次发不了"

        try:
            post = await qz.service.publish_post(text=text)
        except Exception as e:
            logger.warning(f"[fish_qzone] 发布失败: {type(e).__name__}: {e}")
            return "空间这会儿发不出去（可能掉登录了），跟对方说待会儿再试"

        await self.put_kv_data("last_post_date", today)
        logger.info(f"[fish_qzone] 发了一条说说: {text[:40]}")
        return (
            "发出去了，空间里能看到。"
            "顺口跟对方提一句就行，别报「已发送」这种客服话"
        )
