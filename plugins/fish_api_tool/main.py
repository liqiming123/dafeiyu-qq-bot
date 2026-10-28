"""大肥鱼的接口工具 —— 她想调就调（function calling 模式）。

替代之前"关键词匹配 + [[发图]] 暗号"那套：
  - 系统提示里给她一份接口清单（图片/视频/文字分组）
  - 她自己判断要不要调、调哪个，直接调 call_api 工具
  - 图片/视频：工具里当场取图、转 base64、发出去，返回"已发出"，
    她的解说在下一轮跟着出（图先到、话跟上）
  - 文字：原文作为工具结果返回，她用自己的语气转述

聚合插件（astrbot_plugin_apis）只当"接口库 + 取数引擎"用，
它的关键词自动触发已打补丁停用。
"""

import asyncio
import base64
import re
import os
import time
from urllib.parse import unquote, urlparse

from astrbot.api import llm_tool, logger
from astrbot.api.event import AstrMessageEvent, MessageChain
from astrbot.api.event import filter as event_filter
from astrbot.api.message_components import Record, Video
from astrbot.api.provider import ProviderRequest
from astrbot.api.star import Context, Star, register
from astrbot.core.star.star import star_map

_MAX_MB = 30
_CATALOG_TTL = 600  # 接口清单缓存 10 分钟
_CATALOG_CAP = 40  # 每组最多列 40 个，防止提示词爆炸

# 性感/擦边类接口（推荐备选时用来对内容）
_HOT_RE = re.compile(r"(妞|色|骚|腿|足|辣妹|擦玻璃|变装|萝莉|三坑|美女|妹子|玉足|胸)")

# 内容说明：名字看不出是什么的接口，在这里补一句（没有的只标类型）
_DESC = {
    "看看妞": "美女写真",
    "看看色色": "性感向",
    "看看骚的": "性感向",
    "看看玉足": "玉足",
    "擦玻璃": "擦边舞蹈",
    "蹲下变装": "变装",
    "背影变装": "变装",
    "动漫变装": "二次元变装",
    "看看萝莉": "萝莉",
    "超甜辣妹": "辣妹写真",
    "三坑少女": "JK/洛丽塔",
    "电脑壁纸": "桌面壁纸",
    "高清壁纸": "高清壁纸",
    "手机壁纸": "手机壁纸",
    "看看腿": "腿部",
    "来点二次元": "二次元图",
    "看看猫猫": "猫图",
    "来点龙图": "龙图",
    "来点cos": "cosplay",
    "看看风景": "风景图",
    "读世界": "世界见闻",
}


def _local_path(file: str | None) -> str | None:
    if not file:
        return None
    if file.startswith("file://"):
        return unquote(urlparse(file).path)
    if file.startswith("/"):
        return unquote(file)
    return None


@register("fish_api_tool", "local", "大肥鱼的接口工具", "2.0.0")
class FishApiTool(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        self._catalog: str = ""
        self._catalog_at: float = 0.0

    # ---------- 聚合插件实例与清单 ----------

    def _agg(self):
        for meta in list(star_map.values()):
            if getattr(meta, "name", None) == "astrbot_plugin_apis" and getattr(
                meta, "activated", False
            ):
                inst = getattr(meta, "star_cls", None)
                if inst is not None and hasattr(inst, "core"):
                    return inst
        return None

    def _build_catalog(self) -> str:
        now = time.time()
        if self._catalog and now - self._catalog_at < _CATALOG_TTL:
            return self._catalog
        agg = self._agg()
        groups: dict[str, list[str]] = {"图片": [], "视频": [], "文字": []}
        if agg is not None:
            try:
                for e in agg.core.api_mgr.list_enabled_entries():
                    if not e.valid:
                        continue
                    dt = e.data_type
                    if dt.is_text:
                        groups["文字"].append(e.name)
                    elif getattr(dt, "is_video", False):
                        groups["视频"].append(e.name)
                    else:
                        groups["图片"].append(e.name)
            except Exception as ex:
                logger.warning(f"[fish_api_tool] 读接口池失败: {ex}")
        # 名字(类型·内容) 逐个标注，让她知道调的是什么、出来的是图还是视频
        def tag(name: str, kind: str) -> str:
            d = _DESC.get(name)
            return f"{name}({kind}·{d})" if d else f"{name}({kind})"

        parts = []
        for k, kind in (("图片", "图"), ("视频", "视频"), ("文字", "文字")):
            names = [tag(n, kind) for n in groups[k][:_CATALOG_CAP]]
            more = len(groups[k]) - len(names)
            tail = f" 等{more}个" if more > 0 else ""
            parts.append(f"{k}类：{'、'.join(names)}{tail}")
        self._catalog = "；".join(parts)
        self._catalog_at = now
        return self._catalog

    # ---------- 每轮请求：把清单塞给她 ----------

    @event_filter.on_llm_request()
    async def tell_catalog(self, event: AstrMessageEvent, req: ProviderRequest):
        catalog = self._build_catalog()
        if not catalog:
            return
        req.system_prompt = (req.system_prompt or "") + (
            "\n\n【你能直接调用的外部接口（用 call_api 工具，参数填接口名）】\n"
            + catalog
            + "\n常用对照（直接照着调，不用猜）：\n"
            "- 色图 / 美女图 / 妹妹 / 写真 → 调「看看妞」（图）\n"
            "- 色色视频 / 骚的 → 调「看看色色」或「看看骚的」（视频）\n"
            "- 壁纸 → 调「电脑壁纸」（图）\n"
            "- 笑话 → 调「讲个笑话」（文字）\n"
            "\n每个名字后面的括号是【类型·内容】，按这个挑，别瞎猜：\n"
            "- 对方要**图**（色图、写真、壁纸、照片）→ 只挑标「图」的\n"
            "- 对方要**视频** → 挑标「视频」的\n"
            "- 名字跟对方要的对不上（比如要图但那名字标着视频），换一个匹配的，别硬调\n"
            "图/视频调完当场发出去，你下一句解说；文字拿到原文用自己的语气转述，别照念。"
            "调不到或没有的，直说「这个我这边没有」。别一次连调好几个。"
        )

    # ---------- 工具本体 ----------

    async def _to_sendable(self, comp):
        if not isinstance(comp, Video | Record):
            return comp
        path = _local_path(getattr(comp, "file", None))
        if not path or not os.path.exists(path):
            return comp
        size_mb = os.path.getsize(path) / 1048576
        if size_mb > _MAX_MB:
            logger.warning(f"[fish_api_tool] 媒体过大 {size_mb:.1f}MB，跳过")
            return None
        try:
            b64 = base64.b64encode(open(path, "rb").read()).decode()
            return type(comp).fromBase64(b64)
        except Exception as e:
            logger.warning(f"[fish_api_tool] 转 base64 失败: {e}")
            return comp

    def _find_entry(self, agg, name: str):
        name = (name or "").strip()
        entries = agg.core.api_mgr.list_enabled_entries()
        for e in entries:  # 精确名
            if e.name == name:
                return e
        for e in entries:  # 关键词
            if name in (e.keywords or []):
                return e
        for e in entries:  # 名字包含
            if name and name in e.name:
                return e
        return None

    def _entry_kind(self, entry) -> str:
        dt = entry.data_type
        if getattr(dt, "is_video", False):
            return "视频"
        return "文字" if dt.is_text else "图"

    _VID_RE = re.compile(r"(视频|影片|小电影)")
    _IMG_RE = re.compile(r"(图|照片|写真|头像|壁纸)")

    def _user_wants(self, event: AstrMessageEvent) -> str:
        """从对方原话判断要的是图还是视频（视频词优先）。她说什么都不算数。"""
        msg = event.message_str or ""
        if self._VID_RE.search(msg):
            return "视频"
        if self._IMG_RE.search(msg):
            return "图"
        return ""

    @llm_tool(name="call_api")
    async def call_api(self, event: AstrMessageEvent, name: str) -> str:
        """调用一个外部接口拿真实内容。图片/视频会直接发给对方（你下一句接着解说即可）；文字类会把原文返回给你转述。

        Args:
            name(string): 接口名，从系统提示里的接口清单中选。
        """
        agg = self._agg()
        if agg is None:
            return "接口库没连上，这次调不了"

        entry = self._find_entry(agg, name)
        if entry is None:
            return f"没有叫「{name}」的接口。可用的在系统提示里的清单里，别瞎猜"

        # 类型硬校验：按**对方原话**里要的类型来，调错了打回并给正确选项
        want = self._user_wants(event)
        actual = self._entry_kind(entry)
        if want and want in ("图", "视频", "文字") and want != actual:
            alts: list[str] = []
            try:
                wanted = [
                    e for e in agg.core.api_mgr.list_enabled_entries()
                    if e.valid and self._entry_kind(e) == want
                ]
                # 内容对口优先：被打回的是性感类，就推性感的图/视频
                if _HOT_RE.search(entry.name):
                    alts = [e.name for e in wanted if _HOT_RE.search(e.name)][:6]
                if not alts:
                    alts = [e.name for e in wanted][:6]
            except Exception:
                pass
            hint = f"直接换这些（都是{want}）：{'、'.join(alts)}" if alts else f"清单里没有「{want}」类的"
            return f"打回：「{entry.name}」是{actual}，但对方要的是{want}。{hint}。重新调其中一个"

        try:
            entry.updated_params = await agg._build_params(event, entry, [])
            data = await asyncio.wait_for(
                agg.core.data_service.fetch(entry, use_local=agg.cfg.use_local),
                timeout=25,
            )
        except Exception as e:
            logger.warning(f"[fish_api_tool] 调「{entry.name}」失败: {e}")
            return f"「{entry.name}」这个接口现在挂了，跟对方说查不到"

        if data is None:
            return f"「{entry.name}」没取到内容，跟对方说这次没有"

        try:
            if data.data_type.is_text and data.final_text:
                return str(data.final_text)[:1500]
            comp = await agg.data_to_comp(data)
        except Exception as e:
            logger.warning(f"[fish_api_tool] 转换失败: {e}")
            return "取到了但发不出去，跟对方说这次翻车了"

        comp = await self._to_sendable(comp)
        if comp is None:
            return "文件太大发不出去，跟对方说这次不行"
        try:
            await event.send(MessageChain([comp]))
            return f"「{entry.name}」已经发出去了，对方看得到，你直接接一句自己的话，别说「已发送」"
        except Exception as e:
            logger.warning(f"[fish_api_tool] 发送失败: {type(e).__name__}: {e!r}")
            return "发图片失败了，跟对方说这次没弄到"
