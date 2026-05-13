---
name: first-run
description: Guide a new user through their first computer-use agent run (env check, safe browser-only task, then open the trajectory viewer).
---

# First run

Walk the user through running this demo for the first time. Be conversational
and pause for confirmation between phases; the goal is that they understand
what each step does, not just that the commands succeed.

## 0. Orient

Briefly say what is about to happen: you will check their setup, run one safe
browser-only task that does **not** touch their mouse or keyboard, and then
open the trajectory viewer so they can see what the model saw.

## 1. Environment check

> **Never read the contents of `.env`.** Do not `cat`, `grep` (without `-q`),
> `Read`, or otherwise display it — the user's API key must never appear in
> this conversation or in your context. Only check for its *presence*.

- Confirm a virtual environment is active and dependencies are installed:
  `python -c "import computer_use, playwright; print('ok')"`. If that import
  fails, point them at the **Installation** section of `README.md` and stop.
- Confirm `.env` exists and the API key is set without ever printing it:
  `[ -f .env ] && grep -q '^ANTHROPIC_API_KEY=.' .env && echo 'API key: set' || echo 'API key: missing'`
  If missing, copy `.env.example` to `.env` and ask the user to open it in
  their own editor and paste their key into it (do **not** ask them to paste
  the key into chat, and do not edit `.env` for them). Wait until they confirm.
- Run the macOS permission preflight non-fatally:
  `python -c "from computer_use.preflight import check_and_warn; check_and_warn(require=False)"`
  and explain any warnings. These permissions are only needed for the desktop
  `computer` tool, which the first task does not use, so it is fine to
  continue without them for now.

## 2. Run a safe browser-only task

Explain that this task uses only the headless browser tool, so nothing on
their screen will move. Then run:

```bash
CU_ENABLE_COMPUTER_USE_TOOLS=false python -m computer_use \
  "Navigate to https://en.wikipedia.org/wiki/Special:Random three times, \
   take a screenshot each time, then summarize what you saw."
```

While it runs, narrate what the streamed output means (dim thinking text, the
cyan tool-call lines, the yellow tool-result lines, the `[usage]` line). When
it finishes, point out the `trajectory: runs/...` path that was printed.

## 3. Open the trajectory viewer

```bash
python -m streamlit run dev_ui/trajectory_viewer/app.py
```

Tell them to pick the newest run in the sidebar, expand the **System prompt**
section to see exactly what the model was told, and scroll through the turns
to see each screenshot inline.

## 4. Next steps

Offer two follow-ups and let them choose:

- **Try the desktop tool**: once Screen Recording and Accessibility are
  granted, run `python -m computer_use "open TextEdit and type hello world"`.
  Warn them again that this will move their real mouse and keyboard.
- **Explore the dev UIs**: the tool panel at
  `python -m uvicorn dev_ui.tool_panel.server:app --reload` lets them call
  each tool by hand without the model in the loop.

End by pointing at the **Configuration** and **Effective caching and context
pruning** sections of `README.md` for the deeper material.
