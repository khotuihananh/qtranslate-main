# LensTranslate for Windows

LensTranslate là ứng dụng Windows lấy cảm hứng từ giao diện và luồng thao tác của Google Lens. Ứng dụng tập trung vào việc nhận dạng chữ từ ảnh hoặc vùng màn hình, sau đó đưa văn bản vào bộ dịch để người dùng có thể đọc, sao chép hoặc nghe kết quả.

## Trải nghiệm chính

| Chức năng | Cách sử dụng |
|---|---|
| Dịch văn bản | Chọn tab `Văn bản`, nhập nội dung, chọn ngôn ngữ và bấm `Translate` |
| Chọn từ tự nhiên | Click đúp vào một từ trong ô nguồn để chọn đúng từ đó; kéo chuột vẫn chọn được cả đoạn |
| Hoán đổi ngôn ngữ | Bấm nút `⇄`; bản dịch hiện tại trở thành văn bản nguồn và ứng dụng tự dịch lại theo chiều ngược lại |
| OCR vùng màn hình | Nhấn `Ctrl+Shift+O` hoặc chọn `Hình ảnh > Chụp vùng màn hình`, sau đó kéo vùng cần nhận dạng |
| OCR từ ảnh | Bấm `Mở ảnh` hoặc `Chọn ảnh`, chọn file PNG/JPG/BMP/WEBP/TIFF |
| Dịch vùng chọn ở ứng dụng khác | Bôi đen văn bản rồi nhấn phím backtick `` ` `` |
| Sao chép/đọc kết quả | Dùng các nút biểu tượng ở cuối vùng văn bản |
| Chạy nền | Đóng cửa sổ chính; ứng dụng chuyển xuống system tray và vẫn nhận hotkey |
| Tùy chỉnh phím tắt | Mở menu `⋮ > Tùy chọn phím tắt...`, có thể gán một phím đơn không cần Ctrl/Alt/Shift hoặc tổ hợp phím rồi chọn `Áp dụng` |
| Cỡ chữ | Mở menu `⋮ > Cỡ chữ`, chọn từ 9 đến 30 px; lựa chọn được lưu cho lần chạy sau |
| Dark mode | Mở menu `⋮ > Dark mode`; lựa chọn được lưu cho lần chạy sau |
| Khởi động cùng Windows | Bật trong menu biểu tượng `⋮`; ứng dụng sẽ chạy ẩn, có biểu tượng tray và không mở cửa sổ sau khi đăng nhập |

Giao diện chính đã được rút gọn theo phong cách QTranslate: chỉ tập trung vào ô văn bản nguồn, thanh chọn ngôn ngữ, nút dịch và ô kết quả. Các tab `Tài liệu` và `Trang web` đã được loại bỏ. Phần tùy chọn nâng cao được ẩn trong nút menu biểu tượng `⋮` ở góc phải; cửa sổ có thể kéo giãn tự do và thu nhỏ đến khoảng 320×220.

## Phím tắt mặc định

| Hành động | Phím tắt mặc định |
|---|---|
| Dịch văn bản đã chọn | `` ` ``; có thể đổi thành một phím đơn bất kỳ, ví dụ `F2` hoặc `A` |
| OCR vùng màn hình | `Ctrl+Shift+O` |
| Hiện cửa sổ chính | `Ctrl+Q` |
| Dịch nội dung trong ô nguồn | `Ctrl+Enter` |
| Xóa nội dung nguồn | `Ctrl+L` |
| Sao chép bản dịch | `Ctrl+Shift+C` |
| Hủy chọn vùng OCR | `Esc` |

## Chạy bản Windows đã build

Nhấp đúp vào `LensTranslate.exe` hoặc `run_desktop_translator.bat`. Launcher sẽ ưu tiên bản `LensTranslate.exe` trong thư mục dự án. Nút `⋮` ở góc phải mở các tùy chọn phím tắt, API, cỡ chữ, dark mode và khởi động Windows. Trong menu `⋮ > Cỡ chữ`, có thể chọn kích thước từ 9 đến 30 px; lựa chọn áp dụng cho cả ô nguồn và ô kết quả, đồng thời được lưu lại. Khi bật khởi động cùng Windows, ứng dụng chạy ẩn và chỉ hiện biểu tượng trong system tray; khi đóng cửa sổ chính, ứng dụng cũng thu nhỏ vào tray thay vì thoát. Cửa sổ có thể kéo giãn tự do và thu nhỏ đến khoảng 320×220.

## OCR và cài đặt lần đầu

OCR mặc định sử dụng Tesseract cục bộ. Bản `LensTranslate.exe` đã đóng gói sẵn Tesseract cùng model English và Vietnamese, nên không cần cài Tesseract riêng khi chạy bản `.exe`. Ngoài ra có thể chọn `Gemini Vision API` trong `⋮ > Cài đặt API...`; Gemini Vision nhận dạng chữ và dịch ảnh trong một lần gọi. Gemini API cũng có thể dịch văn bản thường.
� dùng OCR.space: mở menu `⋮ > Cài đặt API...`, chọn `OCR.space API`, nhập API key, chọn OCR Engine 2 hoặc 3 rồi bấm `Áp dụng`. API key được lưu trong thư mục cấu hình người dùng và được che trong giao diện. Khi dùng OCR.space, ảnh sẽ được gửi qua Internet đến dịch vụ OCR; khi chọn Tesseract cục bộ, ảnh không rời khỏi máy.

Tài liệu API OCR.space có tại [ocr.space/ocrapi](https://ocr.space/ocrapi); với tiếng Việt nên chọn OCR Engine 2 và mã ngôn ngữ `vnm`.

Để dùng Gemini, mở `⋮ > Cài đặt API...`, chọn `Gemini Vision API`, nhập **Gemini API key** mới rồi bấm `Áp dụng`. Khi chọn ảnh hoặc quét vùng màn hình, ứng dụng gửi ảnh cùng yêu cầu OCR và dịch sang Gemini. Không đưa API key vào mã nguồn; nếu key bị lộ, hãy tạo key mới và vô hiệu hóa key cũ.

## Engine dịch

Nguồn dịch văn bản thường có thể chọn trong `⋮ > Cài đặt API...`: `MyMemory Translation API` tại `https://api.mymemory.translated.net/get` hoặc `Gemini API`. Khi chọn Gemini API, văn bản được gửi tới Gemini cùng ngôn ngữ nguồn và ngôn ngữ đích để dịch theo ngữ cảnh. Khi OCR provider là `Gemini Vision API`, ảnh được Gemini nhận dạng và dịch trực tiếp trong một lần gọi. Khi dùng Tesseract hoặc OCR.space, văn bản OCR sau đó được dịch bằng nguồn dịch văn bản đang chọn. Vì vậy kết quả có thể khác Google Translate.

## Tạo lại file `.exe`

Nếu mã nguồn được thay đổi, chạy `build_exe.bat`. Script dùng Python 3.13, cài Pillow, pytesseract, pystray và PyInstaller, sau đó tạo lại file một-file không hiện cửa sổ console:

```text
LensTranslate.exe
```

## Tệp trong thư mục

| Tệp | Mục đích |
|---|---|
| `desktop_translator.py` | Mã nguồn ứng dụng Windows |
| `LensTranslate.exe` | Bản chạy Windows đã build |
| `run_desktop_translator.bat` | Launcher ưu tiên mở file `.exe` |
| `settings.json` | Lưu ngôn ngữ, hotkey, provider OCR, API key, cỡ chữ và dark mode |
| `requirements.txt` | Dependency OCR, system tray và đóng gói |
| `install_ocr.bat` | Cài dependency Python |
| `build_exe.bat` | Tạo lại bản `.exe` |

Ứng dụng là bản độc lập lấy cảm hứng từ Google Lens và QTranslate, không sử dụng mã nguồn hoặc tài sản độc quyền của các sản phẩm đó.
