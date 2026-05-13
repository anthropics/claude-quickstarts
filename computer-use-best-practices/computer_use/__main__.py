"""CLI entrypoint: `python -m computer_use "do something"`."""

import argparse
from pathlib import Path
from typing import get_args

from constants import (
    ADVISOR_PROMPT_ADDENDUM,
    SCRATCH_PROMPT_ADDENDUM,
    SYSTEM_PROMPT,
    Model,
    ThinkingEffort,
    cfg,
)

from . import render
from .loop import sampling_loop
from .preflight import check_and_warn
from .tools import ToolCollection
from .tools.base import Tool
from .tools.batch import BrowserBatchTool, ComputerBatchTool
from .tools.browser import BrowserTool
from .tools.computer import ComputerTool
from .tools.editor import EditorTool
from .tools.open_app import OpenApplicationTool
from .tools.shell import BashTool, PythonTool
from .trajectory import Trajectory


def build_tools(scratch_dir: Path | None = None) -> ToolCollection:
    if not (cfg.enable_computer_use_tools or cfg.enable_browser_use_tools):
        raise ValueError(
            "At least one of cfg.enable_computer_use_tools or "
            "cfg.enable_browser_use_tools must be True."
        )
    tools: list[Tool] = []
    if cfg.enable_computer_use_tools:
        computer = ComputerTool()
        tools += [computer, ComputerBatchTool(computer), OpenApplicationTool()]
    if cfg.enable_browser_use_tools:
        browser = BrowserTool()
        tools += [browser, BrowserBatchTool(browser)]
    tools += [BashTool(scratch_dir), PythonTool(scratch_dir)]
    if cfg.enable_editor_tool and scratch_dir is not None:
        tools.append(EditorTool(scratch_dir))
    return ToolCollection(*tools)


def build_system_prompt(scratch_dir: Path | None) -> str:
    prompt = SYSTEM_PROMPT
    if cfg.enable_editor_tool and scratch_dir is not None:
        prompt += SCRATCH_PROMPT_ADDENDUM.format(scratch_dir=scratch_dir)
    if cfg.enable_advisor_tool:
        prompt += ADVISOR_PROMPT_ADDENDUM
    return prompt


def main() -> None:
    parser = argparse.ArgumentParser(prog="computer_use")
    parser.add_argument("task", help="natural-language task for the agent")
    parser.add_argument(
        "--model",
        choices=[m.value for m in Model] + list(cfg.extra_models),
        default=Model.SONNET_4_6.value,
    )
    parser.add_argument("--max-iters", type=int, default=cfg.default_max_iters)
    parser.add_argument(
        "--thinking",
        choices=list(get_args(ThinkingEffort)),
        default=None,
        help="reasoning effort; overrides the per-model default in constants.py",
    )
    parser.add_argument(
        "--skip-preflight",
        action="store_true",
        help="skip the macOS Screen Recording / Accessibility permission check",
    )
    args = parser.parse_args()

    render.safety_banner()

    if not args.skip_preflight:
        check_and_warn(require=True)

    traj = Trajectory(model=args.model, task=args.task)
    system_prompt = build_system_prompt(traj.scratch_dir)
    (traj.dir / "system_prompt.txt").write_text(system_prompt)
    tools = build_tools(scratch_dir=traj.scratch_dir)
    print(f"trajectory: {traj.dir}")

    try:
        sampling_loop(
            model=args.model,
            task=args.task,
            tools=tools,
            trajectory=traj,
            system_prompt=system_prompt,
            thinking_effort=args.thinking,
            max_iters=args.max_iters,
        )
    finally:
        tools.close()


if __name__ == "__main__":
    main()
