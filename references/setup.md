# Setup

## 环境要求

- Python 3.11+
- `pip`
- 一个可用的 LLM API Key

建议使用虚拟环境：

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## `.env` 配置

先复制样板：

```bash
cp .env.example .env
```

最小配置二选一：

### OpenAI

```dotenv
LLM_PROVIDER=openai
OPENAI_API_KEY=your_openai_key
```

### Claude

```dotenv
LLM_PROVIDER=claude
ANTHROPIC_API_KEY=your_anthropic_key
```

可选项：

- `OPENAI_BASE_URL` / `ANTHROPIC_BASE_URL`：自定义 API 网关
- `OPENAI_MODEL` / `ANTHROPIC_MODEL`：覆盖默认模型
- `OUTPUT_DIR`：修改默认输出目录

## 安装校验

依赖安装后，先运行：

```bash
python -m src.pipeline --help
```

成功标准：

- 命令能打印参数帮助并正常退出
- 没有 `ModuleNotFoundError`

如果失败：

- 重新确认当前 shell 已激活虚拟环境
- 重新执行 `pip install -r requirements.txt`
- 确认项目根目录下存在 `.env`

## Provider 选择规则

- 命令行传 `--provider` 时，以命令行为准
- 不传 `--provider` 时，读取 `.env` 中的 `LLM_PROVIDER`
- `LLM_PROVIDER=openai` 需要 `OPENAI_API_KEY`
- `LLM_PROVIDER=claude` 需要 `ANTHROPIC_API_KEY`
- 未传 `--skip-vector` 时，会额外解析 embedding provider；当前默认且唯一支持的 embedding provider 是 `openai`
- 因此 `--provider claude` 且需要向量索引时，仍需要 `OPENAI_API_KEY`
- 如需显式指定，可传 `--embedding-provider openai`
- embedding model 优先读取 `OPENAI_EMBEDDING_MODEL`，未设置时回退到 `EMBEDDING_MODEL`

## 首次运行建议

第一次生成建议带上：

```bash
--skip-vector
```

这样可以先验证主流水线是否通，再决定是否开启向量索引。
