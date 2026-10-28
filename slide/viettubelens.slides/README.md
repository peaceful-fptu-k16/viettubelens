# VietTubeLens Web Slides

Web presentation 18 slide cho buổi bảo vệ đồ án VietTubeLens.

## Trải nghiệm trình chiếu

- Chuyển cảnh hai lớp với prism sweep, không nháy trắng giữa slide.
- Choreography riêng cho title, diagram, chart và table.
- Màn điều khiển có speaker notes, timer, slide hiện tại, preview slide kế tiếp và nút điều hướng.
- Màn trình chiếu sạch tự ẩn thanh công cụ và đồng bộ qua `BroadcastChannel`.
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

## Trình chiếu hai màn hình

1. Mở `http://127.0.0.1:4173/` trên máy thuyết trình.
2. Nhấn `P` hoặc biểu tượng màn hình để mở **Màn điều khiển**.
3. Trong Màn điều khiển, chọn **Mở màn trình chiếu**.
4. Kéo cửa sổ trình chiếu sang màn hình thứ hai và bật toàn màn hình của trình duyệt.
5. Điều hướng bằng phím mũi tên hoặc các nút trong Màn điều khiển. Hai cửa sổ tự đồng bộ.

Có thể mở trực tiếp:

- Màn điều khiển: `http://127.0.0.1:4173/?presenter=1#/1`
- Màn trình chiếu: `http://127.0.0.1:4173/?audience=1#/1`

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
