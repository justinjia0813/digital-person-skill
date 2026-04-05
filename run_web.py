"""Web 入口 — 运行 Streamlit 前端"""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def main():
    subprocess.run(
        [sys.executable, "-m", "streamlit", "run", str(ROOT / "src" / "web" / "app.py"), "--server.port", "8501"],
        cwd=str(ROOT),
    )


if __name__ == "__main__":
    main()
