import json
import providers


def test_gateway_stream(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test")
    monkeypatch.setenv("GEMINI_API_FORMAT", "openai")
    monkeypatch.setenv("GEMINI_BASE_URL", "https://gateway.example/v1/")
    seen = {}

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def raise_for_status(self):
            pass

        def iter_lines(self):
            for content in ["Left", "<!--FOLIO_CARD-->", "Strategy"]:
                yield b"data: " + json.dumps(
                    {"choices": [{"delta": {"content": content}}]}
                ).encode()
            yield b"data: [DONE]"

    def post(url, **kwargs):
        seen.update(url=url, **kwargs)
        return Response()

    monkeypatch.setattr(providers.requests, "post", post)
    assert (
        "".join(providers.gemini_stream([dict(role="user", text="Test")], {}))
        == "Left<!--FOLIO_CARD-->Strategy"
    )
    assert seen["url"] == "https://gateway.example/v1/chat/completions"
    assert seen["json"]["stream"] is True
    assert seen["headers"]["Authorization"] == "Bearer test"


def test_gateway_planner(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test")
    monkeypatch.setenv("GEMINI_API_FORMAT", "openai")

    class Response:
        def raise_for_status(self):
            pass

        def json(self):
            return {
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "profile": {"risk": "balanced"},
                                    "weights": [20, 35, 25, 10, 10],
                                }
                            )
                        }
                    }
                ]
            }

    monkeypatch.setattr(providers.requests, "post", lambda *a, **k: Response())
    profile, weights = providers.gemini_plan([], {})
    assert profile["risk"] == "balanced"
    assert sum(weights) == 100
