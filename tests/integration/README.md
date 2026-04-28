# Real Provider Integration Tests

这些测试覆盖 `digital-person` 生成器的 CLI 端到端主路径，并使用仓库内固定真实样本文件作为输入，避免把网络采集稳定性和 provider 调用稳定性混在一起。

## 覆盖目标

- `python -m src.pipeline` 的 CLI 主路径
- `--provider openai|claude` 的真实 provider 调用
- URL 抓取的受控录制回放（本地固定 HTML，不依赖公网页面稳定性）
- provider 凭证缺失时的前置校验
- `--provider claude` 时的 embedding 默认推导语义
- `--skip-vector` 下的可降级执行策略
- 启用向量索引时的真实 chat provider + embedding provider 链路
- provider 限流 / 超时 / 依赖缺失三类失败的稳定错误语义
- `--export claude` 的导出产物检查

## 样本与执行策略

- 真实样本文件：`tests/fixtures/real_provider_articles.json`
- URL 回放夹具：`tests/fixtures/wechat_article_replay.html`
- 输入模式：`--input ... --source wechat_mp`
- URL 回放模式：`--urls urls.txt --source wechat_mp`，其中 URL 指向本地临时 HTTP 服务提供的固定 HTML
- 降级策略：默认带 `--skip-vector`，只验证主生成链路，不把 embedding 配置耦合进首条真实链路测试
- 若关闭 `--skip-vector`，当前默认 embedding provider 为 `openai`；即使 chat provider 为 `claude`，也需要准备 OpenAI 兼容 embedding 凭证

## 默认行为

为了避免在本地或 CI 无意触发真实计费调用：

- `tests/test_pipeline_integration_real_provider.py::test_cli_fails_fast_when_provider_credentials_are_missing` 默认执行
- `tests/test_pipeline_integration_real_provider.py::test_cli_real_provider_pipeline_with_fixture_sample` 只有在 `RUN_REAL_PROVIDER_TESTS=1` 时才执行
- `tests/test_pipeline_integration_real_provider.py::test_cli_real_provider_pipeline_with_replayed_url_input` 只有在 `RUN_REAL_PROVIDER_TESTS=1` 且本地可导入 `readability-lxml` 时才执行
- `tests/test_pipeline_integration_real_provider.py::test_cli_real_provider_pipeline_with_vector_enabled` 只有在 `RUN_REAL_PROVIDER_VECTOR_TESTS=1` 时才执行
- 缺凭证前置校验必须早于 `wechat_mp`/`readability` 导入链路；即使本地缺少这类采集依赖，`--skip-vector` 场景也应先看到 provider 凭证错误
- `readability-lxml` / `lxml_html_clean` 属于可选采集依赖；本目录中的缺凭证测试会同时防回归，确保 stderr 不再退化成这类导入异常
- `RUN_REAL_PROVIDER_VECTOR_TESTS=1` 表示允许真实 embedding 计费调用；建议仅在受控环境中开启

## OpenAI 真实链路

```bash
export RUN_REAL_PROVIDER_TESTS=1
export OPENAI_API_KEY=your_key
pytest tests/test_pipeline_integration_real_provider.py -k openai -m integration -vv
```

## Claude 真实链路

```bash
export RUN_REAL_PROVIDER_TESTS=1
export ANTHROPIC_API_KEY=your_key
pytest tests/test_pipeline_integration_real_provider.py -k claude -m integration -vv
```

## 受控 URL 回放链路

```bash
export RUN_REAL_PROVIDER_TESTS=1
export OPENAI_API_KEY=your_key   # 或 ANTHROPIC_API_KEY=your_key
pytest tests/test_pipeline_integration_real_provider.py -k replayed_url -m integration -vv
```

说明：

- 测试会在本地临时端口启动 HTTP 服务，回放 `tests/fixtures/wechat_article_replay.html`
- 这个用例验证 URL 文件输入、页面抓取、readability 解析和真实 provider 主链路能否一起通过
- 若本地未安装 `readability-lxml` / `lxml_html_clean`，该用例会跳过而不是误报公网抓取失败

## 真实向量索引链路

```bash
export RUN_REAL_PROVIDER_VECTOR_TESTS=1
export OPENAI_API_KEY=your_key
# Claude 聊天链路额外需要：
export ANTHROPIC_API_KEY=your_key
pytest tests/test_pipeline_integration_real_provider.py -k vector_enabled -m integration -vv
```

说明：

- `provider=openai` 时：chat 和 embedding 都走 OpenAI
- `provider=claude` 时：chat 走 Claude，embedding 默认仍走 OpenAI，因此需要同时准备 `ANTHROPIC_API_KEY` 与 `OPENAI_API_KEY`
- 该用例会校验 `knowledge/vector_index/manifest.json` 已落盘且 `enabled=true`

## 预期结果

- 退出码为 `0`
- 生成 `output` 目录下的 `digital-person-<name>/`
- 至少包含 `SKILL.md`、`CLAUDE.md`、`profile/soul.md`、`knowledge/opinions.json`
- 无论是否启用向量索引，都应看到 `knowledge/vector_index/manifest.json`
- 启用向量索引时，`manifest.json` 与版本目录下的 `metadata.json` 应共享 `VectorIndexManifest.FIELD_NAMES` 全量字段，collection metadata 应共享 `VectorIndexManifest.COLLECTION_FIELD_NAMES` 核心字段，且会生成按 `人物名 + version` 命名的索引目录
- 使用 `--skip-vector` 时，`knowledge/vector_index/manifest.json` 仍应稳定落盘，并显式包含 `enabled=false` 与 `skip_reason=explicit_skip_vector`

## 失败语义门控

- `provider_rate_limited`：provider 返回 429 / Too Many Requests / RateLimit 语义
- `provider_timeout`：provider 或网络调用超时
- `dependency_missing`：缺少 `chromadb`、`readability-lxml` 等运行依赖

这些语义由 `tests/test_pipeline_regressions.py` 中的回归测试固定，目的是在重构 CLI、provider 客户端或向量索引链路时，仍能稳定区分“真实调用失败类型”与“成功链路”。

## 建议执行顺序

1. 先跑现有回归测试，确认本地依赖完整
2. 再跑缺凭证前置校验测试，确认 CLI 失败信息正确
3. 受控环境中开启 `RUN_REAL_PROVIDER_TESTS=1` 跑真实主链路与 URL 回放测试
4. 仅在允许 embedding 真实计费时开启 `RUN_REAL_PROVIDER_VECTOR_TESTS=1` 跑向量链路测试
