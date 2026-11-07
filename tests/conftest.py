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
