import time

from fastapi.testclient import TestClient

from app.main import app, cache


def test_health():
    with TestClient(app) as client:
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"
        assert response.json()["model_status"] == "disabled"


def test_batch_job_reaches_terminal_state():
    cache.clear()
    with TestClient(app) as client:
        video_id = "demoVideo01"
        response = client.post(
            "/api/v1/analysis/batch", json={"video_ids": [video_id], "max_comments": 30}
        )
        assert response.status_code == 200
        assert response.json()["items"][0]["status"] in {"queued", "ready"}
        payload = None
        for _ in range(20):
            follow_up = client.get(f"/api/v1/analysis/{video_id}")
            if follow_up.status_code == 200 and follow_up.json()["status"] != "queued":
                payload = follow_up.json()
                break
            time.sleep(0.02)
        assert payload is not None
        assert payload["source"] == "demo"
        assert payload["sample_size"] >= 20


def test_rejects_invalid_video_id():
    with TestClient(app) as client:
        response = client.post("/api/v1/analysis/batch", json={"video_ids": ["bad id!"]})
        assert response.status_code == 422


def test_batch_status_returns_all_requested_items():
    cache.clear()
    with TestClient(app) as client:
        video_ids = ["statusVid001", "statusVid002"]
        queued = client.post(
            "/api/v1/analysis/batch", json={"video_ids": video_ids, "max_comments": 30}
        )
        assert queued.status_code == 200
        response = client.post("/api/v1/analysis/status", json={"video_ids": video_ids})
        assert response.status_code == 200
        assert {item["video_id"] for item in response.json()["items"]} == set(video_ids)
