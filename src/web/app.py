"""Digital Person Skill — Streamlit 管理面板"""

import json
import sys
from pathlib import Path

import streamlit as st

# 确保项目根目录在 path 中
ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main():
    st.set_page_config(
        page_title="Digital Person Skill",
        page_icon="🧠",
        layout="wide",
    )

    st.title("🧠 Digital Person Skill 管理面板")
    st.markdown("数字分身生成与管理工具")

    # 侧边栏导航
    page = st.sidebar.selectbox(
        "选择功能",
        ["📊 概览", "📝 数据采集", "⚙️ 流水线运行", "📦 Skill 包管理"],
    )

    if page == "📊 概览":
        _render_overview()
    elif page == "📝 数据采集":
        _render_collect()
    elif page == "⚙️ 流水线运行":
        _render_pipeline()
    elif page == "📦 Skill 包管理":
        _render_skill_manager()


def _render_overview():
    """概览页面"""
    st.header("📊 项目概览")

    output_dir = ROOT / "output"
    if not output_dir.exists():
        st.info("尚未生成任何 Skill 包。请先运行流水线。")
        return

    # 扫描 Skill 包
    skill_dirs = [d for d in output_dir.iterdir() if d.is_dir() and d.name.startswith("digital-person-")]

    if not skill_dirs:
        st.info("尚未生成任何 Skill 包。请先运行流水线。")
        return

    for skill_dir in skill_dirs:
        name = skill_dir.name.replace("digital-person-", "")
        with st.expander(f"**{name}**", expanded=True):
            col1, col2, col3, col4 = st.columns(4)

            # 统计数据
            opinions = _load_json(skill_dir / "knowledge" / "opinions.json")
            articles = _load_json(skill_dir / "knowledge" / "articles.json")
            kg = _load_json(skill_dir / "knowledge" / "knowledge_graph.json")
            config = _load_yaml(skill_dir / "config.yaml")

            col1.metric("文章数", len(articles) if articles else 0)
            col2.metric("观点数", len(opinions) if opinions else 0)
            col3.metric("实体数", len(kg.get("nodes", [])) if kg else 0)
            col4.metric("版本", config.get("version", "N/A") if config else "N/A")

            # 观点领域分布
            if opinions:
                domains = {}
                for op in opinions:
                    d = op.get("domain", "未分类")
                    domains[d] = domains.get(d, 0) + 1

                st.subheader("观点领域分布")
                chart_data = {"领域": list(domains.keys()), "数量": list(domains.values())}
                st.bar_chart(chart_data, x="领域", y="数量")

            # 观点演化
            evo = _load_json(skill_dir / "memory" / "evolution.json")
            if evo:
                st.subheader("观点演化")
                for item in evo:
                    trend_emoji = "🔄" if item.get("stance_changed") else "➡️"
                    st.write(f"{trend_emoji} **{item.get('topic', '')}** — {item.get('trend', 'stable')}")


def _render_collect():
    """数据采集页面"""
    st.header("📝 数据采集")

    source = st.selectbox("数据源", ["微信公众号", "微博", "Twitter/X"])

    if source == "微信公众号":
        st.subheader("通过 URL 采集")
        urls_text = st.text_area("输入微信文章 URL（每行一个）", height=150)
        if st.button("采集"):
            if urls_text.strip():
                urls = [u.strip() for u in urls_text.strip().split("\n") if u.strip()]
                st.info(f"准备采集 {len(urls)} 篇文章。请使用命令行运行：")
                st.code(f"python -m src.pipeline --name <名称> --urls urls.txt --skip-vector")

        st.subheader("手动粘贴")
        title = st.text_input("文章标题")
        content = st.text_area("文章内容", height=200)
        if st.button("保存文章"):
            if title and content:
                save_dir = ROOT / "data" / "manual"
                save_dir.mkdir(parents=True, exist_ok=True)
                import hashlib
                fid = hashlib.md5(title.encode()).hexdigest()[:8]
                (save_dir / f"{fid}.json").write_text(
                    json.dumps({"title": title, "content": content}, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
                st.success(f"已保存: {title}")


def _render_pipeline():
    """流水线运行页面"""
    st.header("⚙️ 运行流水线")

    name = st.text_input("人物名称", value="测试用户")
    col1, col2 = st.columns(2)

    with col1:
        url_file = st.text_input("URL 文件路径", value="test_urls.txt")
    with col2:
        skip_vector = st.checkbox("跳过向量索引", value=True)

    export_format = st.selectbox("导出格式", ["无", "claude", "chatgpt"])

    if st.button("🚀 运行流水线", type="primary"):
        cmd = f"python -m src.pipeline --name \"{name}\" --urls \"{url_file}\""
        if skip_vector:
            cmd += " --skip-vector"
        if export_format != "无":
            cmd += f" --export {export_format}"

        st.code(cmd, language="bash")
        st.info("请在终端中运行以上命令。Web 界面暂不支持直接执行长时间任务。")


def _render_skill_manager():
    """Skill 包管理页面"""
    st.header("📦 Skill 包管理")

    output_dir = ROOT / "output"
    if not output_dir.exists():
        st.info("尚未生成任何 Skill 包。")
        return

    skill_dirs = [d for d in output_dir.iterdir() if d.is_dir() and d.name.startswith("digital-person-")]
    if not skill_dirs:
        st.info("尚未生成任何 Skill 包。")
        return

    selected = st.selectbox(
        "选择 Skill 包",
        skill_dirs,
        format_func=lambda d: d.name.replace("digital-person-", ""),
    )

    if selected:
        tab1, tab2, tab3, tab4 = st.tabs(["📄 文件结构", "💡 观点库", "🧬 观点演化", "📤 导出"])

        with tab1:
            st.subheader("文件结构")
            _show_tree(selected)

        with tab2:
            opinions = _load_json(selected / "knowledge" / "opinions.json")
            if opinions:
                # 搜索
                search = st.text_input("搜索观点")
                filtered = opinions
                if search:
                    filtered = [o for o in opinions if search.lower() in o.get("claim", "").lower() or search.lower() in o.get("domain", "").lower()]

                st.write(f"共 {len(filtered)} 个观点" + (f"（筛选自 {len(opinions)}）" if search else ""))
                for op in filtered[:50]:
                    confidence = op.get("confidence", "medium")
                    emoji = {"high": "🟢", "medium": "🟡", "low": "🔴"}.get(confidence, "⚪")
                    st.write(f"{emoji} **[{op.get('domain', '')}]** {op.get('claim', '')}")
                    if op.get("reasoning"):
                        with st.expander("理由"):
                            for r in op["reasoning"]:
                                st.write(f"- {r}")
            else:
                st.info("暂无观点数据")

        with tab3:
            evo = _load_json(selected / "memory" / "evolution.json")
            if evo:
                for item in evo:
                    changed = item.get("stance_changed", False)
                    icon = "🔄" if changed else "➡️"
                    st.subheader(f"{icon} {item.get('topic', '')}")

                    trend = item.get("trend", "stable")
                    st.write(f"趋势：**{trend}**")

                    timeline = item.get("timeline", [])
                    if timeline:
                        for snap in timeline:
                            time_label = snap.get("time", "未知时间")
                            stance = snap.get("stance", "")
                            st.write(f"- `{time_label}` — {stance}")

                    triggers = item.get("triggers", [])
                    if triggers:
                        st.write("**触发因素**：")
                        for t in triggers:
                            st.write(f"- {t}")

                    st.divider()
            else:
                st.info("暂无观点演化数据")

        with tab4:
            st.subheader("导出为自定义指令")
            fmt = st.selectbox("选择平台", ["claude", "chatgpt"])

            if st.button("生成导出文件"):
                try:
                    from src.generators.exporters import get_exporter
                    name = selected.name.replace("digital-person-", "")
                    exporter = get_exporter(fmt)
                    path = exporter.export(selected, name)
                    st.success(f"已导出到: {path.name}")
                    content = path.read_text(encoding="utf-8")
                    st.text_area("导出内容", value=content, height=400)
                except Exception as e:
                    st.error(f"导出失败: {e}")


def _load_json(path: Path) -> dict | list | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _load_yaml(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        import yaml
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    except Exception:
        return None


def _show_tree(directory: Path, prefix: str = ""):
    """显示目录树"""
    items = sorted(directory.iterdir(), key=lambda x: (not x.is_dir(), x.name))
    for i, item in enumerate(items):
        is_last = i == len(items) - 1
        connector = "└── " if is_last else "├── "
        icon = "📁 " if item.is_dir() else "📄 "
        st.text(f"{prefix}{connector}{icon}{item.name}")
        if item.is_dir() and not item.name.startswith("."):
            extension = "    " if is_last else "│   "
            _show_tree(item, prefix + extension)


if __name__ == "__main__":
    main()
