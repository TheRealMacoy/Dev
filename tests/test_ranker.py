from types import SimpleNamespace
from unittest.mock import patch

from jobagent import ranker
from jobagent.models import Job


def test_rank_drops_poor_fit_and_region_locked():
    jobs = [Job(t, "Co", f"https://x/{i}", "t", "Worldwide", None) for i, t in
            enumerate(["Community Manager", "Social Lead", "Content Producer"])]
    parsed = ranker.Assessments(assessments=[
        ranker.Assessment(index=0, fit=90, worldwide=True, reason="Ran 47k Cardano community"),
        ranker.Assessment(index=1, fit=85, worldwide=False, reason="US only"),
        ranker.Assessment(index=2, fit=30, worldwide=True, reason="Needs 10y broadcast"),
    ])
    resp = SimpleNamespace(stop_reason="end_turn", parsed_output=parsed)
    with patch("anthropic.Anthropic") as client:
        client.return_value.messages.parse.return_value = resp
        out = ranker.rank_with_claude(jobs)
    assert [(j.title, j.score) for j in out] == [("Community Manager", 90)]
    assert out[0].reason.startswith("Ran")
    kwargs = client.return_value.messages.parse.call_args.kwargs
    assert kwargs["model"] == "claude-opus-5-5" and kwargs["output_format"] is ranker.Assessments
