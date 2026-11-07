"""Blueprint schema and startup/recovery notification policy."""

import inspect
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
        **(
            {"schema": automation_config.AUTOMATION_BLUEPRINT_SCHEMA}
            if "schema" in inspect.signature(Blueprint).parameters
            else {}
        ),
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
