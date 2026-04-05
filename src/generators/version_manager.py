"""版本管理器 — Skill 包版本控制和变更追踪"""

from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path

from src.models import VersionInfo


class VersionManager:
    """管理 Skill 包的版本历史"""

    def __init__(self, output_dir: str):
        self.output_dir = Path(output_dir)

    def detect_current_version(self, skill_dir: Path) -> VersionInfo | None:
        """检测现有的 Skill 包版本"""
        config_path = skill_dir / "config.yaml"
        if not config_path.exists():
            return None

        import yaml

        with open(config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)

        version = config.get("version", "1.0.0")
        created_at = config.get("created_at", "")

        # 读取统计数据
        opinions_path = skill_dir / "knowledge" / "opinions.json"
        articles_path = skill_dir / "knowledge" / "articles.json"

        opinion_count = 0
        article_count = 0
        if opinions_path.exists():
            with open(opinions_path, "r", encoding="utf-8") as f:
                opinion_count = len(json.load(f))
        if articles_path.exists():
            with open(articles_path, "r", encoding="utf-8") as f:
                article_count = len(json.load(f))

        return VersionInfo(
            version=version,
            created_at=created_at,
            article_count=article_count,
            opinion_count=opinion_count,
            sources=config.get("data_sources", []),
        )

    def create_versioned_copy(self, skill_dir: Path, version: str) -> Path | None:
        """将当前 Skill 包归档到 versions/ 目录"""
        versions_dir = skill_dir / "versions" / f"v{version}"
        if versions_dir.exists():
            return None

        # 只归档关键文件（不包含 vector_db）
        versions_dir.mkdir(parents=True, exist_ok=True)

        for subdir in ["profile", "knowledge"]:
            src = skill_dir / subdir
            dst = versions_dir / subdir
            if src.exists():
                shutil.copytree(src, dst, ignore=shutil.ignore_patterns("vector_db"))

        for f in ["SKILL.md", "config.yaml", "CHANGELOG.md"]:
            src = skill_dir / f
            if src.exists():
                shutil.copy2(src, versions_dir / f)

        return versions_dir

    def generate_changelog(
        self,
        skill_dir: Path,
        old_version: VersionInfo | None,
        new_version: VersionInfo,
    ) -> str:
        """生成 CHANGELOG.md"""
        entries = []

        if old_version is None:
            entries.append(
                f"## v{new_version.version} ({datetime.now().strftime('%Y-%m-%d')})\n"
                f"- 初始版本\n"
                f"- {new_version.article_count} 篇文章, {new_version.opinion_count} 个观点\n"
            )
        else:
            changes = []
            article_diff = new_version.article_count - old_version.article_count
            opinion_diff = new_version.opinion_count - old_version.opinion_count

            if article_diff != 0:
                changes.append(f"文章: {old_version.article_count} → {new_version.article_count} ({'+' if article_diff > 0 else ''}{article_diff})")
            if opinion_diff != 0:
                changes.append(f"观点: {old_version.opinion_count} → {new_version.opinion_count} ({'+' if opinion_diff > 0 else ''}{opinion_diff})")

            entries.append(
                f"## v{new_version.version} ({datetime.now().strftime('%Y-%m-%d')})\n"
                + "\n".join(f"- {c}" for c in changes)
            )

        # 追加到现有 CHANGELOG
        changelog_path = skill_dir / "CHANGELOG.md"
        existing = ""
        if changelog_path.exists():
            existing = changelog_path.read_text(encoding="utf-8")

        header = f"# {new_version.person_name if hasattr(new_version, 'person_name') else 'Digital Person'} 变更日志\n\n"
        new_content = header + "\n\n".join(entries)
        if existing and "# " in existing:
            # 保留旧条目
            old_entries = existing.split("\n\n", 1)[1] if "\n\n" in existing else ""
            new_content = header + "\n\n".join(entries) + "\n\n" + old_entries

        return new_content

    @staticmethod
    def increment_version(old_version: str | None, has_breaking: bool = False) -> str:
        """语义化版本递增"""
        if old_version is None:
            return "1.0.0"

        parts = old_version.split(".")
        if len(parts) != 3:
            return "1.0.0"

        major, minor, patch = int(parts[0]), int(parts[1]), int(parts[2])

        if has_breaking:
            return f"{major + 1}.0.0"
        else:
            return f"{major}.{minor}.{patch + 1}"
