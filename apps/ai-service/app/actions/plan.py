"""The action contract between the planner and the executor.

The model never runs code. It only proposes an `ActionPlan`, which is validated
here and executed by `executor.py` through a fixed whitelist of operations.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

ActionKind = Literal[
    "openApp",
    "openUrl",
    "search",
    "mediaControl",
    "shortcut",
    "typeText",
    "respond",
    "unsupported",
]

# Only these apps can be launched by name. Anything else is rejected rather
# than passed to the shell.
ALLOWED_APPS: dict[str, str] = {
    "safari": "Safari",
    "chrome": "Google Chrome",
    "google chrome": "Google Chrome",
    "finder": "Finder",
    "terminal": "Terminal",
    "spotify": "Spotify",
    "music": "Music",
    "musiqa": "Music",
    "notes": "Notes",
    "eslatma": "Notes",
    "mail": "Mail",
    "pochta": "Mail",
    "messages": "Messages",
    "xabarlar": "Messages",
    "calendar": "Calendar",
    "kalendar": "Calendar",
    "calculator": "Calculator",
    "kalkulyator": "Calculator",
    "photos": "Photos",
    "rasmlar": "Photos",
    "preview": "Preview",
    "textedit": "TextEdit",
    "system settings": "System Settings",
    "sozlamalar": "System Settings",
    "visual studio code": "Visual Studio Code",
    "vs code": "Visual Studio Code",
    "vscode": "Visual Studio Code",
    "xcode": "Xcode",
}

MEDIA_COMMANDS = {"play", "pause", "toggle", "next", "previous"}

# Deliberately excludes anything that deletes, sends, purchases, or changes
# system state.
SHORTCUTS: dict[str, tuple[str, list[str]]] = {
    "copy": ("c", ["command"]),
    "paste": ("v", ["command"]),
    "save": ("s", ["command"]),
    "undo": ("z", ["command"]),
    "newTab": ("t", ["command"]),
    "closeTab": ("w", ["command"]),
    "enter": ("return", []),
}


class ActionStep(BaseModel):
    kind: ActionKind
    value: str = ""


class ActionPlan(BaseModel):
    """`summary` is spoken aloud before the steps run."""

    summary: str = Field(min_length=1, max_length=240)
    steps: list[ActionStep] = Field(min_length=1, max_length=4)
    requiresConfirmation: bool = False

    def is_conversational(self) -> bool:
        return all(step.kind in {"respond", "unsupported"} for step in self.steps)


class PlanRejected(Exception):
    """A plan that failed validation; it is never executed."""


def validate_plan(plan: ActionPlan) -> ActionPlan:
    steps: list[ActionStep] = []
    for step in plan.steps:
        value = step.value.strip()
        if len(value) > 500:
            raise PlanRejected("qadam qiymati juda uzun")
        if step.kind == "openApp":
            if resolve_app(value) is None:
                raise PlanRejected(f"ruxsat etilmagan dastur: {value}")
        elif step.kind == "openUrl":
            if not value.startswith(("http://", "https://")):
                raise PlanRejected("faqat http/https manzillar ochiladi")
        elif step.kind == "mediaControl":
            if value.lower() not in MEDIA_COMMANDS:
                raise PlanRejected(f"noma'lum media buyrug'i: {value}")
        elif step.kind == "shortcut":
            if value not in SHORTCUTS:
                raise PlanRejected(f"ruxsat etilmagan tugmalar birikmasi: {value}")
        elif step.kind in {"search", "typeText"}:
            if not value:
                raise PlanRejected(f"{step.kind} uchun matn bo'sh")
        steps.append(ActionStep(kind=step.kind, value=value))
    return ActionPlan(summary=plan.summary.strip(), steps=steps, requiresConfirmation=plan.requiresConfirmation)


def resolve_app(name: str) -> str | None:
    key = name.strip().lower()
    if key in ALLOWED_APPS:
        return ALLOWED_APPS[key]
    # Accept the canonical display name too ("Google Chrome").
    for display in ALLOWED_APPS.values():
        if display.lower() == key:
            return display
    return None
