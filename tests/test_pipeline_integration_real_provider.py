from __future__ import annotations

import os
import shutil
import socketserver
import subprocess
import sys
import threading
from pathlib import Path
from http.server import SimpleHTTPRequestHandler

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_PATH = PROJECT_ROOT / "tests" / "fixtures" / "real_provider_articles.json"
URL_REPLAY_FIXTURE_PATH = PROJECT_ROOT / "tests" / "fixtures" / "wechat_article_replay.html"


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


def _vector_provider_ready(provider: str) -> bool:
    if provider == "openai":
        return bool(os.environ.get("OPENAI_API_KEY"))
    if provider == "claude":
        return bool(os.environ.get("ANTHROPIC_API_KEY")) and bool(os.environ.get("OPENAI_API_KEY"))
    return False


def _real_provider_vector_enabled() -> bool:
    return os.environ.get("RUN_REAL_PROVIDER_VECTOR_TESTS") == "1"


def _readability_ready() -> bool:
    try:
        import readability  # noqa: F401
    except ModuleNotFoundError:
        return False
    return True


class _FixtureRequestHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, directory: str, **kwargs):
        super().__init__(*args, directory=directory, **kwargs)

    def log_message(self, format: str, *args) -> None:  # noqa: A003
        return


class _ThreadingTCPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    allow_reuse_address = True


class _FixtureHttpServer:
    def __init__(self, directory: Path):
        self.directory = directory
        self.server: _ThreadingTCPServer | None = None
        self.thread: threading.Thread | None = None

    def __enter__(self) -> str:
        handler = lambda *args, **kwargs: _FixtureRequestHandler(  # noqa: E731
            *args, directory=str(self.directory), **kwargs
        )
        self.server = _ThreadingTCPServer(("127.0.0.1", 0), handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        host, port = self.server.server_address
        return f"http://{host}:{port}"

    def __exit__(self, exc_type, exc, tb) -> None:
        assert self.server is not None
        self.server.shutdown()
        self.server.server_close()
        if self.thread is not None:
            self.thread.join(timeout=5)


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
    assert "ModuleNotFoundError" not in result.stderr
    assert "lxml_html_clean" not in result.stderr


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


@pytest.mark.integration
@pytest.mark.parametrize("provider", ["openai", "claude"])
def test_cli_real_provider_pipeline_with_replayed_url_input(tmp_path: Path, provider: str) -> None:
    if not _real_provider_enabled():
        pytest.skip("Set RUN_REAL_PROVIDER_TESTS=1 to enable real provider integration tests.")
    if not _provider_ready(provider):
        pytest.skip(f"{provider} credentials are not configured in the environment.")
    if not _readability_ready():
        pytest.skip("readability-lxml is required for replayed URL fetch tests.")

    url_file = tmp_path / "urls.txt"
    with _FixtureHttpServer(URL_REPLAY_FIXTURE_PATH.parent) as base_url:
        url_file.write_text(f"{base_url}/{URL_REPLAY_FIXTURE_PATH.name}\n", encoding="utf-8")
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "src.pipeline",
                "--name",
                f"ReplayUrl{provider.title()}",
                "--urls",
                str(url_file),
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

    skill_dir = tmp_path / f"digital-person-ReplayUrl{provider.title()}"
    articles = (skill_dir / "knowledge" / "articles.json").read_text(encoding="utf-8")
    assert skill_dir.exists()
    assert "受控回放样本：数字分身文章" in result.stdout
    assert "受控回放作者" in articles


@pytest.mark.integration
@pytest.mark.parametrize("provider", ["openai", "claude"])
def test_cli_real_provider_pipeline_with_vector_enabled(tmp_path: Path, provider: str) -> None:
    if not _real_provider_vector_enabled():
        pytest.skip("Set RUN_REAL_PROVIDER_VECTOR_TESTS=1 to enable real provider vector integration tests.")
    if not _vector_provider_ready(provider):
        pytest.skip(f"{provider} vector credentials are not fully configured in the environment.")
    if shutil.which(sys.executable) is None:
        pytest.skip("Python executable is not available.")

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "src.pipeline",
            "--name",
            f"RealVector{provider.title()}",
            "--input",
            str(FIXTURE_PATH),
            "--source",
            "wechat_mp",
            "--provider",
            provider,
            "--export",
            "claude",
            "--output",
            str(tmp_path),
        ],
        cwd=PROJECT_ROOT,
        env=_provider_env(provider),
        capture_output=True,
        text=True,
        timeout=900,
    )

    assert result.returncode == 0, result.stderr or result.stdout

    skill_dir = tmp_path / f"digital-person-RealVector{provider.title()}"
    manifest_path = skill_dir / "knowledge" / "vector_index" / "manifest.json"
    assert skill_dir.exists()
    assert manifest_path.exists()
    assert '"enabled": true' in manifest_path.read_text(encoding="utf-8").lower()
