"""Collect a privacy-minimized Vietnamese YouTube comment seed dataset."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import time
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

API_ROOT = "https://www.googleapis.com/youtube/v3"
DEFAULT_TOPICS = {
    "education": "giáo dục kiến thức Việt Nam",
    "technology": "công nghệ đánh giá Việt Nam",
    "gaming": "game Việt Nam review",
    "music": "âm nhạc Việt Nam",
    "news": "tin tức Việt Nam phân tích",
    "food": "ẩm thực Việt Nam review",
    "travel": "du lịch Việt Nam trải nghiệm",
    "science": "khoa học Việt Nam",
}
VIETNAMESE_MARKS = re.compile(r"[àáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡ"
                              r"ùúụủũưừứựửữỳýỵỷỹđ]", re.IGNORECASE)
VIETNAMESE_WORDS = {
    "anh", "ban", "bạn", "bài", "cho", "có", "của", "hay", "không", "là", "mình",
    "này", "nhưng", "quá", "rất", "thấy", "thật", "video", "với", "xem", "được",
}


def load_api_key(env_file: Path | None) -> str:
    key = os.getenv("YOUTUBE_API_KEY", "").strip()
    if key or env_file is None or not env_file.exists():
        return key
    for line in env_file.read_text("utf-8").splitlines():
        if line.startswith("YOUTUBE_API_KEY="):
            return line.split("=", 1)[1].strip().strip("'\"")
    return ""


def is_probably_vietnamese(text: str) -> bool:
    lowered = text.lower()
    if VIETNAMESE_MARKS.search(lowered):
        return True
    tokens = set(re.findall(r"[a-zA-ZÀ-ỹ]+", lowered))
    return len(tokens & VIETNAMESE_WORDS) >= 2


def normalize_text(text: str) -> str:
    return " ".join(text.replace("\u200b", " ").split()).strip()


def pseudonymous_id(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:24]


class YouTubeDatasetCollector:
    def __init__(self, api_key: str, timeout: float = 20) -> None:
        self.api_key = api_key
        self.client = httpx.Client(timeout=timeout)

    def close(self) -> None:
        self.client.close()

    def _get(self, resource: str, **params: str | int) -> dict[str, Any]:
        response = self.client.get(
            f"{API_ROOT}/{resource}", params={**params, "key": self.api_key}
        )
        response.raise_for_status()
        return dict(response.json())

    def discover(self, query: str, limit: int) -> list[str]:
        payload = self._get(
            "search",
            part="snippet",
            q=query,
            type="video",
            maxResults=min(limit * 2, 50),
            relevanceLanguage="vi",
            regionCode="VN",
            safeSearch="moderate",
            order="relevance",
        )
        return [
            str(item["id"]["videoId"])
            for item in payload.get("items", [])
            if item.get("snippet", {}).get("liveBroadcastContent") == "none"
        ][:limit]

    def video_metadata(self, video_ids: list[str]) -> dict[str, dict[str, str]]:
        if not video_ids:
            return {}
        payload = self._get(
            "videos",
            part="snippet,statistics,liveStreamingDetails",
            id=",".join(video_ids),
            maxResults=50,
        )
        metadata: dict[str, dict[str, str]] = {}
        for item in payload.get("items", []):
            snippet = item.get("snippet", {})
            if snippet.get("liveBroadcastContent") != "none" or item.get(
                "liveStreamingDetails"
            ):
                continue
            metadata[str(item["id"])] = {
                "channel_id": str(snippet.get("channelId", "unknown")),
                "title": normalize_text(str(snippet.get("title", ""))),
                "published_at": str(snippet.get("publishedAt", "")),
            }
        return metadata

    def comments(self, video_id: str, limit: int) -> list[dict[str, Any]]:
        comments: list[dict[str, Any]] = []
        page_token = ""
        while len(comments) < limit:
            params: dict[str, str | int] = {
                "part": "snippet",
                "videoId": video_id,
                "maxResults": min(100, limit - len(comments)),
                "order": "relevance",
                "textFormat": "plainText",
            }
            if page_token:
                params["pageToken"] = page_token
            try:
                payload = self._get("commentThreads", **params)
            except httpx.HTTPStatusError as error:
                if error.response.status_code in {403, 404}:
                    return comments
                raise
            for item in payload.get("items", []):
                top = item.get("snippet", {}).get("topLevelComment", {})
                snippet = top.get("snippet", {})
                text = normalize_text(str(snippet.get("textDisplay", "")))
                if text and is_probably_vietnamese(text):
                    comments.append(
                        {
                            "source_comment_id": str(top.get("id", item.get("id", ""))),
                            "text": text,
                            "like_count": max(0, int(snippet.get("likeCount", 0))),
                            "published_at": snippet.get("publishedAt"),
                        }
                    )
            page_token = str(payload.get("nextPageToken", ""))
            if not page_token:
                break
        return comments[:limit]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--env-file", type=Path, default=Path("../backend/.env"))
    parser.add_argument("--topics", default=",".join(DEFAULT_TOPICS))
    parser.add_argument("--videos-per-topic", type=int, default=8)
    parser.add_argument("--comments-per-video", type=int, default=80)
    parser.add_argument("--max-comments", type=int, default=5000)
    args = parser.parse_args()
    if min(args.videos_per_topic, args.comments_per_video, args.max_comments) < 1:
        raise ValueError("Collection limits must be positive")
    topics = [topic.strip() for topic in args.topics.split(",") if topic.strip()]
    unknown = sorted(set(topics) - set(DEFAULT_TOPICS))
    if unknown:
        raise ValueError(f"Unknown topics: {', '.join(unknown)}")
    api_key = load_api_key(args.env_file)
    if not api_key:
        raise ValueError("YOUTUBE_API_KEY is missing")

    collector = YouTubeDatasetCollector(api_key)
    collected_at = datetime.now(UTC).isoformat()
    records: list[dict[str, Any]] = []
    seen_texts: set[str] = set()
    video_counts: Counter[str] = Counter()
    try:
        for topic in topics:
            video_ids = collector.discover(DEFAULT_TOPICS[topic], args.videos_per_topic)
            metadata = collector.video_metadata(video_ids)
            for video_id in video_ids:
                if len(records) >= args.max_comments:
                    break
                if video_id not in metadata:
                    continue
                item = metadata[video_id]
                for comment in collector.comments(video_id, args.comments_per_video):
                    fingerprint = hashlib.sha256(
                        comment["text"].casefold().encode("utf-8")
                    ).hexdigest()
                    if fingerprint in seen_texts:
                        continue
                    seen_texts.add(fingerprint)
                    records.append(
                        {
                            "video_id": video_id,
                            "comment_id": pseudonymous_id(comment.pop("source_comment_id")),
                            "channel_id": item["channel_id"],
                            "topic": topic,
                            "video_title": item["title"],
                            "collected_at": collected_at,
                            **comment,
                        }
                    )
                    video_counts[video_id] += 1
                    if len(records) >= args.max_comments:
                        break
                time.sleep(0.05)
    finally:
        collector.close()

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="\n") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    summary = {
        "collected_at": collected_at,
        "comments": len(records),
        "videos": len(video_counts),
        "channels": len({record["channel_id"] for record in records}),
        "topics": dict(Counter(record["topic"] for record in records)),
        "privacy": "author fields omitted; source comment IDs SHA-256 pseudonymized",
    }
    args.output.with_suffix(".summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
