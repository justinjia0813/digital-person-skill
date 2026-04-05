# Digital Person Skill

> Claude Code Skill — 把一个人的思维方式数字化，让 AI 能"像他一样思考"。

从公开内容（公众号、微博、Twitter/X）中提取观点、决策框架和认知风格，生成可部署的 AI 数字分身。

## 作为 Claude Code Skill 使用

### 安装

```bash
# 克隆到 Claude Code skills 目录
git clone https://github.com/justinjia0813/digital-person-skill.git ~/.claude/skills/digital-person

# 安装依赖
cd ~/.claude/skills/digital-person
pip install -r requirements.txt

# 配置 LLM API Key
cp .env.example .env
# 编辑 .env，填入 OPENAI_API_KEY 或 ANTHROPIC_API_KEY
```

### 调用

在 Claude Code 中直接对话即可触发 skill，例如：

- "帮我基于这些公众号文章创建一个数字分身"
- "把这个人的微博内容转化为 Claude Code 自定义指令"
- "我要给某人生成一个 AI persona skill"

skill 会引导你完成内容采集、流水线运行和结果部署。

### 部署生成的分身

流水线输出的 `CLAUDE.md` 可直接作为 Claude Code 项目自定义指令使用：

```bash
# 方式一：复制到项目级 CLAUDE.md
cp output/digital-person-某人/CLAUDE.md ./CLAUDE.md

# 方式二：复制到用户级 CLAUDE.md（全局生效）
cp output/digital-person-某人/CLAUDE.md ~/.claude/CLAUDE.md
```

## 命令行使用

也可以直接通过命令行运行流水线：

```bash
# 准备 URL 列表文件（每行一个链接）
python -m src.pipeline --name "某人" --urls urls.txt --export claude

# 从微博导出文件
python -m src.pipeline --name "某人" --input weibo.json --source weibo --export claude
```

| 参数 | 说明 |
|------|------|
| `--name` | 人物名称（必填） |
| `--urls` | URL 列表文件路径 |
| `--input` | 本地数据文件 |
| `--source` | `wechat_mp` / `weibo` / `twitter` / `auto` |
| `--provider` | `openai` / `claude` |
| `--export` | `claude` / `chatgpt` |
| `--skip-vector` | 跳过向量索引构建 |

## Web 管理面板

```bash
python run_web.py
```

浏览器访问 `http://localhost:8501`，可视化浏览 Skill 包、搜索观点、查看演化时间线。

## 输出结构

```
output/digital-person-<name>/
├── SKILL.md              # Skill 主指令
├── CLAUDE.md             # Claude Code 自定义指令
├── config.yaml           # 元数据与版本
├── CHANGELOG.md          # 变更日志
├── profile/
│   ├── soul.md           # 人格、说话风格、价值观
│   ├── cognitive.md      # 认知模型、分析框架
│   └── decisions.md      # 决策框架、判断模式
├── knowledge/
│   ├── opinions.json     # 结构化观点库
│   ├── articles.json     # 文章归档
│   └── knowledge_graph.json  # 知识图谱
├── memory/
│   ├── evolution.json    # 观点演化追踪
│   └── decisions_log.json    # 决策日志
└── versions/             # 历史版本归档
```

## 技术栈

- **LLM** — OpenAI GPT / Anthropic Claude
- **向量数据库** — ChromaDB
- **知识图谱** — NetworkX
- **前端** — Streamlit
- **数据处理** — Pydantic, BeautifulSoup, html2text

## License

MIT
