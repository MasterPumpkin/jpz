"""
JPZ - Analýza přijímacích řízení na střední školy.
Hlavní balíček a CLI entrypoint.
"""

import sys
import subprocess
from pathlib import Path

def main() -> None:
    """Spustí Streamlit aplikaci app.py."""
    app_path = Path(__file__).resolve().parent.parent.parent / "app.py"
    cmd = [sys.executable, "-m", "streamlit", "run", str(app_path)] + sys.argv[1:]
    try:
        subprocess.run(cmd)
    except KeyboardInterrupt:
        pass

if __name__ == "__main__":
    main()
