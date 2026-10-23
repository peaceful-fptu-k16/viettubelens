import hashlib
import random

import httpx

from .config import Settings
from .schemas import Comment, DataSource


class CommentsUnavailableError(RuntimeError):
    pass


POSITIVE_DEMO = [
    "Nội dung rất dễ hiểu, ngắn gọn mà đúng trọng tâm.",
    "Cách giải thích hay và có ví dụ nên mình hiểu ngay.",
    "Video chất lượng, cảm ơn kênh đã chia sẻ kiến thức hữu ích.",
    "Phần hình ảnh trực quan, xem rất cuốn và dễ theo dõi.",
    "Thông tin đầy đủ, trình bày tự nhiên và thuyết phục.",
    "Mình đã thử làm theo và kết quả khá tốt.",
    "Một góc nhìn mới rất đáng để suy nghĩ.",
    "Âm thanh rõ, nội dung có đầu tư, xứng đáng được biết đến nhiều hơn.",
]
NEUTRAL_DEMO = [
    "Mình đang xem lại để kiểm tra thêm các nguồn khác.",
    "Ai còn xem video này trong năm nay?",
    "Video dài bao nhiêu phút vậy mọi người?",
    "Mình đến đây từ phần đề xuất của YouTube.",
    "Có ai biết tài liệu được nhắc đến ở đâu không?",
]
NEGATIVE_DEMO = [
    "Tiêu đề hơi phóng đại so với phần nội dung thực tế.",
    "Ý chính ổn nhưng âm thanh nhỏ quá nên khá khó nghe.",
    "Phần này giải thích còn thiếu bằng chứng và hơi vội.",
    "Quảng cáo chen vào nhiều làm trải nghiệm bị ngắt quãng.",
    "Mình không đồng ý với kết luận vì dữ liệu chưa đủ thuyết phục.",
]
TOXIC_DEMO = [
    "Nói chuyện kiểu này thật khó chịu, đừng làm nội dung nữa.",
    "Bình luận vô lý quá, tranh luận mà không đưa ra bằng chứng gì cả.",
]


class YouTubeCollector:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def collect(self, video_id: str, max_comments: int) -> tuple[list[Comment], DataSource]:
        if self.settings.uses_demo_data:
            return self._demo_comments(video_id, max_comments), DataSource.DEMO
        params: dict[str, str | int] = {
            "part": "snippet",
            "videoId": video_id,
            "maxResults": min(max_comments, 100),
            "order": "relevance",
            "textFormat": "plainText",
            "key": self.settings.youtube_api_key,
        }
        async with httpx.AsyncClient(timeout=12) as client:
            response = await client.get(
                "https://www.googleapis.com/youtube/v3/commentThreads", params=params
            )
        if response.status_code == 403:
            raise CommentsUnavailableError("Bình luận bị tắt hoặc YouTube API đã hết quota")
        if response.status_code == 404:
            raise CommentsUnavailableError("Video không còn khả dụng")
        response.raise_for_status()
        items = response.json().get("items", [])
        comments = []
        for item in items:
            top = item.get("snippet", {}).get("topLevelComment", {})
            snippet = top.get("snippet", {})
            text = str(snippet.get("textDisplay", "")).strip()
            if text:
                comment_id = str(top.get("id", item.get("id", "")))
                comments.append(
                    Comment(
                        id=comment_id,
                        text=text,
                        like_count=int(snippet.get("likeCount", 0)),
                        url=f"https://www.youtube.com/watch?v={video_id}&lc={comment_id}",
                    )
                )
        return comments, DataSource.YOUTUBE

    @staticmethod
    def _demo_comments(video_id: str, max_comments: int) -> list[Comment]:
        seed = int(hashlib.sha256(video_id.encode()).hexdigest()[:12], 16)
        rng = random.Random(seed)
        pool = POSITIVE_DEMO * 3 + NEUTRAL_DEMO + NEGATIVE_DEMO * 2 + TOXIC_DEMO
        rng.shuffle(pool)
        count = min(max_comments, 24 + seed % 7)
        return [
            Comment(
                id=f"demo-{index}", text=pool[index % len(pool)], like_count=rng.randint(0, 180)
            )
            for index in range(count)
        ]
