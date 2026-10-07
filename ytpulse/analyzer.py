"""Claude-based stance classification and speaker-quote extraction."""
from __future__ import annotations

import json
import os

import anthropic

from .models import Quote, Video

DEFAULT_MODEL = "claude-opus-5-5"

# Long videos can have very long transcripts. This caps what is sent per video
# to keep cost predictable; raise it (or set to 0 for no cap) if you need more.
MAX_TRANSCRIPT_CHARS = int(os.environ.get("MAX_TRANSCRIPT_CHARS", "40000"))

SYSTEM_PROMPT = """You analyze YouTube videos for a Korean-speaking user who wants a quick read on how a topic is being received.

Given one video's metadata, transcript and top comments, decide the video's stance toward the topic:
- "positive": the video mainly supports, praises, or is favorable/optimistic about the topic
- "negative": the video mainly criticizes, opposes, or is unfavorable/pessimistic about the topic
- "neutral": straight news, mixed, or unrelated to the topic
Judge the video's own content (what the people in it say); use comments only as supporting signal.

Then pick up to 3 of the most important statements made by people speaking in the video, quoted as close to verbatim as the transcript allows, with the speaker (name or role, e.g. "진행자", "기자", "출연자") and the [mm:ss] timestamp from the transcript. If there is no transcript, return no quotes rather than inventing them.

Write summary, reason and speaker labels in Korean. Keep quotes in their original language."""

ANALYSIS_SCHEMA = {
    "type": "object",
    "properties": {
        "sentiment": {"type": "string", "enum": ["positive", "negative", "neutral"]},
        "confidence": {"type": "number"},
        "summary": {"type": "string"},
        "reason": {"type": "string"},
        "quotes": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "speaker": {"type": "string"},
                    "text": {"type": "string"},
                    "timestamp": {"type": "string"},
                },
                "required": ["speaker", "text", "timestamp"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["sentiment", "confidence", "summary", "reason", "quotes"],
    "additionalProperties": False,
}


class Analyzer:
    def __init__(self, api_key: str | None = None, model: str | None = None):
        self._client = anthropic.Anthropic(api_key=api_key) if api_key else anthropic.Anthropic()
        self.model = model or os.environ.get("CLAUDE_MODEL", DEFAULT_MODEL)

    def analyze(self, topic: str, video: Video) -> Video:
        """Fill video.sentiment / summary / reason / quotes in place and return it."""
        response = self._client.beta.messages.create(
            model=self.model,
            max_tokens=16000,
            # Classification is a simple task; low effort keeps it fast and cheap.
            output_config={
                "effort": "low",
                "format": {"type": "json_schema", "schema": ANALYSIS_SCHEMA},
            },
            # If a safety classifier declines, re-run on Anthropic's recommended fallback model.
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": _build_prompt(topic, video)}],
        )

        if response.stop_reason == "refusal":
            video.sentiment = "neutral"
            video.reason = "모델이 이 영상의 분석을 거절했습니다."
            return video

        text = "".join(b.text for b in response.content if b.type == "text")
        data = json.loads(text)
        video.sentiment = data["sentiment"]
        video.confidence = float(data["confidence"])
        video.summary = data["summary"]
        video.reason = data["reason"]
        video.quotes = [Quote(**q) for q in data["quotes"]]
        return video


def _build_prompt(topic: str, video: Video) -> str:
    transcript = video.transcript
    if MAX_TRANSCRIPT_CHARS and len(transcript) > MAX_TRANSCRIPT_CHARS:
        transcript = transcript[:MAX_TRANSCRIPT_CHARS] + "\n[... transcript truncated ...]"
    comments = "\n".join(f"- ({c.like_count} likes) {c.text}" for c in video.comments) or "(none)"
    return f"""<topic>{topic}</topic>

<video>
title: {video.title}
channel: {video.channel}
published: {video.published_at}
views: {video.view_count}
description:
{video.description[:3000]}
</video>

<transcript>
{transcript or "(no transcript available)"}
</transcript>

<top_comments>
{comments}
</top_comments>"""
