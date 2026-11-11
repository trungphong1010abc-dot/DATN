# Test nhanh module node

Node **Blue Pill STM32F103C8 + MAX13487E** → **USB–RS485 CH340** → laptop hiển thị số liệu và lưu CSV mở bằng Excel.

Mỗi trường hợp tạo một file riêng, mặc định 20 dòng, một báo cáo mỗi giây. Số liệu cũ đã được thay bằng bài thử này; chương trình không sinh số liệu mô phỏng.

## Nối dây

| Blue Pill | Khối analog / module MAX13487E |
|---|---|
| PA0 | ADC_CURRENT |
| PA1 | ADC_LIGHT sau hai tầng RC cố định |
| PA9/TX | RXD (DI) |
| PA10/RX | Để hở; node chỉ phát trong bài thử này |
| PB0 | Để hở; module tự chuyển chiều |
| GND | GND module và GND nguồn |
| Nguồn 5 V DC | VCC module; kiểm tra nguồn tại IC trong dải 4,75–5,25 V |

TXD/RO module MAX13487E để hở trong bài thử node chỉ phát. Không nối chân 3V3 vào VCC module. [Datasheet MAX13487E](https://www.analog.com/media/en/technical-documentation/data-sheets/max13487e-max13488e.pdf).

| Module MAX13487E node | USB–RS485 CH340 |
|---|---|
| A | A |
| B | B |

Adapter hiện có hai cọc A/B: chỉ nối hai dây A/B. GND module nối GND Blue Pill và GND nguồn cấp node. Node nhận adapter nguồn 5 V riêng; USB–RS485 cắm vào laptop.

## Nạp chương trình

1. Node: mở thư mục này bằng PlatformIO trong VS Code; cắm ST-Link, chọn `bluepill_f103c8`, Upload. Hoặc chạy `pio run -e bluepill_f103c8 -t upload`.
2. ESP32 riêng tạo chớp LED tiếp tục dùng code GPIO23: HIGH 10 ms, LOW 190 ms; LED đỏ mắc nối tiếp 330 Ω.

## Chuẩn bị một lần trước phiên

- Mạch dòng giữ burden 150 Ω và lọc 1 kΩ/100 nF. CT tỷ số **1000:1**, một lượt sơ cấp.
- Mạch quang giữ hồi tiếp 10 kΩ/100 pF và hai tầng RC cố định 1 kΩ/10 nF.
- **Tắt LED tạo chớp khi khởi động/reset node trong ít nhất 2 giây**. Node đo nền quang trong khoảng giây đầu; sau đó giữ nguyên ánh sáng phòng, vị trí LED và cảm biến. Đo nền lại bằng reset node nếu ánh sáng phòng thay đổi.
- Node lấy mẫu từng kênh **2.000 mẫu/giây** bằng timer, tương ứng khoảng 20 mẫu trong xung 10 ms; gửi một báo cáo/giây. Nhịp này là cấu hình thử module, không phải thông số chốt thuật toán cuối cùng.
- `include/test_logic.h`: `ADC_REFERENCE_V=3.3` là giá trị khởi đầu, chỉnh theo 3V3 thực đo. `CURRENT_GAIN=1.0` là hệ số chưa hiệu chỉnh; không có hiệu chuẩn tự động hay cam kết chính xác 100%.
- Ngưỡng quang khởi đầu: cao hơn nền **50 mV** để bật, xuống dưới nền + **25 mV** để kết thúc xung. Chỉ đếm xung dài 1–100 ms, cách nhau ít nhất 50 ms. Đây là tham số thử; nếu chưa bắt được LED, kiểm điện áp và khoảng cách rồi chỉnh hai ngưỡng trong `test_logic.h`, nạp lại node.

## Chạy bốn trường hợp

Nguồn tải cách ly 12 VAC, điện trở 50 Ω–25 W. Dây xuyên CT đặt trước điểm chia nhánh; dây về đi ngoài CT. Tắt nguồn tải khi thay đổi nhánh; giữ burden nối kín thứ cấp khi có dòng sơ cấp.

| Chọn | Trường hợp | Tải | LED | Cảnh báo mong đợi |
|---|---|---|---|---|
| 1 | Bình thường | 1 trở, dự kiến 0,24 A | Tắt | Không |
| 2 | Chỉ dòng | 2 trở song song, dự kiến 0,48 A | Tắt | Không |
| 3 | Chỉ quang | 1 trở | Chớp | Không |
| 4 | Kết hợp | 2 trở song song | Chớp | Có |

Cảnh báo thử dùng ngưỡng dòng **0,40 A**, kết hợp chớp trong **200 ms**. Node kiểm RMS theo khối 20 ms, ghi nhận sự kiện liên tục, chốt cờ nếu có cảnh báo trong giây báo cáo. Hai hướng kết hợp đều xét thời gian: dòng vượt trước chớp hoặc chớp trước dòng. Đây là logic thử bằng tải và LED, chưa chứng minh nhận diện hồ quang thật.

Trong Terminal tại thư mục dự án:

```powershell
python -m pip install -r requirements.txt
python tools/capture_module.py
```

Nếu `python` của máy không có pip, dùng Python đã cài pyserial (ví dụ môi trường `.venv` có sẵn). Chọn 1/2/3/4, chọn **COM của USB–RS485 CH340**, đặt đúng tải/LED rồi nhấn Enter. Đóng Arduino Serial Monitor/PlatformIO Monitor trước khi chạy vì chúng không dùng chung COM với Python.

Hoặc chạy chỉ định (thay COM3 bằng COM USB–RS485 thực):

```powershell
python tools/capture_module.py 1 --port COM3
python tools/capture_module.py 2 --port COM3
python tools/capture_module.py 3 --port COM3
python tools/capture_module.py 4 --port COM3
```

Mỗi lệnh tạo một file có tên trường hợp và thời gian trong `data/module/`, không ghi đè. Chương trình bỏ báo cáo đầu sau Enter để tránh lấy khoảng đo từ trước khi bắt đầu. `Ctrl+C` dừng và giữ phần đã thu; chỉ phiên báo **HOÀN TẤT** mới đủ 20 dòng. Không đổi tải hoặc LED giữa một phiên. Node không cần reset giữa các trường hợp nếu mức nền giữ nguyên.

Python `.venv` có sẵn trong dự án đã có pyserial 3.5. Có thể chạy trực tiếp, không cần cài lại:

```powershell
.\.venv\bin\python.exe tools\capture_module.py
```

Các file `tools/capture_bpw34.py`, `tools/analyze_bpw34.py` và `docs/bpw34_test.md` là công cụ/tài liệu cũ còn giữ, không dùng cho bài thử mới. Số liệu BPW34 cũ đã xóa theo yêu cầu; kết quả mới chỉ nằm trong `data/module/`.
## Xem trực tiếp và lưu CSV

Để chỉ xem gói dữ liệu, liệt kê cổng rồi mở COM của USB–RS485 (thay COM3 bằng cổng thực):

```powershell
& "C:\Users\Lenovo\.platformio\penv\Scripts\python.exe" -m serial.tools.list_ports
& "C:\Users\Lenovo\.platformio\penv\Scripts\python.exe" -m serial.tools.miniterm COM3 115200
```

Node chạy `bluepill_f103c8` gửi gói `DATA,...*XX` mỗi giây. Thoát miniterm bằng Ctrl+]. Để vừa hiển thị số liệu dễ đọc vừa lưu CSV, chạy `capture_module.py` ở trên; đóng miniterm trước vì hai chương trình không dùng chung COM.

## Sáu cột CSV

| Cột | Nội dung |
|---|---|
| Thời gian | Ngày giờ laptop nhận, có mili giây; không phải mốc đo độ trễ node. |
| Trường hợp thử | Một tên cố định trong toàn file. |
| Dòng RMS (A) | RMS thành phần AC trong 1 giây, loại DC/BIAS bằng phương sai mẫu; quy đổi CT 1000:1 và burden 150 Ω. |
| Điện áp quang đỉnh (V) | Điện áp PA1 lớn nhất trong giây, **bao gồm BIAS**. Không phải lux. |
| Số chớp | Số xung hợp lệ kết thúc trong giây đó, không cộng dồn. |
| Cảnh báo hồ quang | Có ít nhất một lần logic cảnh báo thử đúng trong giây: Có/Không. |

CSV UTF-8 có BOM, phân cách **dấu chấm phẩy**, số thập phân **dấu phẩy**, thuận tiện Excel thiết lập Việt Nam. Nếu Excel không tự chia cột: Data → From Text/CSV → UTF-8 → delimiter `;`, chọn locale Vietnamese khi chuyển số.

Dòng phải đối chiếu đồng hồ RMS thực; 0,24/0,48 A chỉ là lý thuyết tại đúng 12 VAC. Điện áp đỉnh quang phải tăng rõ khi LED chớp, không bắt buộc đạt 2,10 V. Đếm hướng tới 5 chớp/giây; xem tổng cả phiên vì ranh giới giây và dao động chu kỳ có thể làm từng dòng lệch. Không có chớp thì mong đợi 0.

Node gửi checksum và số thứ tự nội bộ. Python dừng khi sai khung, mất/trùng bản tin, node reset, ADC chạm biên, lệch nhịp lấy mẫu hoặc tràn hàng đợi; không chèn số 0 và không lặp số cũ để lấp chỗ trống. File phiên dừng sớm chỉ giữ phần đã thu; đo lại để có phiên đủ.

## Giới hạn xác nhận

Build và kiểm thử bằng dữ liệu tổng hợp chỉ kiểm logic/phần mềm. Chưa có kết quả đo thực của bộ mới. Nạp chương trình đo lên node và chạy đủ bốn trường hợp qua USB–RS485 để kiểm phần cứng, nguồn MAX13487E, độ ổn định lấy mẫu và ngưỡng quang trước khi hàn PCB.
