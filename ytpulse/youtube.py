"""YouTube Data API v3 + transcript helpers."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api import YouTubeTranscriptApiException

from .models import Comment, Video


class YouTubeClient:
    def __init__(self, api_key: str, region: str = "KR", language: str = "ko"):
        self._yt = build("youtube", "v3", developerKey=api_key, cache_discovery=False)
        self._transcripts = YouTubeTranscriptApi()
        self.region = region
        self.language = language

    def search_recent(self, topic: str, days: int = 7, max_results: int = 50) -> list[Video]:
        """Videos about `topic` published in the last `days` days, most viewed first.

        search.list costs 100 quota units per page (50 results), so keep
        max_results modest.
        """
        published_after = (datetime.now(timezone.utc) - timedelta(days=days)).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
        ids: list[str] = []
        page_token = None
        while len(ids) < max_results:
            resp = (
                self._yt.search()
                .list(
                    q=topic,
                    part="id",
                    type="video",
                    order="viewCount",
                    publishedAfter=published_after,
                    regionCode=self.region,
                    relevanceLanguage=self.language,
                    maxResults=min(50, max_results - len(ids)),
                    pageToken=page_token,
                )
                .execute()
            )
            ids += [item["id"]["videoId"] for item in resp.get("items", [])]
            page_token = resp.get("nextPageToken")
            if not page_token:
                break

        videos = self._video_details(ids)
        # search.list's viewCount ordering is approximate; re-sort on real stats.
        videos.sort(key=lambda v: v.view_count, reverse=True)
        return videos

    def _video_details(self, ids: list[str]) -> list[Video]:
        videos: list[Video] = []
        for i in range(0, len(ids), 50):
            resp = (
                self._yt.videos()
                .list(part="snippet,statistics", id=",".join(ids[i : i + 50]))
                .execute()
            )
            for item in resp.get("items", []):
                sn, st = item["snippet"], item.get("statistics", {})
                thumbs = sn.get("thumbnails", {})
                thumb = (thumbs.get("medium") or thumbs.get("default") or {}).get("url", "")
                videos.append(
                    Video(
                        video_id=item["id"],
                        title=sn.get("title", ""),
                        channel=sn.get("channelTitle", ""),
                        published_at=sn.get("publishedAt", ""),
                        description=sn.get("description", ""),
                        view_count=int(st.get("viewCount", 0)),
                        like_count=int(st.get("likeCount", 0)),
                        comment_count=int(st.get("commentCount", 0)),
                        thumbnail_url=thumb,
                    )
                )
        return videos

    def top_comments(self, video_id: str, n: int = 5) -> list[Comment]:
        """Top-level comments with the most likes (empty if comments are disabled)."""
        try:
            resp = (
                self._yt.commentThreads()
                .list(
                    part="snippet",
                    videoId=video_id,
                    order="relevance",
                    maxResults=100,
                    textFormat="plainText",
                )
                .execute()
            )
        except HttpError as e:
            if e.resp.status in (403, 404):  # commentsDisabled / video not found
                return []
            raise
        comments = []
        for item in resp.get("items", []):
            c = item["snippet"]["topLevelComment"]["snippet"]
            comments.append(
                Comment(
                    author=c.get("authorDisplayName", ""),
                    text=c.get("textDisplay", ""),
                    like_count=int(c.get("likeCount", 0)),
                    published_at=c.get("publishedAt", ""),
                )
            )
        comments.sort(key=lambda c: c.like_count, reverse=True)
        return comments[:n]

    def transcript(self, video_id: str) -> str:
        """Timestamped transcript ("[mm:ss] text" per line), or "" if unavailable."""
        try:
            fetched = self._transcripts.fetch(video_id, languages=[self.language, "ko", "en"])
        except YouTubeTranscriptApiException:
            return ""
        lines = []
        for s in fetched:
            m, sec = divmod(int(s.start), 60)
            lines.append(f"[{m:02d}:{sec:02d}] {s.text}")
        return "\n".join(lines)
