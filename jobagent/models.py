from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Job:
    title: str
    company: str
    url: str
    source: str
    location: str
    posted_at: datetime | None
    description: str = ""
    tags: list[str] = field(default_factory=list)
    # Set by the source when it already knows the job is open worldwide
    # (e.g. Himalayas with no location restrictions).
    worldwide_hint: bool | None = None

    # Filled in by matching / ranking.
    score: float = 0.0
    matched: list[str] = field(default_factory=list)
    reason: str = ""
