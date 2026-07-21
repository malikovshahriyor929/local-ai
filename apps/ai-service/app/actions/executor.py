"""Executes validated ActionPlan steps on macOS.

Every step goes through `validate_plan` first, so the values reaching
`subprocess` here are already whitelist-checked. Nothing is ever passed to a
shell (`shell=True` is never used) and no step can run arbitrary commands.
"""
from __future__ import annotations

import platform
import subprocess
import time
from urllib.parse import quote_plus

from app.actions.plan import SHORTCUTS, ActionPlan, ActionStep, resolve_app
from app.errors import LocalAIError

SEARCH_URL = "https://www.google.com/search?q={query}"


def _run(command: list[str], timeout: float = 15) -> str:
    try:
        result = subprocess.run(command, check=True, capture_output=True, text=True, timeout=timeout)
    except FileNotFoundError as exc:
        raise LocalAIError("ACTION_UNSUPPORTED_PLATFORM", "Bu amal faqat macOS'da ishlaydi.", str(exc)) from exc
    except subprocess.TimeoutExpired as exc:
        raise LocalAIError("ACTION_TIMEOUT", "Amal juda uzoq davom etdi.", str(exc), True) from exc
    except subprocess.CalledProcessError as exc:
        raise LocalAIError("ACTION_FAILED", "Amalni bajarib bo'lmadi.", (exc.stderr or "").strip(), True) from exc
    return (result.stdout or "").strip()


def _osascript(script: str) -> str:
    """System Events scripting needs Accessibility permission for this process."""
    return _run(["osascript", "-e", script])


def _open_app(display_name: str) -> str:
    _run(["open", "-a", display_name])
    return f"{display_name} ochildi"


def _open_url(url: str) -> str:
    _run(["open", url])
    return "Havola brauzerda ochildi"


def _search(query: str) -> str:
    _run(["open", SEARCH_URL.format(query=quote_plus(query))])
    return f"“{query}” bo'yicha qidiruv ochildi"


def _media(command: str) -> str:
    action = {
        "play": "play",
        "pause": "pause",
        "toggle": "playpause",
        "next": "next track",
        "previous": "previous track",
    }[command.lower()]
    # Prefer whichever player is already running; fall back to Music.
    for app in ("Spotify", "Music"):
        running = _osascript(f'tell application "System Events" to (name of processes) contains "{app}"')
        if running == "true":
            _osascript(f'tell application "{app}" to {action}')
            return f"{app}: {command}"
    _run(["open", "-a", "Music"])
    time.sleep(1.5)
    _osascript(f'tell application "Music" to {action}')
    return f"Music: {command}"


def _shortcut(name: str) -> str:
    key, modifiers = SHORTCUTS[name]
    using = " using {" + ", ".join(f"{m} down" for m in modifiers) + "}" if modifiers else ""
    keystroke = f'key code 36{using}' if key == "return" else f'keystroke "{key}"{using}'
    _osascript(f'tell application "System Events" to {keystroke}')
    return f"{name} bajarildi"


def _type_text(text: str) -> str:
    escaped = text.replace("\\", "\\\\").replace('"', '\\"')
    _osascript(f'tell application "System Events" to keystroke "{escaped}"')
    return "Matn yozildi"


def execute_step(step: ActionStep) -> str:
    if platform.system() != "Darwin":
        raise LocalAIError("ACTION_UNSUPPORTED_PLATFORM", "Amallar faqat macOS'da bajariladi.")
    if step.kind == "openApp":
        display = resolve_app(step.value)
        if display is None:
            raise LocalAIError("ACTION_APP_NOT_ALLOWED", f"Bu dasturni ochishga ruxsat yo'q: {step.value}")
        return _open_app(display)
    if step.kind == "openUrl":
        return _open_url(step.value)
    if step.kind == "search":
        return _search(step.value)
    if step.kind == "mediaControl":
        return _media(step.value)
    if step.kind == "shortcut":
        return _shortcut(step.value)
    if step.kind == "typeText":
        return _type_text(step.value)
    # respond / unsupported carry no side effect.
    return ""


def execute_plan(plan: ActionPlan) -> list[dict[str, object]]:
    """Runs steps in order and stops at the first failure."""
    results: list[dict[str, object]] = []
    for step in plan.steps:
        if step.kind in {"respond", "unsupported"}:
            results.append({"kind": step.kind, "value": step.value, "ok": True, "message": step.value})
            continue
        try:
            message = execute_step(step)
            results.append({"kind": step.kind, "value": step.value, "ok": True, "message": message})
        except LocalAIError as exc:
            results.append({"kind": step.kind, "value": step.value, "ok": False, "message": exc.message, "details": exc.details})
            break
    return results
