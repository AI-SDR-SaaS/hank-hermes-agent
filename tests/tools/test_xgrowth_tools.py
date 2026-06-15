import json
import os
from unittest.mock import patch

import pytest

from tools import xgrowth_client


def test_check_requirements_fails_closed(monkeypatch):
    monkeypatch.delenv("XGROWTH_API_BASE", raising=False)
    monkeypatch.delenv("XGROWTH_API_KEY", raising=False)
    assert xgrowth_client.check_xgrowth_requirements() is False


def test_check_requirements_true_when_set(monkeypatch):
    monkeypatch.setenv("XGROWTH_API_BASE", "https://xgrowth.example.com")
    monkeypatch.setenv("XGROWTH_API_KEY", "k")
    assert xgrowth_client.check_xgrowth_requirements() is True


from tools import xgrowth_tools  # noqa: E402
from tools.xgrowth_tools import XGROWTH_TOOLSET  # noqa: E402


def test_toolset_constant():
    assert XGROWTH_TOOLSET == "xgrowth"
