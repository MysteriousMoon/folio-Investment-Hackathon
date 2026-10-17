import pytest
import providers


@pytest.mark.parametrize("base", [None, "", "  ", "https://custom.example/v1beta/"])
@pytest.mark.parametrize("action", ["generateContent", "streamGenerateContent"])
def test_native_requests_use_configured_endpoint(monkeypatch, base, action):
    monkeypatch.setenv("GEMINI_API_KEY", "test")
    monkeypatch.setenv("GEMINI_API_FORMAT", "google")
    monkeypatch.setenv("GEMINI_MODEL", "test-model")
    if base is None:
        monkeypatch.delenv("GEMINI_BASE_URL", raising=False)
    else:
        monkeypatch.setenv("GEMINI_BASE_URL", base)
    expected = (
        base.strip().rstrip("/")
        if base and base.strip()
        else providers.OFFICIAL_GEMINI_BASE_URL
    )

    class RequestObserved(Exception):
        pass

    def post(url, **kwargs):
        assert url == f"{expected}/models/test-model:{action}"
        assert kwargs["headers"]["x-goog-api-key"] == "test"
        raise RequestObserved

    monkeypatch.setattr(providers.requests, "post", post)
    with pytest.raises(RequestObserved):
        if action == "streamGenerateContent":
            list(providers.gemini_stream([], {}))
        else:
            providers.gemini_plan([], {})


def test_official_compatible_endpoint(monkeypatch):
    monkeypatch.delenv("GEMINI_BASE_URL", raising=False)
    assert (
        providers.compatible_endpoint()
        == providers.OFFICIAL_GEMINI_BASE_URL + "/openai/chat/completions"
    )
