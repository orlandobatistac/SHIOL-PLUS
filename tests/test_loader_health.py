import sys
from types import ModuleType, SimpleNamespace

from src import loader


def _build_mock_response(status_code: int, text: str) -> SimpleNamespace:
    return SimpleNamespace(status_code=status_code, text=text)


def _build_requests_module(responses):
    module = ModuleType("requests")
    module.calls = []

    def get(url, headers=None, params=None, timeout=None):
        module.calls.append((url, headers, params, timeout))
        for substring, response in responses:
            if substring in url:
                return response
        raise AssertionError(f"Unexpected URL called during health check: {url}")

    module.get = get
    return module


def test_quick_health_check_reports_all_sources(monkeypatch):
    fake_requests = _build_requests_module([
        ("powerball.com", _build_mock_response(200, "<span>number-powerball</span>")),
        ("nclottery.com", _build_mock_response(200, "x" * 2000)),
        ("api.musl.com", _build_mock_response(200, "{}")),
    ])

    monkeypatch.setitem(sys.modules, "requests", fake_requests)
    monkeypatch.setenv("MUSL_API_KEY", "mock-key")

    health = loader.quick_health_check_sources()

    assert health == {
        "powerball_official": True,
        "web_scraping": True,
        "musl_api": True,
    }
    assert len(fake_requests.calls) == 3


def test_quick_health_check_detects_degraded_sources(monkeypatch):
    fake_requests = _build_requests_module([
        ("powerball.com", _build_mock_response(500, "<span>offline</span>")),
        ("nclottery.com", _build_mock_response(200, "short")),
        ("api.musl.com", _build_mock_response(503, "{}")),
    ])

    monkeypatch.setitem(sys.modules, "requests", fake_requests)
    monkeypatch.setenv("MUSL_API_KEY", "mock-key")

    health = loader.quick_health_check_sources()

    assert health == {
        "powerball_official": False,
        "web_scraping": False,
        "musl_api": False,
    }
    assert len(fake_requests.calls) == 3
