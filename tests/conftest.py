"""Shared fixtures."""

import pytest

from custom_components.radar_occupancy import const


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Load custom_components/ in every test."""
    yield


@pytest.fixture(autouse=True)
def fast_retries(monkeypatch):
    monkeypatch.setattr(const, "OFF_RETRY_DELAY", 0)
