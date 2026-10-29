# 本地补丁清单

这些补丁直接改在第三方插件源码里，插件更新会被覆盖，需要重打。每条都标注了位置和作用。

## 1. zhipu_source.py（智谱关思考）

**文件**：`patches/zhipu_source.py`（挂载覆盖容器内同名文件，重建不丢）

```yaml
# compose.yaml
- ./patches/zhipu_source.py:/AstrBot/astrbot/core/provider/sources/zhipu_source.py:ro
```

**作用**：GLM-5 系列默认开"深度思考"，又慢又吃 max_tokens。补丁在请求里强制加 `thinking: {"type": "disabled"}`，端到端回复从 10~20s 降到 ~6s。

## 2. meme_manager 视觉挑图

**文件**：`astrbot_plugin_apis`…不对，是 `meme_manager/mixins/event_handlers.py`，搜 `[本地补丁] 视觉挑图`。

**作用**：原版分类内**随机抽一张**表情，经常和她的话不搭。补丁把 `random.choice` 换成：她这句回复 + 分类内最多 12 张候选图 → glm-5.3-flash 视觉挑最贴的一张（挑错/超时回退随机）。每张表情多 3~4.5 秒和一次视觉调用。

**代价**：函数约 60 行，更新插件后需重打（同样的锚点替换）。

## 3. astrbot_plugin_apis 先判断后调接口

**文件**：`astrbot_plugin_apis/main.py`，搜 `[本地补丁 v3]`。

**作用**：原版关键词命中就立刻调接口发原文。补丁后：文字类照旧取；图/视频类只把名字"报价"给模型，她决定给（写暗号）才真正调接口。配合 fish_api_tool 使用。

## 4. astrbot_plugin_qzone 定时转心情

**文件**：`astrbot_plugin_qzone/main.py`，搜 `[本地补丁]`。

**作用**：停用插件自己的定时发布/自动评论（`publish_cron=""`、`comment_cron=""`、`read_prob=0`），停用它的 `llm_publish_feed` 工具（会绕过 fish_qzone 的一天一条限制）。发布引擎保留给 fish_qzone 用。

## 5. astrbot_plugin_qzone 评论修复（三处）

- `core/qzone/client.py`：`parsed.get("data", {}).get("ret")` 在 QZone 返回 `data` 为**字符串**时直接崩（`'str' object has no attribute 'get'`，这就是评论区报错的元凶）→ 补 isinstance 判断
- `core/llm_action.py` `generate_comment`：评论 prompt 原来只有 `[帖子内容]`，她**不知道这条说是谁发的**，在爸爸空间里也把爸爸当外人怼 → 补 `[帖子作者]：名字（QQ:xxx）`
- `main.py` llm_view_feed 的 except：`logger.error(e)` 对空异常啥也不记 → 补异常类型和堆栈
- 配置 `llm.comment_prompt` / `reply_prompt`：写明"作者 QQ 是爸爸 → 用对爸爸的语气（傲娇但亲）；别人 → 有礼貌有底线"

## 6. meme_manager 不注册 search_memes 工具

**文件**：`meme_manager/main.py`，搜 `[本地补丁] 不注册为 LLM 工具`。

**作用**：注释掉 `@llm_tool(name="search_memes")`，避免每条请求都带工具 schema 拖慢回复。
