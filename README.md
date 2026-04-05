# Digital Person Skill

> 把一个人的思维方式数字化，让 AI 能"像他一样思考"。

从公开/半公开内容中提取观点、决策框架和认知风格，生成可部署的 AI 数字分身 Skill 包。

## 功能

- **多数据源采集** — 微信公众号、微博、Twitter/X、手动粘贴
- **观点抽取与演化追踪** — 提取结构化观点，追踪立场随时间的变化
- **认知建模** — 通过 LLM 构建决策框架、思维风格画像
- **知识图谱** — 自动构建实体关系三元组
- **RAG 向量索引** — 基于 ChromaDB 的语义检索
- **多格式导出** — 支持 Claude Code 自定义指令、ChatGPT Custom Instructions
- **隐私分级** — 对观点和内容进行隐私等级标注与过滤
- **版本控制** — 语义化版本管理，自动生成 CHANGELOG
- **Streamlit 管理面板** — 可视化浏览、搜索和管理 Skill 包

## 快速开始

### 安装

```bash
git clone https://github.com/justinjia0813/digital-person-skill.git
cd digital-person-skill
pip install -r requirements.txt
```

### 配置

复制环境变量模板并填入 API Key：

```bash
cp .env.example .env
```

支持 OpenAI 和 Anthropic 作为 LLM 后端，在 `.env` 中配置：

```
OPENAI_API_KEY=sk-...
# 或
ANTHROPIC_API_KEY=sk-ant-...
```

### 运行流水线

准备一个 URL 列表文件（每行一个文章链接），然后运行：

```bash
python -m src.pipeline --name "某人" --urls urls.txt
```

常用参数：

| 参数 | 说明 |
|------|------|
| `--name` | 人物名称（必填） |
| `--urls` | URL 列表文件路径 |
| `--source` | 数据源类型：`wechat` / `weibo` / `twitter` / `auto` |
| `--provider` | LLM 后端：`openai` / `anthropic` |
| `--skip-vector` | 跳过向量索引构建 |
| `--export` | 导出格式：`claude` / `chatgpt` |

### Web 管理面板

```bash
python run_web.py
```

浏览器访问 `http://localhost:8501`，可以可视化浏览 Skill 包、搜索观点、查看演化时间线。

## 项目结构

```
src/
├── adapters/          # 数据源适配器（公众号、微博、Twitter）
├── processors/        # 内容处理（解析、观点抽取、风格分析、知识图谱…）
├── generators/        # Skill 包生成（SKILL.md、向量索引、导出）
│   └── exporters/     # Claude / ChatGPT 格式导出器
├── llm/               # LLM 抽象层（OpenAI / Anthropic）
├── models.py          # Pydantic 数据模型
├── config.py          # 配置管理
├── pipeline.py        # 流水线编排
└── web/               # Streamlit 前端
```

## 输出结构

流水线运行后，在 `output/digital-person-<name>/` 下生成：

```
├── SKILL.md              # Agent 指令文件
├── CLAUDE.md             # Claude Code 自定义指令
├── config.yaml           # 元数据与版本
├── CHANGELOG.md          # 变更日志
├── profile/
│   ├── personality.json  # 人格画像
│   ├── cognitive.json    # 认知模型
│   └── style.json        # 语言风格
├── knowledge/
│   ├── opinions.json     # 结构化观点库
│   ├── articles.json     # 文章归档
│   └── knowledge_graph.json  # 知识图谱
├── memory/
│   ├── evolution.json    # 观点演化追踪
│   └── decisions_log.json    # 决策框架
└── exports/              # 平台专用导出
```

## 技术栈

- **LLM** — OpenAI GPT / Anthropic Claude
- **向量数据库** — ChromaDB
- **知识图谱** — NetworkX
- **前端** — Streamlit
- **数据处理** — Pydantic, BeautifulSoup, html2text

## License

MIT
