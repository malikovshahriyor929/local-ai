"""Turns free-form Uzbek speech into a validated ActionPlan.

The deterministic parser runs first. Only when it does not recognise the
request does the local GGUF model produce a plan, constrained to the ActionPlan
JSON schema so the output cannot drift into prose or invented action kinds.
"""
from __future__ import annotations

import json

from app.actions import parser
from app.actions.plan import ActionPlan, PlanRejected, validate_plan
from app.engines.llm import llm_engine
from app.errors import LocalAIError

PLANNER_PROMPT = """Siz macOS ovozli yordamchisining buyruq rejalashtiruvchisisiz. Foydalanuvchi so'rovini bitta JSON rejaga aylantiring.

Ruxsat etilgan kind qiymatlari:
- openApp: value dastur nomi (Safari, Google Chrome, Finder, Terminal, Spotify, Music, Notes, Mail, Messages, Calendar, Calculator, Photos, Preview, TextEdit, System Settings, Visual Studio Code, Xcode).
- openUrl: value to'liq https manzil.
- search: value internetdan qidiriladigan matn.
- mediaControl: value faqat play, pause, toggle, next yoki previous.
- shortcut: value faqat copy, paste, save, undo, newTab, closeTab yoki enter.
- typeText: value yoziladigan matn.
- respond: kompyuterni boshqarish shart bo'lmasa, value javob matni.
- unsupported: so'ralgan amal qo'llab-quvvatlanmasa, value qisqa sabab.

summary — o'zbek tilida, birinchi shaxsda, nima qilishingizni bildiruvchi bitta qisqa jumla. U ovoz bilan o'qiladi. Masalan: "Safari dasturini ochaman".

Ko'pi bilan 4 qadam. Fayl o'chirish, xarid, parol, terminal buyruqlari yoki ro'yxatdan tashqari amallarni hech qachon rejaga qo'shmang — bunday holatda unsupported qaytaring va requiresConfirmation ni true qiling. Aks holda requiresConfirmation false bo'lsin.

Faqat bitta JSON obyekt qaytaring, boshqa hech narsa emas."""

PLAN_SCHEMA = {
    "type": "object",
    "properties": {
        "summary": {"type": "string"},
        "steps": {
            "type": "array",
            "minItems": 1,
            "maxItems": 4,
            "items": {
                "type": "object",
                "properties": {
                    "kind": {
                        "type": "string",
                        "enum": ["openApp", "openUrl", "search", "mediaControl", "shortcut", "typeText", "respond", "unsupported"],
                    },
                    "value": {"type": "string"},
                },
                "required": ["kind", "value"],
            },
        },
        "requiresConfirmation": {"type": "boolean"},
    },
    "required": ["summary", "steps", "requiresConfirmation"],
}


def plan_with_llm(transcript: str) -> ActionPlan:
    model = llm_engine._require_model()
    try:
        completion = model.create_chat_completion(
            messages=[
                {"role": "system", "content": PLANNER_PROMPT},
                {"role": "user", "content": transcript},
            ],
            temperature=0.0,
            max_tokens=400,
            response_format={"type": "json_object", "schema": PLAN_SCHEMA},
        )
    except Exception as exc:
        raise LocalAIError("PLAN_FAILED", "Buyruq rejasi tuzilmadi.", str(exc), True) from exc
    content = completion["choices"][0]["message"]["content"] or ""
    try:
        plan = ActionPlan.model_validate(json.loads(content))
    except Exception as exc:
        raise LocalAIError("PLAN_INVALID", "Model to'g'ri reja qaytarmadi.", content[:400], True) from exc
    try:
        return validate_plan(plan)
    except PlanRejected as exc:
        raise LocalAIError("PLAN_REJECTED", f"Reja qabul qilinmadi: {exc}", content[:400]) from exc


def make_plan(transcript: str) -> tuple[ActionPlan, str]:
    """Returns the plan and which stage produced it."""
    fast = parser.parse(transcript)
    if fast is not None:
        return validate_plan(fast), "parser"
    return plan_with_llm(transcript), "llm"
