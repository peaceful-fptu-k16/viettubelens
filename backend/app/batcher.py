import asyncio
from dataclasses import dataclass

from .model_service import PretrainedModelService
from .schemas import AnalysisResult, Comment, DataSource


@dataclass(slots=True)
class BatchItem:
    video_id: str
    comments: list[Comment]
    source: DataSource
    future: asyncio.Future[AnalysisResult]


class InferenceBatcher:
    """Coalesces nearby video jobs into one cross-video model pass."""

    def __init__(
        self,
        model_service: PretrainedModelService,
        *,
        max_videos: int = 3,
        flush_delay_seconds: float = 0.075,
    ) -> None:
        self.model_service = model_service
        self.max_videos = max_videos
        self.flush_delay_seconds = flush_delay_seconds
        self._queue: asyncio.Queue[BatchItem] = asyncio.Queue()
        self._worker: asyncio.Task[None] | None = None

    async def submit(
        self, video_id: str, comments: list[Comment], source: DataSource
    ) -> AnalysisResult:
        loop = asyncio.get_running_loop()
        future: asyncio.Future[AnalysisResult] = loop.create_future()
        await self._queue.put(BatchItem(video_id, comments, source, future))
        if self._worker is None or self._worker.done():
            self._worker = asyncio.create_task(self._run())
        return await future

    async def _run(self) -> None:
        while True:
            first = await self._queue.get()
            batch = [first]
            await asyncio.sleep(self.flush_delay_seconds)
            while len(batch) < self.max_videos and not self._queue.empty():
                batch.append(self._queue.get_nowait())
            try:
                results = await self.model_service.analyze_adaptive_many(
                    [(item.video_id, item.comments, item.source) for item in batch]
                )
                for item, result in zip(batch, results, strict=True):
                    if not item.future.cancelled():
                        item.future.set_result(result)
            except Exception as error:
                for item in batch:
                    if not item.future.cancelled():
                        item.future.set_exception(error)
            finally:
                for _ in batch:
                    self._queue.task_done()

    async def shutdown(self) -> None:
        if self._worker is None:
            return
        self._worker.cancel()
        await asyncio.gather(self._worker, return_exceptions=True)
        self._worker = None
