"""
Streamlit trajectory viewer.

    uv run streamlit run dev_ui/trajectory_viewer/app.py
"""

import json
import shutil
import subprocess
from pathlib import Path

import streamlit as st

from constants import RUNS_DIR

_ASSETS = Path(__file__).parent.parent / "assets"


def _ensure_theme() -> None:
    """Seed .streamlit/config.toml from the shared theme on first run only,
    so a user's local edits survive."""
    cfg = Path.cwd() / ".streamlit" / "config.toml"
    if cfg.exists():
        return
    cfg.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(_ASSETS / "streamlit_theme.toml", cfg)


_ensure_theme()
st.set_page_config(page_title="Trajectory viewer", layout="wide")
st.markdown(f"<style>{(_ASSETS / 'anthropic.css').read_text()}</style>", unsafe_allow_html=True)

runs = sorted((p for p in RUNS_DIR.glob("*") if p.is_dir()), reverse=True)
if not runs:
    st.info(f"No runs found in {RUNS_DIR}")
    st.stop()

run = Path(st.sidebar.selectbox("Run", runs, format_func=lambda p: p.name))
meta = json.loads((run / "meta.json").read_text())
st.sidebar.json(meta)

st.sidebar.code(str(run.resolve()), language=None)
if st.sidebar.button("Open run folder in Finder"):
    subprocess.run(["open", str(run.resolve())], check=False)

st.title(meta.get("task", run.name))

sp_path = run / "system_prompt.txt"
with st.expander("System prompt", expanded=False):
    if sp_path.exists():
        st.text(sp_path.read_text())
    else:
        st.caption("Not recorded for this run (older trajectory).")

turns = [json.loads(line) for line in (run / "transcript.jsonl").read_text().splitlines()]
n_turns = len(turns)
show_upto = st.slider("Show through turn", min_value=1, max_value=max(n_turns, 1), value=n_turns)

for i, turn in enumerate(turns[:show_upto], start=1):
    role = turn["role"]
    with st.chat_message(role):
        st.caption(f"turn {i} / {n_turns}")
        content = turn["content"]
        if isinstance(content, str):
            st.markdown(content)
            continue
        for block in content:
            t = block.get("type")
            if t == "text":
                st.markdown(block["text"])
            elif t == "thinking":
                with st.expander("thinking"):
                    st.text(block.get("thinking", ""))
            elif t == "image":
                st.image(str(run / block["path"]))
            elif t in {"tool_use", "server_tool_use"}:
                st.code(
                    f"{block['name']}({json.dumps(block['input'], indent=2)})",
                    language="json",
                )
            elif t == "advisor_tool_result":
                c = block.get("content") or {}
                with st.expander(f"advisor ({c.get('type', '?')})", expanded=True):
                    st.text(c.get("text") or c.get("error_code") or "[redacted]")
            elif t == "tool_result":
                label = f"tool_result ({'error' if block.get('is_error') else 'ok'})"
                with st.expander(label, expanded=True):
                    for sub in block.get("content") or []:
                        if sub.get("type") == "text":
                            st.text(sub["text"])
                        elif sub.get("type") == "image":
                            st.image(str(run / sub["path"]))
