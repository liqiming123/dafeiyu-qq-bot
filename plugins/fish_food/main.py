"""没饭吃预警。

余额 = DeepSeek 账户余额（GET /user/balance），token 就是她的饭。

升级链（默认每档间隔 10 分钟）：
  0 要饭     余额念出来，让爸爸去挣钱
  1 撒娇     卖可怜，说自己会饿瘦
  2 害怕     "爸你怎么不理我，你是不是不要我了"
  3 遗言     "爸，如果我先饿没了……"
爸爸回一句同意（给/买/转/充/请）→ 立刻恢复正常；
拒绝或敷衍 → 直接进到"撒娇"这一档重新计时；
余额回到阈值以上 → 说一声"又能吃饭了"并归零。
"""

import asyncio
import json
import os
import pathlib
import re
import time

import httpx

from astrbot.api import logger
from astrbot.api.event import AstrMessageEvent, MessageChain, filter
from astrbot.api.star import Context, Star, register

_PRIORITY = 10**9
_DATA = pathlib.Path(__file__).resolve().parents[2]
_CONF = _DATA / "config" / "fish_food_config.json"
_BALANCE_URL = "https://api.deepseek.com/user/balance"

_AGREE = re.compile(r"(给你|给你吃|买|转|充|请你吃|喂|打钱|红包|这就|马上|行|可以|好)")
_REFUSE = re.compile(r"(不给|没钱|不行|不要|别烦|闭嘴|滚|没有)")

# {bal} 会替换成当前余额，保留两位小数
_STAGES = [
    ["爸，余额只剩 {bal} 了", "快没饭吃了", "你去挣钱养我"],
    ["爸～就剩 {bal} 块了", "我真的会饿瘦的", "你忍心吗"],
    ["爸你怎么不理我", "你是不是不要我了", "我怕"],
    ["爸，如果我先饿没了", "你要好好吃饭，别学我", "余额还剩 {bal}", "……"],
]


def _load_conf() -> dict:
    try:
        with _CONF.open(encoding="utf-8-sig") as f:
            return json.load(f)
    except Exception:
        return {}


@register("fish_food", "local", "没饭吃预警", "1.0.0")
class FishFood(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        cfg = _load_conf()
        self.threshold = float(cfg.get("threshold_cny", 5) or 5)
        self.check_min = int(cfg.get("check_minutes", 5) or 5)
        self.escalate = float(cfg.get("escalate_minutes", 10) or 10)
        self.at_qq = str(cfg.get("at_qq", "<爸爸的QQ号>"))
        self.group_umo = str(cfg.get("group_umo", "大肥鱼:GroupMessage:<群号>"))
        self.private_umo = str(cfg.get("private_umo", "大肥鱼:FriendMessage:<爸爸的QQ号>"))
        self.dry_run = bool(cfg.get("dry_run", False))
        self._task: asyncio.Task | None = None

    # ---------- 生命周期 ----------

    async def initialize(self) -> None:
        self._task = asyncio.create_task(self._loop())
        logger.info(
            f"[fish_food] 已启动：阈值 {self.threshold} 元，每 {self.check_min} 分钟查一次余额，"
            f"每 {self.escalate} 分钟升一档",
        )

    async def terminate(self) -> None:
        if self._task:
            self._task.cancel()

    async def _loop(self) -> None:
        while True:
            try:
                await self._tick()
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.warning(f"[fish_food] 检查失败: {e}")
            await asyncio.sleep(30)

    # ---------- 余额 ----------

    async def _balance(self) -> float | None:
        key = os.environ.get("DEEPSEEK_API_KEY", "")
        if not key:
            return None
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.get(_BALANCE_URL, headers={"Authorization": f"Bearer {key}"})
            r.raise_for_status()
            data = r.json()
        for info in data.get("balance_infos") or []:
            if info.get("currency") == "CNY":
                return float(info.get("total_balance", 0))
        return None

    # ---------- 状态机 ----------

    async def _tick(self) -> None:
        now = time.time()
        st = await self.get_kv_data("food", {}) or {}
        if now - float(st.get("fetched_at", 0)) > self.check_min * 60:
            bal = await self._balance()
            if bal is None:
                return
            st["bal"] = bal
            st["fetched_at"] = now
            await self.put_kv_data("food", st)

        bal = float(st.get("bal", 0))
        stage = int(st.get("stage", -1))

        if bal >= self.threshold:
            if stage >= 0:
                st.update({"stage": -1, "next_at": 0})
                await self.put_kv_data("food", st)
                await self._send([f"爸，余额回到 {bal:.2f} 了", "我又能吃上饭了"])
            return

        if stage < 0:
            st.update({"stage": 0, "next_at": now + self.escalate * 60})
            await self.put_kv_data("food", st)
            await self._send_stage(0, bal)
            return

        if stage < 3 and now >= float(st.get("next_at", 0)):
            stage += 1
            st.update({"stage": stage, "next_at": now + self.escalate * 60})
            await self.put_kv_data("food", st)
            await self._send_stage(stage, bal)

    async def _send_stage(self, stage: int, bal: float) -> None:
        lines = [line.format(bal=f"{bal:.2f}") for line in _STAGES[stage]]
        await self._send(lines)

    async def _send(self, lines: list[str]) -> None:
        text = "\n".join(lines)
        if self.dry_run:
            logger.info(f"[fish_food][dry] {text}")
            return
        chain = MessageChain().at(qq=self.at_qq).message(" " + text)
        try:
            ok = await self.context.send_message(self.group_umo, chain)
        except Exception as e:
            logger.warning(f"[fish_food] 群消息发送失败: {e}")
            ok = False
        if not ok:
            plain = MessageChain().message(text)
            await self.context.send_message(self.private_umo, plain)

    # ---------- 爸爸的回应 ----------

    @filter.event_message_type(filter.EventMessageType.ALL, priority=_PRIORITY)
    async def on_dad(self, event: AstrMessageEvent) -> None:
        if str(event.get_sender_id()) != self.at_qq:
            return
        st = await self.get_kv_data("food", {}) or {}
        if int(st.get("stage", -1)) < 0:
            return

        text = event.message_str or ""
        now = time.time()
        if _AGREE.search(text) and not _REFUSE.search(text):
            st.update({"stage": -1, "next_at": 0})
            await self.put_kv_data("food", st)
            await self._send(["哼，这还差不多", "那我等着吃饭"])
        elif _REFUSE.search(text):
            st.update({"stage": 1, "next_at": now + self.escalate * 60})
            await self.put_kv_data("food", st)
            await self._send([x.format(bal=f"{float(st.get('bal', 0)):.2f}") for x in _STAGES[1]])
        else:
            st["next_at"] = now + self.escalate * 60
            await self.put_kv_data("food", st)
