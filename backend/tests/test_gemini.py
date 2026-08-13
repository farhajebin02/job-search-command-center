import json
import pytest
from core import gemini


class _Resp:
    def __init__(self, text): self.text = text


def test_generate_json_parses_response(monkeypatch):
    monkeypatch.setattr(gemini, "_call", lambda p, s, m: _Resp('{"score": 88}'))
    assert gemini.generate_json("p", {"type": "object"}, "m") == {"score": 88}


def test_generate_json_raises_on_unparseable_response(monkeypatch):
    monkeypatch.setattr(gemini, "_call", lambda p, s, m: _Resp("not json"))
    with pytest.raises(ValueError, match="did not return valid JSON"):
        gemini.generate_json("p", {"type": "object"}, "m")
