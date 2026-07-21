import pytest

from app.actions.parser import parse
from app.actions.plan import ActionPlan, ActionStep, PlanRejected, resolve_app, validate_plan


@pytest.mark.parametrize(
    ("text", "kind", "value"),
    [
        ("open safari", "openApp", "Safari"),
        ("Safari och", "openApp", "Safari"),
        ("safarini och", "openApp", "Safari"),
        ("chrome och", "openApp", "Google Chrome"),
        ("open google chrome", "openApp", "Google Chrome"),
        ("terminalni och", "openApp", "Terminal"),
        ("spotify", "openApp", "Spotify"),
        ("musiqa qo'y", "mediaControl", "play"),
        ("keyingi qo'shiq", "mediaControl", "next"),
        ("yangi tab", "shortcut", "newTab"),
        ("nusxa ol", "shortcut", "copy"),
        ("search for tashkent weather", "search", "tashkent weather"),
        ("toshkent ob-havosi qidir", "search", "toshkent ob-havosi"),
    ],
)
def test_fast_parser_recognises_uzbek_and_english_commands(text, kind, value) -> None:
    plan = parse(text)
    assert plan is not None, f"{text!r} tanilmadi"
    assert plan.steps[0].kind == kind
    assert plan.steps[0].value == value
    assert plan.summary.strip()


@pytest.mark.parametrize(
    "text",
    ["bugun kayfiyating qanday", "o'zbekiston poytaxti qayer", "menga she'r yozib ber"],
)
def test_questions_are_not_treated_as_commands(text) -> None:
    assert parse(text) is None


def test_typographic_apostrophe_matches_the_same_command() -> None:
    assert parse("musiqa qoʻy") == parse("musiqa qo'y")


def test_validation_rejects_apps_outside_the_whitelist() -> None:
    plan = ActionPlan(summary="x", steps=[ActionStep(kind="openApp", value="Keychain Access")])
    with pytest.raises(PlanRejected):
        validate_plan(plan)


def test_validation_rejects_non_http_urls() -> None:
    for url in ("file:///etc/passwd", "ftp://example.com", "javascript:alert(1)"):
        with pytest.raises(PlanRejected):
            validate_plan(ActionPlan(summary="x", steps=[ActionStep(kind="openUrl", value=url)]))


def test_validation_rejects_unknown_media_and_shortcut_values() -> None:
    with pytest.raises(PlanRejected):
        validate_plan(ActionPlan(summary="x", steps=[ActionStep(kind="mediaControl", value="delete")]))
    with pytest.raises(PlanRejected):
        validate_plan(ActionPlan(summary="x", steps=[ActionStep(kind="shortcut", value="quitApp")]))


def test_validation_accepts_whitelisted_plan_and_normalises_values() -> None:
    plan = validate_plan(
        ActionPlan(summary="  Safari ochaman  ", steps=[ActionStep(kind="openApp", value=" safari ")])
    )
    assert plan.summary == "Safari ochaman"
    assert plan.steps[0].value == "safari"
    assert resolve_app(plan.steps[0].value) == "Safari"


def test_conversational_plans_are_flagged_so_they_are_not_executed() -> None:
    plan = ActionPlan(summary="Javob", steps=[ActionStep(kind="respond", value="Salom")])
    assert plan.is_conversational() is True
    assert ActionPlan(summary="x", steps=[ActionStep(kind="openApp", value="Safari")]).is_conversational() is False
