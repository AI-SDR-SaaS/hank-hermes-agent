"""Tests for tools/fastlane_client.py."""

from unittest.mock import patch

import httpx
import pytest

from tools import fastlane_client


def test_check_requirements_fails_closed(monkeypatch):
    monkeypatch.delenv("FASTLANE_API_KEY", raising=False)
    assert fastlane_client.check_fastlane_requirements() is False


def test_check_requirements_true_when_set(monkeypatch):
    monkeypatch.setenv("FASTLANE_API_KEY", "fsln_live_test")
    assert fastlane_client.check_fastlane_requirements() is True


def test_base_url_default(monkeypatch):
    monkeypatch.delenv("FASTLANE_API_BASE", raising=False)
    assert fastlane_client._base_url() == "https://api.usefastlane.ai/api/v1"


def test_base_url_override(monkeypatch):
    monkeypatch.setenv("FASTLANE_API_BASE", "https://api.staging.fastlane/api/v1")
    assert fastlane_client._base_url() == "https://api.staging.fastlane/api/v1"
