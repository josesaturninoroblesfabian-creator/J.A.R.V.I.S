"""The process-wide benchmark wrapper must respect explicit client opt-outs."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from openjarvis.agents.hybrid._openai_retry import _wrap_create


@pytest.mark.parametrize(
    "base_url",
    [
        "https://api.openai.com/v1",
        "https://api.groq.com/openai/v1",
        "http://127.0.0.1:8000/v1",
    ],
)
def test_no_retries_means_one_attempt(base_url, monkeypatch):
    import openai
    from openjarvis.agents.hybrid import _openai_retry

    sleep = Mock(side_effect=AssertionError("explicit retry opt-out must not sleep"))
    monkeypatch.setattr(_openai_retry.time, "sleep", sleep)
    error = openai.APIConnectionError(request=Mock())
    operation = Mock(side_effect=error)
    resource = SimpleNamespace(
        _client=SimpleNamespace(base_url=base_url, max_retries=0)
    )
    with pytest.raises(openai.APIConnectionError):
        _wrap_create(operation)(resource)
    operation.assert_called_once_with(resource)
    sleep.assert_not_called()
