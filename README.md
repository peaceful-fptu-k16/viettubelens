<div align="center">

![VietTubeLens — Signal Prism](docs/assets/readme-hero.svg?v=static-cards-2)

# VietTubeLens

### Hiểu phản ứng cộng đồng trước khi bạn nhấn xem.

Chrome Extension phân tích cảm xúc, độc hại và các góc nhìn nổi bật trong bình luận YouTube tiếng Việt — trực tiếp trên từng video card.

[![Manifest V3](https://img.shields.io/badge/Chrome-Manifest%20V3-7C5CFC?style=flat-square&logo=googlechrome&logoColor=white)](apps/extension/public/manifest.json)
[![React](https://img.shields.io/badge/React-18-22D3EE?style=flat-square&logo=react&logoColor=07111F)](apps/extension/package.json)
[![FastAPI](https://img.shields.io/badge/FastAPI-Python-A3E635?style=flat-square&logo=fastapi&logoColor=07111F)](backend/pyproject.toml)
[![Tests](https://img.shields.io/badge/tests-14%20passing-14B8A6?style=flat-square)](#kiểm-thử--chất-lượng)
[![Language](https://img.shields.io/badge/UI-Tiếng%20Việt-F9738C?style=flat-square)](#trải-nghiệm-signal-prism)

[Bắt đầu nhanh](#bắt-đầu-nhanh) · [Tính năng](#điểm-nổi-bật) · [Kiến trúc](#kiến-trúc) · [API](#api) · [Cấu hình](#cấu-hình) · [Khắc phục lỗi](#khắc-phục-lỗi)

</div>

> [!IMPORTANT]
> VietTubeLens mô tả **phản ứng trong mẫu bình luận đã phân tích**, không chấm điểm chất lượng khách quan của video và không đại diện cho toàn bộ người xem.

## VietTubeLens giải quyết điều gì?

Một thumbnail hấp dẫn chưa cho biết cộng đồng thực sự phản ứng thế nào. Việc mở từng video, cuộn bình luận và tự tổng hợp ý kiến vừa chậm vừa dễ bị chi phối bởi một vài bình luận nổi bật.

VietTubeLens đặt một lớp tín hiệu nhỏ ngay trên trang chủ và kết quả tìm kiếm YouTube:

- Nhìn nhanh tỷ lệ phản ứng tích cực, trung lập và tiêu cực.
- Nhận biết dấu hiệu bình luận độc hại mà không cần đọc toàn bộ thảo luận.
- Kiểm tra bằng chứng từ tối đa ba bình luận đại diện.
- Thấy rõ độ tin cậy, cỡ mẫu và lý do hệ thống từ chối kết luận.
- Khám phá góc nhìn thiểu số khi cộng đồng có dấu hiệu phân cực.

<div align="center">

![Luồng tín hiệu VietTubeLens](docs/assets/readme-flow.svg?v=static-cards-2)

</div>

## Điểm nổi bật

<div align="center">

![Feature constellation của VietTubeLens](docs/assets/readme-constellation.svg?v=static-cards-2)

</div>

| Khả năng | Cách hoạt động |
|---|---|
| **Lens Badge trong viewport** | Theo dõi card bằng `MutationObserver` và `IntersectionObserver`; chỉ phân tích khi video đi vào vùng nhìn. |
| **Tối đa 12 video** | Scheduler ưu tiên card đang nhìn thấy, bỏ qua livestream và tiếp tục khi người dùng cuộn. |
| **Cache-first** | Đọc backend cache và session cache của extension trước khi tạo tác vụ mới. |
| **Phân tích thích ứng** | Bắt đầu với 16 bình luận; tự mở rộng đến 30 khi confidence thấp hoặc cần từ chối kết luận. |
| **Batch inference** | Gom tác vụ gần nhau thành một lượt suy luận, tối đa ba video trong một model pass. |
| **Evidence-first** | Hiện bình luận đại diện, sentiment, liên kết gốc và bằng chứng góc nhìn thiểu số. |
| **Biết từ chối** | Trả về `insufficient_data` khi thiếu bình luận phù hợp hoặc confidence dưới ngưỡng. |
| **Không làm vỡ YouTube** | UI đặt trong isolated root, không sửa style gốc và tự thích ứng light/dark mode. |
| **Accessible motion** | Animation chỉ dùng `transform`/`opacity`, hỗ trợ bàn phím và `prefers-reduced-motion`. |
| **Fallback an toàn** | Nếu checkpoint không tải được, backend chuyển sang heuristic fallback và khai báo trạng thái. |

## Trải nghiệm Signal Prism

Signal Prism là ngôn ngữ nhận diện riêng của VietTubeLens:

- **Prism Violet** `#7C5CFC` — phân tích và nhận diện.
- **Signal Cyan** `#22D3EE` — dữ liệu và trạng thái hoạt động.
- **Insight Lime** `#A3E635` — confidence và hoàn thành.
- **Ink** `#0B1020` — nền tương phản cao.
- Manrope cho tiêu đề, Inter cho nội dung; toàn bộ font được đóng gói cục bộ.

Badge mở rộng khi hover hoặc focus. Click sẽ mở popover tại chỗ với phân bố cảm xúc, toxicity, cỡ mẫu, confidence, evidence và trạng thái cache. Khi một popover mở, các badge khác được ẩn tạm thời để không che nội dung.

Các trạng thái `queued`, `ready`, `insufficient_data`, `unavailable`, `error` và skeleton loading có cách thể hiện riêng. Kết quả hoàn thành có prism sweep một lần; giao diện không phát hiệu ứng liên tục gây xao nhãng.

<div align="center">

![Ba trạng thái trung thực của VietTubeLens](docs/assets/readme-states.svg?v=static-cards-2)

</div>

## Kiến trúc

<div align="center">

![Sơ đồ kiến trúc VietTubeLens](docs/assets/readme-architecture.svg?v=static-cards-2)

</div>

1. Content script phát hiện card hợp lệ trong viewport và loại livestream.
2. Service worker kiểm tra session cache rồi gửi các ID còn thiếu theo batch.
3. Backend trả kết quả cache ngay hoặc trạng thái `queued`.
4. Cache miss được thu thập tối đa 30 top-level comment theo relevance.
5. Model warm-up chạy nền; các video gần nhau được gom vào một lượt suy luận.
6. Bộ tổng hợp tính sentiment, toxicity, confidence, polarization và evidence.
7. Extension polling theo batch với backoff và cập nhật độc lập từng badge.

## Công nghệ

| Lớp | Công nghệ |
|---|---|
| Extension | React 18, TypeScript strict, Vite, Manifest V3, isolated DOM |
| Backend | Python 3.11+, FastAPI, Pydantic, HTTPX, SQLite, asyncio |
| NLP | PyTorch, Transformers, ViSoBERT sentiment, ONNX Runtime toxicity |
| UI | CSS design tokens, Manrope, Inter, Lucide, reduced-motion support |
| Chất lượng | Vitest, TypeScript, pytest, Ruff, mypy |

## Bắt đầu nhanh

### Yêu cầu

- Chrome hoặc Chromium hỗ trợ Manifest V3.
- Node.js 20+ và npm.
- Python 3.11+.
- Khoảng 3–5 GB trống cho môi trường Python và checkpoint model.
- YouTube Data API v3 key nếu muốn phân tích bình luận thật.

### 1. Clone repository

```bash
git clone https://github.com/peaceful-fptu-k16/viettubelens.git
cd viettubelens
```

### 2. Chạy backend

<details open>
<summary><strong>Windows PowerShell</strong></summary>

```powershell
cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e ".[dev,ml]"
Copy-Item .env.example .env
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

</details>

<details>
<summary><strong>macOS / Linux</strong></summary>

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev,ml]"
cp .env.example .env
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

</details>

Mặc định `.env.example` bật demo mode. Để dùng bình luận thật:

```dotenv
YOUTUBE_API_KEY=your_new_key_here
DEMO_MODE=false
```

Kiểm tra backend tại `http://127.0.0.1:8000/health`; Swagger UI tại `http://127.0.0.1:8000/docs`. Lần đầu sẽ tải checkpoint, sau đó model được giữ resident cho các lượt tiếp theo.

### 3. Cài extension

Repository có sẵn bản build trong `apps/extension/dist`. Sau khi clone, có thể mở
`chrome://extensions`, bật **Developer mode**, chọn **Load unpacked** và trỏ thẳng
đến thư mục này. Trong popup, nhập URL HTTPS của backend rồi chọn **Lưu & kiểm tra**.

Nếu thay đổi source, build lại bằng:

```bash
npm install
npm run build
```

1. Mở `chrome://extensions` và bật **Developer mode**.
2. Chọn **Load unpacked** → `apps/extension/dist`.
3. Mở YouTube và refresh trang một lần.
4. Mở popup VietTubeLens để kiểm tra backend và content script.

## Cấu hình

| Biến | Mặc định | Ý nghĩa |
|---|---:|---|
| `YOUTUBE_API_KEY` | trống | API key chỉ lưu ở backend. |
| `DEMO_MODE` | `true` trong example | Dùng dữ liệu mô phỏng, không tiêu quota. |
| `USE_PRETRAINED_MODELS` | `true` | Tắt để dùng heuristic fallback trong test/máy nhẹ. |
| `MODEL_DEVICE` | `auto` | PyTorch chọn CUDA nếu khả dụng, ngược lại dùng CPU. |
| `MODEL_BATCH_SIZE` | `16` | Số comment mỗi lượt model inference. |
| `ANALYSIS_CONCURRENCY` | `3` | Số video tối đa trong một micro-batch. |
| `ADAPTIVE_INITIAL_COMMENTS` | `16` | Cỡ mẫu phân tích ban đầu. |
| `ADAPTIVE_EXPAND_CONFIDENCE` | `0.72` | Mở rộng mẫu khi thấp hơn ngưỡng này. |
| `MIN_RELEVANT_COMMENTS` | `10` | Dưới ngưỡng sẽ từ chối kết luận. |
| `CONFIDENCE_THRESHOLD` | `0.58` | Confidence tối thiểu để kết luận. |
| `CACHE_TTL_SECONDS` | `86400` | TTL cache, mặc định 24 giờ. |
| `CACHE_PATH` | `data/viettubelens.db` | Đường dẫn SQLite cache. |

> [!NOTE]
> Sentiment model có thể dùng CUDA. Toxicity model hiện vẫn dùng ONNX `CPUExecutionProvider`; cần đổi provider và cài `onnxruntime-gpu` để triển khai GPU hoàn chỉnh.

### Cài extension trên máy khác

Trong cùng mạng LAN, chạy backend bằng:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Nhập `http://<IP-MAY-BACKEND>:8000` vào **Cài đặt → Địa chỉ backend**. Cho phép TCP port `8000` trong firewall và chỉ dùng trên mạng tin cậy. Nếu hai máy khác mạng, hãy dùng HTTPS tunnel hoặc cloud; không mở thẳng FastAPI ra Internet khi chưa có authentication và rate limiting.

## API

OpenAPI tại `/openapi.json` là nguồn sự thật.

| Method | Endpoint | Mục đích |
|---|---|---|
| `GET` | `/health` | Model, device, demo mode và backend status. |
| `POST` | `/api/v1/analysis/batch` | Tạo/phục hồi batch tối đa sáu video. |
| `POST` | `/api/v1/analysis/status` | Poll tối đa 12 kết quả trong một request. |
| `GET` | `/api/v1/analysis/{video_id}` | Lấy kết quả của một video. |
| `DELETE` | `/api/v1/cache` | Xóa cache backend. |

```http
POST /api/v1/analysis/batch
Content-Type: application/json

{
  "video_ids": ["dQw4w9WgXcQ", "aqz-KE-bpKQ"],
  "max_comments": 30,
  "refresh": false
}
```

<details>
<summary><strong>Ví dụ response rút gọn</strong></summary>

```json
{
  "video_id": "dQw4w9WgXcQ",
  "status": "ready",
  "sample_size": 30,
  "relevant_count": 24,
  "sentiment_distribution": { "positive": 0.57, "neutral": 0.23, "negative": 0.20 },
  "toxicity_rate": 0.08,
  "overall_reaction": "positive",
  "confidence_score": 0.79,
  "confidence_tier": "high",
  "abstained": false,
  "opinion_pattern": "consensus",
  "polarization_score": 0.21,
  "cache_hit": false,
  "model_version": "visobert-social-sentiment+visobert-toxicity-adaptive-v3",
  "source": "youtube"
}
```

</details>

## Cấu trúc repository

```text
viettubelens/
├── apps/extension/
│   ├── public/          # Manifest V3
│   ├── scripts/         # Icon và build verification
│   └── src/
│       ├── background/  # Service worker, cache, API bridge
│       ├── content/     # YouTube observers, badge, popover
│       ├── popup/       # Dashboard và cài đặt
│       ├── shared/      # Types, API client, settings
│       └── showcase/    # UI showcase
├── backend/
│   ├── app/             # API, collector, queue, model, cache
│   └── tests/
├── docs/                # Contract và annotation guide
└── ml/                  # Multi-task training, calibration và ONNX export
```

Thư mục ML còn có collector đã ẩn danh, truy vấn thu thập có thể tái tạo,
pseudo-label kèm provenance/confidence, dedup và giao diện kiểm duyệt thủ công.
Comment text lấy từ YouTube được giữ ngoài Git; [`ml/datasets`](ml/datasets)
chỉ lưu manifest, nguồn dữ liệu, giấy phép và hướng dẫn gán nhãn.

## Kiểm thử & chất lượng

```bash
# Extension
npm test
npm run typecheck
npm run build

# Backend
cd backend
python -m pytest
python -m ruff check .
python -m mypy app
```

Trạng thái hiện tại: **4 Vitest + 10 backend pytest + 16 ML pytest passing**,
TypeScript strict, Ruff, mypy strict và production build đều đạt.

## Hiệu năng

- Model warm-up không khóa startup API.
- Session cache 15 phút và backend cache 24 giờ.
- Dedupe tác vụ theo `video_id` và polling theo batch.
- Micro-batch tối đa ba video với cửa sổ gom 75 ms.
- Model batch size 16 comment.
- Phân tích 16 comment trước, chỉ mở rộng lên 30 khi cần.

Hiệu năng phụ thuộc CPU/GPU, YouTube API, cache và số comment; không nên dùng một con số latency cố định làm cam kết cho mọi máy.

## Quyền riêng tư & bảo mật

- Extension chỉ gửi YouTube video ID đã validate đến backend đã cấu hình.
- YouTube API key không được đóng gói trong extension.
- Evidence đến từ bình luận công khai.
- `.env`, SQLite cache, virtual environment và model cache bị loại khỏi Git.
- Demo output luôn được đánh dấu `source=demo`.
- Extension không tải JavaScript hoặc font từ CDN.

> [!WARNING]
> Endpoint hiện phù hợp cho local/demo. Trước khi public production, cần authentication, rate limiting, CORS chặt hơn, persistent datastore và bảo vệ endpoint xóa cache.

## Cách diễn giải & giới hạn

| Trường | Nên hiểu là |
|---|---|
| `sentiment_distribution` | Phân bố trong các comment phù hợp đã được lấy mẫu. |
| `toxicity_rate` | Tỷ lệ comment trong mẫu vượt ngưỡng toxicity. |
| `confidence_score` | Mức chắc chắn tổng hợp từ độ tách lớp và cỡ mẫu hữu dụng. |
| `polarization_score` | Mức đồng thời tồn tại của phản ứng tích cực và tiêu cực. |
| `evidence` | Bình luận đại diện để người dùng kiểm chứng. |
| `insufficient_data` | Phân tích thành công nhưng chủ động không kết luận. |

- Chỉ lấy top-level comment theo relevance của YouTube API.
- Mẫu mặc định tối đa 30 comment, không đại diện toàn bộ người xem.
- Sarcasm, tiếng lóng mới và code-switching có thể gây sai lệch.
- Like count chỉ là tín hiệu trọng số nhẹ, không phải nhãn đúng/sai.
- Không dùng dislike vì YouTube Data API không công khai số này cho video của kênh khác.

## Khắc phục lỗi

<details>
<summary><strong>Không thấy badge trên YouTube</strong></summary>

Kiểm tra extension và backend đang bật; reload extension rồi refresh YouTube. Livestream được chủ động bỏ qua. Popup sẽ hiển thị số card phát hiện, card trong viewport và badge đã mount. Sau khi reload extension, luôn refresh tab YouTube để tránh `Extension context invalidated`.

</details>

<details>
<summary><strong>Backend vẫn báo demo mode</strong></summary>

Đặt `YOUTUBE_API_KEY=...` và `DEMO_MODE=false` trong `backend/.env`, sau đó khởi động lại backend.

</details>

<details>
<summary><strong>Lần phân tích đầu rất lâu</strong></summary>

Đây thường là thời gian tải checkpoint và warm-up. Chờ `/health` trả `model_status=ready`; các lượt sau nhanh hơn nhờ model resident và cache-first.

</details>

<details>
<summary><strong>Máy khác không kết nối được backend</strong></summary>

Không dùng `127.0.0.1` trên máy thứ hai. Chạy backend với `--host 0.0.0.0`, dùng IP LAN của máy backend và kiểm tra firewall. Với mạng khác nhau, dùng endpoint HTTPS.

</details>

## Roadmap

- [x] Signal Prism design system và responsive badge/popover.
- [x] Viewport scheduler tối đa 12 video.
- [x] Cache-first batch API và adaptive inference.
- [x] Sentiment, toxicity, evidence, confidence và abstention.
- [x] Opinion pattern, polarization và minority evidence.
- [x] Reproducible multi-task training/calibration/export pipeline.
- [ ] OpenAPI-generated TypeScript client.
- [ ] Redis/PostgreSQL cache cho triển khai nhiều instance.
- [ ] ONNX CUDA provider và benchmark GPU.
- [ ] Visual regression light/dark và zoom 100%/125%.
- [ ] Calibrated multi-task ViSoBERT và learned hierarchical aggregator.
- [ ] Chrome Web Store package và privacy policy.

## Đóng góp

1. Fork repository và tạo branch theo phạm vi thay đổi.
2. Giữ API schema tương thích hoặc cập nhật đồng thời Python/TypeScript types.
3. Chạy đầy đủ test, typecheck, lint và build.
4. Không commit API key, `.env`, model weights hoặc dữ liệu bình luận.
5. Mở pull request với mô tả hành vi trước/sau và ảnh nếu thay đổi UI.

Xem thêm [`docs/api-contract.md`](docs/api-contract.md) và [`docs/annotation-guide.md`](docs/annotation-guide.md).

## License

Repository chưa công bố giấy phép mã nguồn mở. Mọi quyền được bảo lưu cho đến khi chủ sở hữu thêm tệp `LICENSE`.

---

<div align="center">

**VietTubeLens · Signal Prism**

*Phản ứng có ngữ cảnh. Bằng chứng có thể kiểm chứng. Kết luận biết giới hạn.*

</div>
