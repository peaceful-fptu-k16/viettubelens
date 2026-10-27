# VietTubeLens Web Slides

Web presentation 18 slide cho buổi bảo vệ đồ án VietTubeLens.

## Trải nghiệm trình chiếu

- Chuyển cảnh hai lớp với prism sweep, không nháy trắng giữa slide.
- Choreography riêng cho title, diagram, chart, table và KPI count-up.
- Speaker notes, timer và cửa sổ presenter đồng bộ qua `BroadcastChannel`.
- Overview 18 thumbnail, URL deep-link theo số slide và prefetch slide kế tiếp.
- Fullscreen tự ẩn chrome, laser pointer, swipe trên màn hình cảm ứng.
- Respect `prefers-reduced-motion`; có thể bật tắt ngay trong toolbar.
- Toàn bộ font và asset chạy offline, không dùng CDN hoặc analytics.

## Chạy local

Sau khi clone repository:

```powershell
cd viettubelens/slide/viettubelens.slides
py -m http.server 4173
```

Mở `http://127.0.0.1:4173/`.

Nếu máy dùng lệnh `python` thay cho `py`:

```powershell
python -m http.server 4173
```

Không mở trực tiếp `index.html` bằng `file://`, vì viewer cần HTTP để tải manifest và nội dung từng slide.

## Phím tắt

- `←` / `→`: slide trước hoặc tiếp theo
- `Home` / `End`: slide đầu hoặc cuối
- `O`: tổng quan thumbnail
- `N`: speaker notes
- `P`: cửa sổ presenter đồng bộ
- `F`: toàn màn hình
- `L`: laser pointer
- `M`: reduced motion
- `R`: phát lại animation của slide hiện tại
- `?`: trợ giúp

Không cần Internet khi trình chiếu. Font, hình ảnh và toàn bộ slide được đóng gói cục bộ.
