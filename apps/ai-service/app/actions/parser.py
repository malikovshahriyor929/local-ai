"""Deterministic fast path for common Uzbek/English commands.

Matching here avoids an LLM round-trip for the commands people repeat all day
("safari och"), so the assistant answers in milliseconds instead of seconds.
Anything this does not recognise falls through to the LLM planner.
"""
from __future__ import annotations

import re

from app.actions.plan import ALLOWED_APPS, ActionPlan, ActionStep, resolve_app

_APOSTROPHES = ("ʻ", "ʼ", "‘", "’", "`")

# Uzbek marks the object with a suffix ("Safari-ni och"), so those endings are
# stripped before the app name is matched.
_SUFFIXES = ("ni", "ga", "da", "dan", "gacha")

_OPEN_VERBS_SUFFIX = ("och", "ochib ber", "oching", "ochgin", "ishga tushir")
_OPEN_VERBS_PREFIX = ("open", "launch", "start", "ochib ber", "och")

_SEARCH_PREFIX = ("search for", "search", "google", "qidir", "izla")
_SEARCH_SUFFIX = ("qidir", "qidirib ber", "izla", "toping", "top")

_MEDIA_PHRASES: dict[str, tuple[str, ...]] = {
    "pause": ("pause", "stop music", "musiqani to'xtat", "musiqani toxtat", "to'xtat musiqa", "pauza"),
    "play": ("play music", "resume", "musiqa qo'y", "musiqa qoy", "musiqani yoq", "qo'shiq qo'y", "qoshiq qoy"),
    "next": ("next track", "next song", "next", "keyingi qo'shiq", "keyingi qoshiq", "keyingisi"),
    "previous": ("previous track", "previous", "oldingi qo'shiq", "oldingi qoshiq", "oldingisi"),
}

_SHORTCUT_PHRASES: dict[str, tuple[str, ...]] = {
    "copy": ("copy", "nusxa ol", "kopiya qil"),
    "paste": ("paste", "qo'y", "joylashtir"),
    "save": ("save", "saqla"),
    "undo": ("undo", "orqaga qaytar", "bekor qil"),
    "newTab": ("new tab", "yangi tab", "yangi oyna"),
    "closeTab": ("close tab", "tabni yop", "oynani yop"),
}

_SHORTCUT_LABELS = {
    "copy": "Nusxa olaman",
    "paste": "Joylashtiraman",
    "save": "Saqlayman",
    "undo": "Oxirgi amalni bekor qilaman",
    "newTab": "Yangi tab ochaman",
    "closeTab": "Tabni yopaman",
}


def normalize(text: str) -> str:
    for apostrophe in _APOSTROPHES:
        text = text.replace(apostrophe, "'")
    text = text.lower().strip()
    text = re.sub(r"[.,!?;:]+$", "", text)
    return re.sub(r"\s+", " ", text)


def _strip_suffix(word: str) -> str:
    for suffix in _SUFFIXES:
        if len(word) > len(suffix) + 2 and word.endswith(suffix):
            return word[: -len(suffix)]
    return word


def _match_app(fragment: str) -> str | None:
    candidate = _strip_suffix(fragment.strip())
    resolved = resolve_app(candidate)
    if resolved:
        return resolved
    # Longest alias first so "google chrome" wins over "chrome".
    for alias in sorted(ALLOWED_APPS, key=len, reverse=True):
        if candidate == alias or candidate.startswith(f"{alias} ") or candidate.endswith(f" {alias}"):
            return ALLOWED_APPS[alias]
    return None


def _plan(summary: str, kind: str, value: str) -> ActionPlan:
    return ActionPlan(summary=summary, steps=[ActionStep(kind=kind, value=value)], requiresConfirmation=False)


def parse(transcript: str) -> ActionPlan | None:
    text = normalize(transcript)
    if not text:
        return None

    for command, phrases in _MEDIA_PHRASES.items():
        if any(text == phrase or text.startswith(f"{phrase} ") for phrase in phrases):
            labels = {"play": "Musiqani qo'yaman", "pause": "Musiqani to'xtataman", "next": "Keyingi qo'shiqqa o'taman", "previous": "Oldingi qo'shiqqa qaytaman"}
            return _plan(labels[command], "mediaControl", command)

    for name, phrases in _SHORTCUT_PHRASES.items():
        if text in phrases:
            return _plan(_SHORTCUT_LABELS[name], "shortcut", name)

    # "<verb> <query>" — search must be checked before app opening, otherwise
    # "google chrome" would be read as a search for "chrome".
    for prefix in _SEARCH_PREFIX:
        if text.startswith(f"{prefix} "):
            query = text[len(prefix) + 1 :].strip()
            if query and _match_app(query) is None:
                return _plan(f"“{query}” ni internetdan qidiraman", "search", query)

    for suffix in _SEARCH_SUFFIX:
        if text.endswith(f" {suffix}"):
            query = text[: -len(suffix) - 1].strip()
            if query and _match_app(query) is None:
                return _plan(f"“{query}” ni internetdan qidiraman", "search", query)

    # "open safari" / "safari och"
    for verb in _OPEN_VERBS_PREFIX:
        if text.startswith(f"{verb} "):
            app = _match_app(text[len(verb) + 1 :])
            if app:
                return _plan(f"{app} dasturini ochaman", "openApp", app)

    for verb in _OPEN_VERBS_SUFFIX:
        if text.endswith(f" {verb}"):
            app = _match_app(text[: -len(verb) - 1])
            if app:
                return _plan(f"{app} dasturini ochaman", "openApp", app)

    # A bare app name is treated as "open it".
    app = _match_app(text)
    if app:
        return _plan(f"{app} dasturini ochaman", "openApp", app)

    return None
