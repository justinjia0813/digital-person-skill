# Real Provider Integration Tests

这些测试覆盖 `digital-person` 生成器的 CLI 端到端主路径，并使用仓库内固定真实样本文件作为输入，避免把网络采集稳定性和 provider 调用稳定性混在一起。

## 覆盖目标

- `python -m src.pipeline` 的 CLI 主路径
- `--provider openai|claude` 的真实 provider 调用
- provider 凭证缺失时的前置校验
- `--provider claude` 时的 embedding 默认推导语义
- `--skip-vector` 下的可降级执行策略
- `--export claude` 的导出产物检查

## 样本与执行策略

- 真实样本文件：`tests/fixtures/real_provider_articles.json`
- 输入模式：`--input ... --source wechat_mp`
- 降级策略：默认带 `--skip-vector`，只验证主生成链路，不把 embedding 配置耦合进首条真实链路测试
- 若关闭 `--skip-vector`，当前默认 embedding provider 为 `openai`；即使 chat provider 为 `claude`，也需要准备 OpenAI 兼容 embedding 凭证

## 默认行为

为了避免在本地或 CI 无意触发真实计费调用：

- `tests/test_pipeline_integration_real_provider.py::test_cli_fails_fast_when_provider_credentials_are_missing` 默认执行
- `tests/test_pipeline_integration_real_provider.py::test_cli_real_provider_pipeline_with_fixture_sample` 只有在 `RUN_REAL_PROVIDER_TESTS=1` 时才执行

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

## 预期结果

- 退出码为 `0`
- 生成 `output` 目录下的 `digital-person-<name>/`
- 至少包含 `SKILL.md`、`CLAUDE.md`、`profile/soul.md`、`knowledge/opinions.json`
- 无论是否启用向量索引，都应看到 `knowledge/vector_index/manifest.json`
- 启用向量索引时，`manifest.json` 与版本目录下的 `metadata.json` 应共享 `VectorIndexManifest.FIELD_NAMES` 全量字段，collection metadata 应共享 `VectorIndexManifest.COLLECTION_FIELD_NAMES` 核心字段，且会生成按 `人物名 + version` 命名的索引目录
- 使用 `--skip-vector` 时，`knowledge/vector_index/manifest.json` 仍应稳定落盘，并显式包含 `enabled=false` 与 `skip_reason=explicit_skip_vector`

## 建议执行顺序

1. 先跑现有回归测试，确认本地依赖完整
2. 再跑缺凭证前置校验测试，确认 CLI 失败信息正确
3. 最后在受控环境中开启 `RUN_REAL_PROVIDER_TESTS=1` 跑真实 provider 测试
