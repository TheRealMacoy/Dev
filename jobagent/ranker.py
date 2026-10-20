"""Optional second pass: Claude reads each shortlisted posting against the CV.

It scores fit 0-100, double-checks that the role is genuinely open worldwide,
and writes a one-line reason that goes into the sheet. Runs only when
ANTHROPIC_API_KEY is set; otherwise the keyword score is used as-is.
"""

import logging

from pydantic import BaseModel

from .profile import CANDIDATE_SUMMARY

log = logging.getLogger(__name__)

MODEL = "claude-opus-5-5"
BATCH_SIZE = 15

SYSTEM = f"""You screen remote job postings for one candidate. Their CV summary:

{CANDIDATE_SUMMARY}
For each posting, judge:
- fit (0-100): how well the candidate's experience and skills match what the role
  actually asks for. 80+ = strong match they could credibly apply to now;
  50-79 = plausible stretch; below 50 = poor fit (e.g. needs a skill set they lack,
  or is much too senior/junior).
- worldwide: true only if someone living in South Africa could be hired. Mark false
  if the posting restricts candidates to specific countries/regions, requires US/EU
  work authorisation, or requires overlap with a timezone that rules out GMT+2.
  If the posting gives no restriction, assume true.
- reason: one short sentence on why it fits (or doesn't), naming the specific
  experience that matches.
Return one assessment per posting, using the posting's index."""


class Assessment(BaseModel):
    index: int
    fit: int
    worldwide: bool
    reason: str


class Assessments(BaseModel):
    assessments: list[Assessment]


def _format(batch):
    parts = []
    for i, j in enumerate(batch):
        parts.append(
            f"<posting index=\"{i}\">\nTitle: {j.title}\nCompany: {j.company}\n"
            f"Location: {j.location or 'not stated'}\nTags: {', '.join(t for t in j.tags if t)}\n"
            f"Description: {(j.description or '')[:3500]}\n</posting>"
        )
    return "\n\n".join(parts)


def rank_with_claude(jobs, min_fit=55):
    import anthropic

    client = anthropic.Anthropic()
    kept = []
    for start in range(0, len(jobs), BATCH_SIZE):
        batch = jobs[start:start + BATCH_SIZE]
        try:
            response = client.messages.parse(
                model=MODEL,
                max_tokens=16000,
                output_config={"effort": "low"},
                system=SYSTEM,
                messages=[{"role": "user", "content": _format(batch)}],
                output_format=Assessments,
            )
        except anthropic.APIError as exc:
            log.warning("Claude ranking failed for batch %d, keeping keyword scores: %s", start, exc)
            kept.extend(batch)
            continue
        if response.stop_reason == "refusal" or response.parsed_output is None:
            log.warning("Claude returned no assessment for batch %d (%s); keeping keyword scores",
                        start, response.stop_reason)
            kept.extend(batch)
            continue
        by_index = {a.index: a for a in response.parsed_output.assessments}
        for i, job in enumerate(batch):
            a = by_index.get(i)
            if a is None:
                kept.append(job)
                continue
            if not a.worldwide or a.fit < min_fit:
                log.debug("dropped %s @ %s (fit=%s worldwide=%s)", job.title, job.company, a.fit, a.worldwide)
                continue
            job.score = a.fit
            job.reason = a.reason
            kept.append(job)
    kept.sort(key=lambda j: j.score, reverse=True)
    return kept
