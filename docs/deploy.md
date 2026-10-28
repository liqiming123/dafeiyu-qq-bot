# 部署指南（macOS 实测，Linux 通用）

从零把大肥鱼跑起来。以下在 Apple Silicon Mac（macOS 26）实测通过；Linux 跳过 Colima 部分直接用 Docker。

## 0. 你需要准备

- 一台能跑 Docker 的机器（4C/8G 起步）
- 一个 QQ 小号（**务必用小号**，第三方协议端有风控风险）
- 智谱 API Key（对话，glm-5.3-flash 很便宜）
- 阿里云百炼 Key（语音 + 记忆向量，可选）
- DeepSeek Key（没饭吃预警的余额来源，可选）

## 1. 装 Docker 运行时

macOS 推荐 Colima（无需 Docker Desktop）：

```bash
brew install colima docker docker-compose
mkdir -p ~/.docker/cli-plugins
ln -sfn /opt/homebrew/lib/docker/cli-plugins/docker-compose ~/.docker/cli-plugins/docker-compose

# 国内网络注意：Colima 虚拟机里拉镜像要走宿主机代理（Clash 等）
# 实测需要给 VM 里的 dockerd 配 http-proxy 指向宿主机（如 http://192.168.5.2:7897）
colima start --cpu 4 --memory 8 --disk 100
```

## 2. 起容器

```bash
git clone https://github.com/liqiming123/dafeiyu-qq-bot.git
cd dafeiyu-qq-bot
cp .env.example .env    # 填 key 和 VNC 密码
docker compose up -d
```

首次启动后打开 **http://127.0.0.1:6081/vnc.html**（密码=你的 VNC_PASSWD），用手机 QQ 扫码登录。

> ⚠️ 别随便重启 snowluma 容器——每次重启都可能要求重新扫码。日常只重启 astrbot。

## 3. 配 AstrBot

1. 打开 **http://127.0.0.1:6185**，首次密码在 `docker compose logs astrbot` 里，登录后改掉
2. 「服务提供商」加对话模型（智谱 `glm-5.3-flash`，OpenAI 兼容格式，api_base=`https://open.bigmodel.cn/api/paas/v4/`）
3. 把 `plugins/` 下 7 个目录复制进 `data/astrbot/plugins/`
4. `patches/zhipu_source.py` 已通过 compose 挂载，无需手动操作
5. 人格：把 `persona/大肥鱼.md` 里的 `<爸爸的QQ号>` 等占位符换成真实值后，用 `scripts/apply-persona.py` 写入

```bash
python3 scripts/apply-persona.py && docker compose restart astrbot
```

## 4. 可选组件

| 组件 | 用途 | 怎么装 |
| --- | --- | --- |
| 表情包 | DeepSeek 二创 174 张 | 插件市场装 [meme_manager](https://github.com/anka-afk/astrbot_plugin_meme_manager) + 装 [deepseek-fanart-meme-pack](https://github.com/anka-afk/deepseek-fanart-meme-pack)，`selection_rules.json` 默认包指过去，概率调 100，再打"视觉挑图"补丁 |
| 语音 | qwen3-tts-flash（Bella 萝莉音） | 百炼 key 写进 fish_voice 读的 provider_sources（或环境变量） |
| 长期记忆 | LivingMemory | 插件市场装，嵌入模型用百炼 `text-embedding-v4`（**注意适配器读 `embedding_api_key`/`embedding_api_base` 字段**，维度 1024） |
| 万能解析 | B站/抖音链接转视频 | 插件市场装 [astrbot_plugin_parser](https://github.com/Zhalslar/astrbot_plugin_parser) |

## 5. 日常操作

```bash
./scripts/up.sh        # 启动（自动拉起 Colima）
./scripts/down.sh      # 停止（--vm 连虚拟机一起停）
./scripts/logs.sh -f   # 实时日志
python3 scripts/reset-quota.py   # 重置"没饭吃"计数
```

## 踩坑实录

1. **Colima 里拉不动镜像**：VM 内 dockerd 走宿主机代理（Clash 开允许局域网），或给 daemon 配 registry-mirrors
2. **智谱 GLM-5 巨慢**：默认开"深度思考"，必须打 `patches/zhipu_source.py` 关掉
3. **视频/语音发不出（ENOENT）**：AstrBot 和 SnowLuma 是两个容器，文件路径互不可见——发送前必须转 base64
4. **AstrBot 机器人 ID 改不了**（WebUI 报 `Bot id cannot be changed`）：改 `cmd_config.json` 的 `platform[0].id` 再重启
5. **表情包图文不符**：两层修复——人格里写分类对照表 + 打视觉挑图补丁
6. **macOS 开机自启**：`~/Documents` 受 TCC 保护，launchd 读不到脚本；用双击 `启动QQ机器人.command` 或把目录挪到 `~/` 下

## 风险提示

- SnowLuma 是第三方协议端（hook 注入 QQ 进程），账号有被封的可能，**只跑小号**
- 空间自动发布、群聊高频率回复都是风控敏感区，频率别调高
- 本项目仅供学习研究
