"""Fixtures for testing the custom Owlet integration."""

import pytest


@pytest.fixture(autouse=True)
def enable_custom_integration(enable_custom_integrations):
    """Load the integration from custom_components."""
    yield


@pytest.fixture
def mock_recorder_before_hass(request):
    """Initialize recorder fixtures before HA, as required by its recorder harness."""
    if "recorder_mock" in request.fixturenames:
        request.getfixturevalue("async_test_recorder")


@pytest.fixture
def prepare_legacy_recorder_database(request):
    """Prepare the old recorder database before its HA fixture starts."""
    from homeassistant.const import __version__

    if __version__.startswith("2024.1.") and "recorder_mock" in request.fixturenames:
        request.getfixturevalue("recorder_db_url")


@pytest.fixture
def hass(prepare_legacy_recorder_database, hass):
    """Order legacy recorder prerequisites before the upstream HA fixture."""
    return hass
