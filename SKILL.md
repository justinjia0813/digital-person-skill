---
name: digital-person
description: |
  从公开内容（公众号、微博、Twitter/X）中提取观点、决策框架和认知风格，
  生成 AI 数字分身 Skill 包和 Claude Code 自定义指令（CLAUDE.md）。

  当用户想要：(1) 为某人创建数字分身，(2) 把公众号/社交媒体内容转化为
  Claude Code 自定义指令，(3) 批量提取文章中的观点和决策框架，
  (4) 生成可部署的 AI persona skill 时触发此 skill。
allowed-tools:
  - Bash
  - Read
  - Write
  - Edit
  - Glob
  - Grep
---

# Digital Person Skill — 数字分身生成器

将一个人的公开内容转化为结构化 Skill 包，让 Claude 能"像他一样思考"。

## 前置条件

项目已安装依赖且配置了 LLM API Key。运行以下命令确认：

```bash
pip install -r requirements.txt
test -f .env && echo "OK" || echo "需要创建 .env"
```

如未配置，参考 `references/setup.md` 完成。

## 工作流程

### 1. 采集内容

用户提供数据源后，运行采集脚本：

**URL 模式（微信公众号文章）：**

```bash
python -m src.pipeline --name "人物名" --urls urls.txt --skip-vector
```

**本地文件模式（微博/Twitter 导出）：**

```bash
python -m src.pipeline --name "人物名" --input data.json --source weibo --skip-vector
```

**手动粘贴模式：** 通过 Web 面板 `python run_web.py` 在浏览器中粘贴。

### 2. 运行完整流水线

```bash
python -m src.pipeline \
  --name "人物名" \
  --urls urls.txt \
  --export claude
```

关键参数：
- `--provider openai|claude` — 选择 LLM 后端
- `--skip-vector` — 跳过向量索引（节省时间）
- `--export claude` — 额外生成 CLAUDE.md 自定义指令
- `--export chatgpt` — 导出 ChatGPT 格式

### 3. 部署生成的 Skill

流水线在 `output/digital-person-<name>/` 下生成完整 Skill 包。

**部署到 Claude Code：**
将生成的 `CLAUDE.md` 内容复制到项目的 `CLAUDE.md` 或 `~/.claude/CLAUDE.md` 中。

**部署为 Claude Code Skill：**
将整个输出目录复制到 `~/.claude/skills/<skill-name>/`，即可通过 `/digital-person` 调用。

## 输出文件说明

| 文件 | 用途 |
|------|------|
| `SKILL.md` | Agent 指令（观点、风格、行为规则） |
| `CLAUDE.md` | Claude Code 自定义指令（可直接粘贴） |
| `profile/soul.md` | 人格、说话风格、价值观 |
| `profile/cognitive.md` | 认知模型（思维风格、分析框架） |
| `profile/decisions.md` | 决策框架和判断模式 |
| `knowledge/opinions.json` | 结构化观点库 |
| `knowledge/knowledge_graph.json` | 实体关系知识图谱 |
| `memory/evolution.json` | 观点演化追踪 |
| `CHANGELOG.md` | 版本变更日志 |

## 增量更新

再次运行流水线时，系统自动：
- 检测已有版本，递增版本号
- 归档旧版本到 `versions/` 目录
- 追加 CHANGELOG 条目
- 追踪观点演化（立场是否变化）

## 数据源适配

| 平台 | 采集方式 | `--source` |
|------|---------|------------|
| 微信公众号 | URL 爬取或手动粘贴 | `wechat_mp`（默认） |
| 微博 | CSV/JSON 导出文件 | `weibo` |
| Twitter/X | tweet.js / CSV / JSON | `twitter` |
