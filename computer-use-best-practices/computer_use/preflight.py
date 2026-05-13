"""
macOS permission preflight.

pyautogui needs Screen Recording (to capture pixels) and Accessibility (to
synthesize input events). Without them, screenshots come back black and
clicks/keystrokes are silently dropped, which looks like a model failure.
These checks call the same TCC query APIs the system uses, via ctypes, so
there is no extra dependency.
"""

import ctypes
import os
import subprocess
import sys

_FRAMEWORKS = "/System/Library/Frameworks"

_PANE_URL = {
    "Screen Recording": (
        "x-apple.systempreferences:com.apple.preference.security?Privacy_ScreenCapture"
    ),
    "Accessibility": (
        "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility"
    ),
}


# macOS sets this (case-sensitive) on every GUI-launched process; ruff's SIM112
# would have us uppercase it, which would just stop matching.
_CF_BUNDLE_ID_ENV = "__CFBundleIdentifier"


def _terminal_app() -> str:
    """Best-effort name of the GUI app this process is running under, so the
    user knows which row to enable in the permission list."""
    bundle = os.environ.get(_CF_BUNDLE_ID_ENV, "")
    known = {
        "com.apple.Terminal": "Terminal",
        "com.googlecode.iterm2": "iTerm",
        "com.microsoft.VSCode": "Visual Studio Code",
        "com.jetbrains.pycharm": "PyCharm",
        "dev.warp.Warp-Stable": "Warp",
        "com.github.wez.wezterm": "WezTerm",
        "io.alacritty": "Alacritty",
    }
    return known.get(bundle, bundle or "your terminal app")


def _probe(framework: str, symbol: str) -> bool:
    """Load a system framework and call a zero-arg bool-returning C function.
    Returns True on any load/call failure so an unknown environment doesn't block."""
    try:
        lib = ctypes.cdll.LoadLibrary(f"{_FRAMEWORKS}/{framework}.framework/{framework}")
        fn = getattr(lib, symbol)
        fn.restype = ctypes.c_bool
        return bool(fn())
    except Exception:
        return True


def screen_recording_granted() -> bool:
    return _probe("CoreGraphics", "CGPreflightScreenCaptureAccess")


def accessibility_granted() -> bool:
    return _probe("ApplicationServices", "AXIsProcessTrusted")


def _request_screen_recording() -> None:
    """Trigger the system "<app> would like to record this computer's screen"
    dialog, which also adds <app> to the Screen Recording list (unchecked) so
    the user only has to flip the toggle instead of hunting for the app.
    Unlike CGPreflightScreenCaptureAccess, this *registers* the request."""
    _probe("CoreGraphics", "CGRequestScreenCaptureAccess")


def _request_accessibility() -> None:
    """Same for Accessibility: AXIsProcessTrustedWithOptions with the prompt
    option pops the system dialog and adds <app> to the list."""
    try:
        appsvcs = ctypes.cdll.LoadLibrary(
            f"{_FRAMEWORKS}/ApplicationServices.framework/ApplicationServices"
        )
        cf = ctypes.cdll.LoadLibrary(f"{_FRAMEWORKS}/CoreFoundation.framework/CoreFoundation")

        prompt_key = ctypes.c_void_p.in_dll(appsvcs, "kAXTrustedCheckOptionPrompt")
        true_val = ctypes.c_void_p.in_dll(cf, "kCFBooleanTrue")

        cf.CFDictionaryCreate.restype = ctypes.c_void_p
        opts = cf.CFDictionaryCreate(
            None,
            (ctypes.c_void_p * 1)(prompt_key),
            (ctypes.c_void_p * 1)(true_val),
            1,
            None,
            None,
        )
        appsvcs.AXIsProcessTrustedWithOptions.restype = ctypes.c_bool
        appsvcs.AXIsProcessTrustedWithOptions(ctypes.c_void_p(opts))
        cf.CFRelease(ctypes.c_void_p(opts))
    except Exception:
        pass


def check_and_warn(*, require: bool = True, open_settings: bool = True) -> bool:
    sr = screen_recording_granted()
    ax = accessibility_granted()
    if sr and ax:
        return True

    app = _terminal_app()
    missing = []
    if not sr:
        missing.append(("Screen Recording", "needed to capture screenshots"))
    if not ax:
        missing.append(("Accessibility", "needed to move the mouse and type"))

    lines = [
        "[!] The `computer` tool needs macOS permissions that are not yet granted",
        f"    to {app}:",
        "",
    ]
    for pane, why in missing:
        lines.append(f"    * {pane:<17s} ({why})")
        lines.append(f"      System Settings > Privacy & Security > {pane}")
        lines.append(f"      then enable the toggle next to {app}")
        lines.append("")
    lines.append(f"    After granting, fully quit and reopen {app} (macOS only")
    lines.append("    re-reads these permissions at app launch). Then run again.")
    lines.append("")
    lines.append("    On macOS 15+ you may also see a separate 'bypass the system")
    lines.append("    private window picker' dialog on the first capture and about")
    lines.append("    once a month after; click Allow. That prompt is from macOS, not")
    lines.append("    from this demo, and is independent of the toggle above.")

    print("\n".join(lines), file=sys.stderr)

    if open_settings and sys.stderr.isatty():
        print(
            "\n    Requesting access (this should add the app to the list) and"
            "\n    opening System Settings to the relevant pane(s) now...",
            file=sys.stderr,
        )
        if not sr:
            _request_screen_recording()
        if not ax:
            _request_accessibility()
        for pane, _ in missing:
            subprocess.run(["open", _PANE_URL[pane]], check=False)

    if require:
        sys.exit(1)
    return False
