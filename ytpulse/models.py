from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Comment:
    author: str
    text: str
    like_count: int
    published_at: str


@dataclass
class Quote:
    speaker: str
    text: str
    timestamp: str  # "mm:ss" or "" if unknown


@dataclass
class Video:
    video_id: str
    title: str
    channel: str
    published_at: str
    description: str
    view_count: int
    like_count: int
    comment_count: int
    thumbnail_url: str = ""
    transcript: str = ""
    comments: list[Comment] = field(default_factory=list)
    # Filled in by the analyzer
    sentiment: str = ""  # "positive" | "negative" | "neutral"
    confidence: float = 0.0
    summary: str = ""
    reason: str = ""
    quotes: list[Quote] = field(default_factory=list)

    @property
    def url(self) -> str:
        return f"https://www.youtube.com/watch?v={self.video_id}"


@dataclass
class TopicReport:
    topic: str
    days: int
    positive: list[Video]
    negative: list[Video]
    scanned: int  # how many candidate videos were analyzed
    analyzed: list[Video] = field(default_factory=list)  # every analyzed video, by views
