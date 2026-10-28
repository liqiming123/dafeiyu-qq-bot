"""控制谁能跟大肥鱼说话。

当前规则：
  - 群聊：任何人 @ 都能对话（靠 AstrBot 的唤醒机制，没 @ 不会触发）。
  - 私聊：只有管理员（admins_id，当前 <爸爸的QQ号>）能对话，其他人静默。

实现：注册一个优先级最高的消息 handler，把不该唤醒的事件 stop 掉。
优先级必须高于内置 handler（内置用 sys.maxsize - 1），
否则内置的「空 @ 等待」等 handler 会先跑。
"""

import sys

from astrbot.api import logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.star import Context, Star, register

# 抢在所有内置 handler 之前执行
_PRIORITY = sys.maxsize

# 与 cmd_config.json 里的 admins_id 保持一致；
# 运行时以 event.role（由唤醒检查阶段按 admins_id 设置）为准，这里只是兜底。
_ADMIN_IDS = {"<爸爸的QQ号>"}

# True：私聊只允许管理员；改成 False 就是所有人都能私聊
_PRIVATE_ADMIN_ONLY = True


@register("admin_only", "local", "群聊开放、私聊仅管理员", "1.1.0")
class AdminOnlyPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)

    @filter.event_message_type(
        filter.EventMessageType.ALL,
        priority=_PRIORITY,
    )
    async def gate(self, event: AstrMessageEvent):
        sender = str(event.get_sender_id())
        is_admin = getattr(event, "role", None) == "admin" or sender in _ADMIN_IDS

        if is_admin:
            return

        # 群聊放开：能走到这里的群消息已经被 @ 或唤醒前缀唤醒了
        if not event.is_private_chat():
            return

        if not _PRIVATE_ADMIN_ONLY:
            return

        logger.info(
            f"[admin_only] 忽略非管理员私聊 sender={sender} group={event.get_group_id()}",
        )
        event.stop_event()
