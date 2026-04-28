---
name: digital-person
description: |
  这是 digital-person 生成器仓库的使用说明，不是最终 persona skill 本体。
  它从公开内容中提取观点、决策框架和认知风格，生成
  `output/digital-person-<name>/` 目录，以及可选的 `CLAUDE.md`
  或 `chatgpt_instructions.md` 导出文件。

  当用户想要：(1) 为某人创建数字分身，(2) 把公众号/社交媒体内容
  转成 Claude Code 或 ChatGPT 指令，(3) 批量提取观点和决策框架时触发。
allowed-tools:
  - Bash
  - Read
  - Write
  - Edit
  - Glob
  - Grep
---

# Digital Person Skill — 数字分身生成器

## 先明确对象

本仓库有两个不同对象：

1. `digital-person`
   - 当前这个生成器仓库
   - 用来安装依赖、配置 provider、运行流水线
2. `digital-person-<name>`
   - 流水线生成的最终 persona skill
   - 输出目录固定在 `output/digital-person-<name>/`

不要把这两者混为一谈。

## 前置条件

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python -m src.pipeline --help
```

如果 `python -m src.pipeline --help` 不能正常打印帮助，先修复环境，不要继续。

Provider 和环境变量说明见 [references/setup.md](references/setup.md)。

## 四段链路

### 1. 安装

目标：把生成器 CLI 跑起来。

关键事实：

- 主执行入口是 `python -m src.pipeline`
- `.env` 中至少要有 `OPENAI_API_KEY` 或 `ANTHROPIC_API_KEY`

### 2. 运行

URL 模式：

```bash
python -m src.pipeline --name "人物名" --urls urls.txt --skip-vector
```

本地文件模式：

```bash
python -m src.pipeline --name "人物名" --input data.json --source weibo --skip-vector
```

完整导出示例：

```bash
python -m src.pipeline \
  --name "人物名" \
  --urls urls.txt \
  --skip-vector \
  --export claude
```

关键参数：

- `--provider openai|claude`：选择 LLM 后端；不传时读 `.env`
- `--skip-vector`：首次运行建议开启，减少环境变量与索引依赖
- `--export claude`：额外生成 `CLAUDE.md`
- `--export chatgpt`：额外生成 `chatgpt_instructions.md`

最低输入建议：

- 至少 5 篇高信息密度内容
- 主题越集中，生成的人格和判断框架越稳定

### 3. 导出

流水线总会生成 `output/digital-person-<name>/`。

只有满足下列条件时才会出现额外平台文件：

- 传 `--export claude`：生成 `CLAUDE.md`
- 传 `--export chatgpt`：生成 `chatgpt_instructions.md`

因此，`CLAUDE.md` 不是默认产物，只有真实导出时才应提及。

### 4. 部署

部署为 Claude Code 项目/用户指令：

```bash
cp output/digital-person-人物名/CLAUDE.md ./CLAUDE.md
```

或：

```bash
cp output/digital-person-人物名/CLAUDE.md ~/.claude/CLAUDE.md
```

部署为 persona skill：

```bash
cp -R output/digital-person-人物名 ~/.claude/skills/
```

调用和识别应以真实产物名为准，即 `digital-person-人物名`，而不是统一写成 `/digital-person`。

## Web / CLI 边界

Web 面板入口：

```bash
python run_web.py
```

边界如下：

- CLI 负责真正执行流水线
- Web 负责录入、浏览、查看和生成命令
- Web 当前不会直接执行长时间任务

“手动粘贴模式”的真实含义是：

- 在 Web 中把内容保存到本地数据文件
- 然后你仍需回到终端，使用 CLI 把这些数据喂给流水线

## 输出文件说明

| 文件 | 角色 |
|------|------|
| `SKILL.md` | 生成后的 persona skill 主指令 |
| `config.yaml` | 版本与数据源元信息 |
| `CHANGELOG.md` | 版本变更记录 |
| `profile/soul.md` | 人格、风格、价值观 |
| `profile/cognitive.md` | 认知模型、分析框架 |
| `profile/decisions.md` | 决策框架 |
| `knowledge/opinions.json` | 结构化观点库 |
| `knowledge/articles.json` | 原始内容索引 |
| `knowledge/knowledge_graph.json` | 知识图谱 |
| `memory/evolution.json` | 观点演化追踪 |
| `CLAUDE.md` | 仅在 `--export claude` 时出现 |
| `chatgpt_instructions.md` | 仅在 `--export chatgpt` 时出现 |

## 当前版本边界

- 已实现：CLI 生成、provider 切换、平台导出、Web 浏览面板
- 未实现为全自动体验：通过对话直接跑完整流水线、Web 直接执行长任务
- 文档中应始终把本仓库称为“生成器”，把 `output/digital-person-<name>/` 称为“生成产物”或“persona skill”
