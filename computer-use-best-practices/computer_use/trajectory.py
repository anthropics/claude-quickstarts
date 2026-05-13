"""
Persist a run's full transcript and images to disk for later inspection.

Layout:
  runs/<iso-timestamp>/
    meta.json         : model, task, timing
    transcript.jsonl  : one JSON object per turn (role + content blocks)
    images/NNN.jpg    : every image we sent or received, referenced by path
                         from transcript.jsonl instead of inline base64
"""

import base64
import datetime as dt
import json
from typing import Any

from constants import RUNS_DIR


class Trajectory:
    def __init__(self, model: str, task: str, system_prompt: str | None = None) -> None:
        ts = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
        self.dir = RUNS_DIR / ts
        (self.dir / "images").mkdir(parents=True, exist_ok=True)
        self.scratch_dir = self.dir / "scratch"
        self.scratch_dir.mkdir(parents=True, exist_ok=True)
        self._transcript = self.dir / "transcript.jsonl"
        self._img_idx = 0
        (self.dir / "meta.json").write_text(
            json.dumps({"model": model, "task": task, "started": ts}, indent=2)
        )
        if system_prompt is not None:
            (self.dir / "system_prompt.txt").write_text(system_prompt)

    def save_image(self, b64: str) -> str:
        path = self.dir / "images" / f"{self._img_idx:03d}.jpg"
        path.write_bytes(base64.standard_b64decode(b64))
        self._img_idx += 1
        return str(path.relative_to(self.dir))

    def _rewrite_images(self, blocks: Any) -> Any:
        """Replace inline base64 image sources with on-disk file paths."""
        if not isinstance(blocks, list):
            return blocks
        out = []
        for b in blocks:
            if isinstance(b, dict) and b.get("type") == "image":
                src = b.get("source", {})
                if src.get("type") == "base64":
                    out.append({"type": "image", "path": self.save_image(src["data"])})
                    continue
            if isinstance(b, dict) and b.get("type") == "tool_result":
                b = {**b, "content": self._rewrite_images(b.get("content"))}
            out.append(b)
        return out

    def record(self, role: str, content: Any) -> None:
        entry = {"role": role, "content": self._rewrite_images(content)}
        with self._transcript.open("a") as f:
            f.write(json.dumps(entry) + "\n")
