import asyncio
from functools import partial

from app.jobs import JobManager
from app.schemas import AnalysisResult, AnalysisStatus, DataSource


async def test_job_manager_limits_parallel_analysis() -> None:
    jobs = JobManager(max_concurrent=2)
    active = 0
    peak = 0

    async def work(video_id: str) -> AnalysisResult:
        nonlocal active, peak
        active += 1
        peak = max(peak, active)
        await asyncio.sleep(0.01)
        active -= 1
        return AnalysisResult(
            video_id=video_id,
            status=AnalysisStatus.READY,
            model_version="test",
            source=DataSource.DEMO,
        )

    for index in range(6):
        video_id = f"video{index:06d}"
        await jobs.enqueue(video_id, partial(work, video_id))

    while any(jobs.is_pending(f"video{index:06d}") for index in range(6)):
        await asyncio.sleep(0.005)

    assert peak == 2
    await jobs.shutdown()
