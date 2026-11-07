"""Blueprint schema and startup/recovery notification policy."""

from pathlib import Path

import pytest
from homeassistant.components.blueprint.models import Blueprint
from homeassistant.helpers import template
from homeassistant.util.yaml import load_yaml


@pytest.mark.parametrize(
    "name", ["owlet_alert_notification", "owlet_stale_data_notification"]
)
async def test_blueprint_expands_and_validates(hass, name):
    from homeassistant.components.automation import config as automation_config

    PLATFORM_SCHEMA = automation_config.PLATFORM_SCHEMA

    config = load_yaml(Path("blueprints/automation/owlet") / f"{name}.yaml")
    blueprint = Blueprint(
        config,
        expected_domain="automation",
        schema=automation_config.AUTOMATION_BLUEPRINT_SCHEMA,
    )
    inputs = {"notify_device": "synthetic-phone", "notify_initial_active": True}
    inputs.update(
        {"alert_sensors": ["binary_sensor.test_alert"]}
        if name == "owlet_alert_notification"
        else {"stale_sensor": "binary_sensor.test_stale"}
    )
    from homeassistant.components.blueprint.models import BlueprintInputs

    expanded = BlueprintInputs(
        blueprint, {"use_blueprint": {"path": f"owlet/{name}.yaml", "input": inputs}}
    ).async_substitute()
    validated = PLATFORM_SCHEMA(expanded)
    assert validated


@pytest.mark.parametrize(
    "initial,prior,expected",
    [
        (False, "off", ["binary_sensor.test_alert"]),
        (False, "unavailable", []),
        (False, None, []),
        (True, "unavailable", ["binary_sensor.test_alert"]),
        (True, None, ["binary_sensor.test_alert"]),
    ],
)
async def test_initial_active_policy(hass, initial, prior, expected):
    from homeassistant.core import State

    config = load_yaml(
        Path("blueprints/automation/owlet/owlet_alert_notification.yaml")
    )
    expression = template.Template(config["variables"]["active_alerts"], hass)
    trigger = {
        "id": "changed",
        "entity_id": "binary_sensor.test_alert",
        "from_state": State("binary_sensor.test_alert", prior) if prior else None,
    }
    assert (
        expression.async_render(
            {
                "trigger": trigger,
                "notify_initial_active": initial,
                "selected_alerts": ["binary_sensor.test_alert"],
            }
        )
        == expected
    )


async def test_startup_explicitly_includes_already_active_selected_alerts(hass):
    config = load_yaml(
        Path("blueprints/automation/owlet/owlet_alert_notification.yaml")
    )
    expression = template.Template(config["variables"]["active_alerts"], hass)
    hass.states.async_set("binary_sensor.test_alert", "on")
    variables = {
        "trigger": {"id": "startup"},
        "notify_initial_active": True,
        "selected_alerts": ["binary_sensor.test_alert"],
    }
    assert expression.async_render(variables) == ["binary_sensor.test_alert"]
    variables["notify_initial_active"] = False
    assert expression.async_render(variables) == []


@pytest.mark.parametrize("path", list(Path("dashboards").glob("*.yaml")))
def test_dashboards_parse(path):
    assert load_yaml(path)["views"]


def dashboard_cards(config):
    for view in config["views"]:
        yield from view.get("cards", [])
        for section in view.get("sections", []):
            yield from section.get("cards", [])


@pytest.mark.parametrize("locale", ["en", "nl"])
async def test_dashboard_explains_disabled_unknown_stale_and_failed_freshness(
    hass, locale
):
    config = load_yaml(
        Path("dashboards/owlet.yaml" if locale == "en" else "dashboards/owlet_nl.yaml")
    )
    cards = list(dashboard_cards(config))
    source = next(
        card["content"]
        for card in cards
        if "freshness_enabled" in card.get("content", "")
    )
    assert "utcnow(" not in source and "now(" not in source
    expression = template.Template(source, hass)
    entity = "binary_sensor.owlet_sock_serial_number_" + (
        "data_stale" if locale == "en" else "verouderde_gegevens"
    )
    assert (
        "unavailable" if locale == "en" else "niet beschikbaar"
    ) in expression.async_render()
    for state, enabled, success, expected in (
        ("off", False, True, "off" if locale == "en" else "uit"),
        (
            "on",
            True,
            True,
            "stale or unknown" if locale == "en" else "verouderd of onbekend",
        ),
        ("off", True, True, "within" if locale == "en" else "binnen"),
        ("off", True, False, "failed" if locale == "en" else "mislukt"),
    ):
        hass.states.async_set(
            entity,
            state,
            {
                "freshness_enabled": enabled,
                "poll_success": success,
                "affected_readings": ["heart_rate"],
            },
        )
        assert expected in expression.async_render()
    controls = next(view for view in config["views"] if view.get("path") == "controls")
    assert any(
        card.get("entity", "").startswith("switch.") for card in controls["cards"]
    )
    for view in config["views"]:
        if view is controls:
            continue
        assert not any(
            card.get("entity", "").startswith("switch.")
            for card in dashboard_cards({"views": [view]})
        )


@pytest.mark.parametrize("locale", ["en", "nl"])
async def test_dashboard_never_hides_unknown_alerts_as_all_clear(hass, locale):
    import re

    config = load_yaml(
        Path("dashboards/owlet.yaml" if locale == "en" else "dashboards/owlet_nl.yaml")
    )
    source = next(
        card["content"]
        for card in dashboard_cards(config)
        if "namespace(unknown" in card.get("content", "")
    )
    expression = template.Template(source, hass)
    unknown = (
        "unknown or unavailable" if locale == "en" else "onbekend of niet beschikbaar"
    )
    assert unknown in expression.async_render()
    entities = list(dict.fromkeys(re.findall(r"binary_sensor\.[a-z0-9_]+", source)))
    assert len(entities) == 9
    for entity in entities:
        hass.states.async_set(entity, "off")
    assert (
        "flags are off" if locale == "en" else "alarmvlaggen staan uit"
    ) in expression.async_render()
    hass.states.async_set(entities[0], "on")
    assert (
        "active alerts" if locale == "en" else "actieve alarmen"
    ) in expression.async_render()
    hass.states.async_set(entities[1], "unavailable")
    result = expression.async_render()
    assert unknown in result
    assert ("active alerts" if locale == "en" else "actieve alarmen") in result
