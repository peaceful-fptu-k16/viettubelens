import asyncio
from collections.abc import Awaitable, Callable

from .schemas import AnalysisResult

JobFactory = Callable[[], Awaitable[AnalysisResult]]


class JobManager:
    def __init__(self, max_concurrent: int = 2) -> None:
        self._tasks: dict[str, asyncio.Task[AnalysisResult]] = {}
        self._results: dict[str, AnalysisResult] = {}
        self._lock = asyncio.Lock()
        self._slots = asyncio.Semaphore(max_concurrent)

    async def enqueue(self, video_id: str, factory: JobFactory) -> None:
        async with self._lock:
            task = self._tasks.get(video_id)
            if task is not None and not task.done():
                return
            self._tasks[video_id] = asyncio.create_task(self._run(video_id, factory))

    async def _run(self, video_id: str, factory: JobFactory) -> AnalysisResult:
        async with self._slots:
            result = await factory()
        self._results[video_id] = result
        return result

    def result(self, video_id: str) -> AnalysisResult | None:
        return self._results.get(video_id)

    def is_pending(self, video_id: str) -> bool:
        task = self._tasks.get(video_id)
        return task is not None and not task.done()

    async def shutdown(self) -> None:
        pending = [task for task in self._tasks.values() if not task.done()]
        for task in pending:
            task.cancel()
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)
