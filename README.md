# Digital Person Skill

> 一个数字分身生成器：从公开内容生成 `digital-person-<name>` Skill 包，以及可选的 `CLAUDE.md` / `chatgpt_instructions.md` 导出文件。

## 这是什么

这个仓库本身是生成器，不是最终给 Claude 直接扮演人物的成品 Skill。

- 生成器仓库：你在这里安装依赖、准备数据、运行 `python -m src.pipeline`
- 生成产物：运行后写入 `output/digital-person-<name>/`
- 可选导出：只有显式传入 `--export claude` 或 `--export chatgpt` 时，才会额外生成平台指令文件

## 快速开始

### 1. 安装生成器

要求：

- Python 3.11+
- 一个可用的 LLM API Key：`OPENAI_API_KEY` 或 `ANTHROPIC_API_KEY`

```bash
git clone https://github.com/justinjia0813/digital-person-skill.git
cd digital-person-skill

python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
```

按需编辑 `.env`。完整说明见 [references/setup.md](references/setup.md)。

### 2. 安装校验

依赖安装后，先确认 CLI 能正常加载：

```bash
python -m src.pipeline --help
```

如果这里失败，先不要继续生成；通常是依赖未安装完整或 `.env` 缺失必填项。

### 3. 准备输入

二选一：

```bash
# 方式一：微信公众号 URL 列表，每行一个 URL
cat > urls.txt <<'EOF'
https://mp.weixin.qq.com/s/example-1
https://mp.weixin.qq.com/s/example-2
EOF
```

```bash
# 方式二：本地导出文件
# 支持按 --source 读取 weibo / twitter / wechat_mp 对应数据
```

最低建议：

- 至少 5 篇有观点密度的文章或帖子
- 尽量覆盖同一人的连续表达，而不是零散转发
- 输入过少时，仍可能生成目录，但人格、观点和决策框架会明显变弱

### 4. 首次生成

```bash
python -m src.pipeline \
  --name "某人" \
  --urls urls.txt \
  --skip-vector \
  --export claude
```

如果使用本地文件：

```bash
python -m src.pipeline \
  --name "某人" \
  --input weibo.json \
  --source weibo \
  --skip-vector \
  --export claude
```

## 四段链路总览

| 阶段 | 目标 | 入口 | 输入 | 输出 | 常见失败点 |
|------|------|------|------|------|-----------|
| 安装 | 把生成器跑起来 | `pip install -r requirements.txt` | Python、依赖、`.env` | 可执行 CLI | 缺少依赖、API Key 未配置 |
| 运行 | 生成数字分身资产 | `python -m src.pipeline ...` | URL 列表或本地文件 | `output/digital-person-<name>/` | 输入为空、抓取失败、LLM 阶段失败 |
| 导出 | 生成平台指令文件 | `--export claude` / `--export chatgpt` | 已生成的 Skill 包 | `CLAUDE.md` 或 `chatgpt_instructions.md` | 未显式传 `--export` |
| 部署 | 决定如何使用产物 | 手动复制文件/目录 | 生成结果目录 | 项目级指令或 persona skill | 把生成器仓库和生成产物混为一谈 |

## 对象模型与命名边界

需要严格区分两个对象：

1. 生成器仓库 `digital-person`
   - 你当前克隆和运行的项目
   - 包含 `src/`、`run_web.py`、`README.md`
   - 负责采集、处理、生成和导出
2. 生成产物 `digital-person-<name>`
   - 由流水线创建在 `output/` 下
   - 目录名和生成的 `SKILL.md` 中 `name:` 都使用 `digital-person-<name>`
   - 这是最终可部署的 persona skill 包

因此：

- 不要把本仓库安装到 `~/.claude/skills/digital-person` 后就认为它已经是某个人的分身
- 也不要把生成后的 skill 统一称为 `/digital-person`
- 如果作为 Claude Code Skill 使用，调用名应与生成产物一致，例如 `/digital-person-某人`

## CLI 参数

| 参数 | 说明 |
|------|------|
| `--name` | 人物名称，必填 |
| `--urls` | URL 列表文件路径 |
| `--input` | 本地数据文件路径 |
| `--source` | `wechat_mp` / `weibo` / `twitter` / `auto` |
| `--format` | `auto` / `json` / `csv` / `tweet_js` |
| `--provider` | `openai` / `claude`；不传时读取 `.env` 中的 `LLM_PROVIDER` |
| `--output` | 输出目录，默认 `./output` |
| `--skip-vector` | 跳过向量索引构建 |
| `--export` | `claude` / `chatgpt` |

## Provider 配置

默认逻辑：

- `LLM_PROVIDER=openai` 时读取 `OPENAI_API_KEY`
- `LLM_PROVIDER=claude` 时读取 `ANTHROPIC_API_KEY`
- 也可以在命令行显式传 `--provider openai` 或 `--provider claude`

常用环境变量见 [references/setup.md](references/setup.md) 和 [.env.example](.env.example)。

## Web 与 CLI 的边界

Web 面板入口：

```bash
python run_web.py
```

浏览器访问 `http://localhost:8501`。

当前边界如下：

- CLI 是主执行入口，真正运行流水线的是 `python -m src.pipeline`
- Web 负责浏览已有 Skill 包、手动录入内容、生成命令、查看导出结果
- Web 当前不会直接执行长时间流水线任务；页面会提示你回到终端执行

如果你的目标是“首次成功生成”，优先走 CLI。

## 输出结构

```text
output/digital-person-<name>/
├── SKILL.md
├── config.yaml
├── CHANGELOG.md
├── profile/
├── knowledge/
├── memory/
└── versions/
```

补充说明：

- `SKILL.md`：生成后的 persona skill 主指令
- `CLAUDE.md`：仅在 `--export claude` 时出现，用于 Claude Code 自定义指令
- `chatgpt_instructions.md`：仅在 `--export chatgpt` 时出现

## 如何部署

### 方案 A：部署为 Claude Code 项目/用户指令

只有在你显式运行过 `--export claude` 时，才会有 `CLAUDE.md` 可复制：

```bash
cp output/digital-person-某人/CLAUDE.md ./CLAUDE.md
```

或：

```bash
cp output/digital-person-某人/CLAUDE.md ~/.claude/CLAUDE.md
```

如果目录里没有 `CLAUDE.md`，先重新运行流水线并带上 `--export claude`。

### 方案 B：部署为 Claude Code persona skill

将整个生成结果目录复制到 Claude Code skills 目录，并保留真实目录名：

```bash
cp -R output/digital-person-某人 ~/.claude/skills/
```

部署后应按产物名使用，而不是统一写成 `/digital-person`。

### 方案 C：导出到 ChatGPT

```bash
python -m src.pipeline --name "某人" --urls urls.txt --skip-vector --export chatgpt
```

这会在产物目录里生成 `chatgpt_instructions.md`。

## 当前版本边界

| 状态 | 内容 |
|------|------|
| 已实现 | CLI 流水线、OpenAI/Claude provider 选择、微信 URL / 本地文件输入、`CLAUDE.md` / ChatGPT 导出、Streamlit 浏览面板 |
| 部分实现 | Web 手动录入后仍需你自行再跑 CLI；向量索引失败时建议改用 `--skip-vector` |
| 不应承诺为现成能力 | “直接对话即可自动跑完整流水线”、统一 `/digital-person` 调用名、Web 直接执行长任务 |

## 相关文档

- [references/setup.md](references/setup.md)
- [SKILL.md](SKILL.md)
- [DESIGN.md](DESIGN.md)

## License

MIT
