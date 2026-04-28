from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_PATH = PROJECT_ROOT / "tests" / "fixtures" / "real_provider_articles.json"


def _base_env() -> dict[str, str]:
    env = os.environ.copy()
    python_path = str(PROJECT_ROOT)
    existing = env.get("PYTHONPATH")
    env["PYTHONPATH"] = python_path if not existing else f"{python_path}:{existing}"
    return env


def _real_provider_enabled() -> bool:
    return os.environ.get("RUN_REAL_PROVIDER_TESTS") == "1"


def _provider_env(provider: str) -> dict[str, str]:
    env = _base_env()
    env["LLM_PROVIDER"] = provider
    if provider == "openai":
        env.setdefault("OPENAI_MODEL", "gpt-4o")
    elif provider == "claude":
        env.setdefault("ANTHROPIC_MODEL", "claude-sonnet-4-20250514")
    return env


def _provider_ready(provider: str) -> bool:
    if provider == "openai":
        return bool(os.environ.get("OPENAI_API_KEY"))
    if provider == "claude":
        return bool(os.environ.get("ANTHROPIC_API_KEY"))
    return False


@pytest.mark.parametrize(
    ("provider", "missing_env", "expected_hint"),
    [
        ("openai", "OPENAI_API_KEY", "OPENAI_API_KEY"),
        ("claude", "ANTHROPIC_API_KEY", "ANTHROPIC_API_KEY"),
    ],
)
def test_cli_fails_fast_when_provider_credentials_are_missing(
    tmp_path: Path, provider: str, missing_env: str, expected_hint: str
) -> None:
    env = _provider_env(provider)
    env.pop(missing_env, None)

    if provider == "openai":
        env["ANTHROPIC_API_KEY"] = env.get("ANTHROPIC_API_KEY", "placeholder-anthropic-key")
    else:
        env["OPENAI_API_KEY"] = env.get("OPENAI_API_KEY", "placeholder-openai-key")

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "src.pipeline",
            "--name",
            "PreflightTester",
            "--input",
            str(FIXTURE_PATH),
            "--source",
            "wechat_mp",
            "--provider",
            provider,
            "--skip-vector",
            "--output",
            str(tmp_path),
        ],
        cwd=PROJECT_ROOT,
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert expected_hint in result.stderr


@pytest.mark.integration
@pytest.mark.parametrize("provider", ["openai", "claude"])
def test_cli_real_provider_pipeline_with_fixture_sample(tmp_path: Path, provider: str) -> None:
    if not _real_provider_enabled():
        pytest.skip("Set RUN_REAL_PROVIDER_TESTS=1 to enable real provider integration tests.")
    if not _provider_ready(provider):
        pytest.skip(f"{provider} credentials are not configured in the environment.")
    if shutil.which(sys.executable) is None:
        pytest.skip("Python executable is not available.")

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "src.pipeline",
            "--name",
            f"RealProvider{provider.title()}",
            "--input",
            str(FIXTURE_PATH),
            "--source",
            "wechat_mp",
            "--provider",
            provider,
            "--skip-vector",
            "--export",
            "claude",
            "--output",
            str(tmp_path),
        ],
        cwd=PROJECT_ROOT,
        env=_provider_env(provider),
        capture_output=True,
        text=True,
        timeout=600,
    )

    assert result.returncode == 0, result.stderr or result.stdout

    skill_dir = tmp_path / f"digital-person-RealProvider{provider.title()}"
    assert skill_dir.exists()
    assert (skill_dir / "SKILL.md").exists()
    assert (skill_dir / "CLAUDE.md").exists()
    assert (skill_dir / "profile" / "soul.md").exists()
    assert (skill_dir / "knowledge" / "opinions.json").exists()
    assert "完成！Skill 包已生成到" in result.stdout
