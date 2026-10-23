import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from functools import partial

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .analyzer import ReactionAnalyzer
from .batcher import InferenceBatcher
from .cache import AnalysisCache
from .collector import CommentsUnavailableError, YouTubeCollector
from .config import get_settings
from .jobs import JobManager
from .model_service import PretrainedModelService
from .schemas import (
    AnalysisResult,
    AnalysisStatus,
    BatchRequest,
    BatchResponse,
    DataSource,
    StatusRequest,
)

settings = get_settings()
cache = AnalysisCache(settings.cache_path, settings.cache_ttl_seconds)
collector = YouTubeCollector(settings)
analyzer = ReactionAnalyzer(settings)
model_service = PretrainedModelService(settings, analyzer)
inference_batcher = InferenceBatcher(
    model_service, max_videos=settings.analysis_concurrency
)
jobs = JobManager(settings.analysis_concurrency)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    warmup_task = asyncio.create_task(model_service.warmup())
    yield
    await jobs.shutdown()
    await inference_batcher.shutdown()
    if not warmup_task.done():
        warmup_task.cancel()
    await asyncio.gather(warmup_task, return_exceptions=True)


app = FastAPI(title="VietTubeLens API", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost", "http://127.0.0.1"],
    allow_origin_regex=r"chrome-extension://.*|https://.*",
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)


def pending_result(video_id: str) -> AnalysisResult:
    return AnalysisResult(
        video_id=video_id,
        status=AnalysisStatus.QUEUED,
        model_version=settings.model_version,
        source=DataSource.DEMO if settings.uses_demo_data else DataSource.YOUTUBE,
    )


async def process(video_id: str, max_comments: int) -> AnalysisResult:
    try:
        comments, source = await collector.collect(video_id, max_comments)
        result = await inference_batcher.submit(video_id, comments, source)
    except CommentsUnavailableError as error:
        result = AnalysisResult(
            video_id=video_id,
            status=AnalysisStatus.UNAVAILABLE,
            message=str(error),
            model_version=settings.model_version,
            source=DataSource.DEMO if settings.uses_demo_data else DataSource.YOUTUBE,
        )
    except Exception:  # API boundary: never expose request URLs, keys, or internals
        result = AnalysisResult(
            video_id=video_id,
            status=AnalysisStatus.ERROR,
            message="Phân tích tạm thời thất bại. Vui lòng thử lại.",
            model_version=settings.model_version,
            source=DataSource.DEMO if settings.uses_demo_data else DataSource.YOUTUBE,
        )
    cache.put(result)
    return result


@app.get("/health")
async def health() -> dict[str, str | bool]:
    return {
        "status": "ok",
        "model_version": settings.model_version,
        "demo_mode": settings.uses_demo_data,
        **model_service.health(),
    }


@app.post("/api/v1/analysis/batch", response_model=BatchResponse)
async def batch_analysis(request: BatchRequest) -> BatchResponse:
    items: list[AnalysisResult] = []
    for video_id in request.video_ids:
        cached = None if request.refresh else cache.get(video_id, settings.model_version)
        if cached is not None:
            items.append(cached)
            continue
        finished = jobs.result(video_id)
        if finished is not None and not request.refresh:
            items.append(finished)
            continue
        await jobs.enqueue(video_id, partial(process, video_id, request.max_comments))
        items.append(pending_result(video_id))
    return BatchResponse(items=items)


@app.get("/api/v1/analysis/{video_id}", response_model=AnalysisResult)
async def get_analysis(video_id: str) -> AnalysisResult:
    cached = cache.get(video_id, settings.model_version)
    if cached is not None:
        return cached
    finished = jobs.result(video_id)
    if finished is not None:
        return finished
    if jobs.is_pending(video_id):
        return pending_result(video_id)
    raise HTTPException(status_code=404, detail="Analysis not found")


@app.post("/api/v1/analysis/status", response_model=BatchResponse)
async def analysis_status(request: StatusRequest) -> BatchResponse:
    items: list[AnalysisResult] = []
    for video_id in request.video_ids:
        cached = cache.get(video_id, settings.model_version)
        if cached is not None:
            items.append(cached)
            continue
        finished = jobs.result(video_id)
        if finished is not None:
            items.append(finished)
        elif jobs.is_pending(video_id):
            items.append(pending_result(video_id))
        else:
            items.append(
                AnalysisResult(
                    video_id=video_id,
                    status=AnalysisStatus.ERROR,
                    message="Không tìm thấy tác vụ phân tích",
                    model_version=settings.model_version,
                    source=DataSource.DEMO if settings.uses_demo_data else DataSource.YOUTUBE,
                )
            )
    return BatchResponse(items=items)


@app.delete("/api/v1/cache")
async def clear_cache() -> dict[str, int | str]:
    return {"status": "ok", "deleted": cache.clear()}
