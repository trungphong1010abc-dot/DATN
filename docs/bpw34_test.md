# Hướng dẫn test cảm biến quang BPW34

## Trạng thái hiện tại

Đã thu đủ CHE, PHONG và DEN sau khi sửa phần cứng, mỗi điều kiện 100 mẫu. Các bước bên dưới được giữ để làm lại phép đo khi cần.

| Điều kiện | File gốc | Trung bình L | Min–max | Đỉnh–đỉnh | Độ lệch chuẩn mẫu |
|---|---|---:|---|---:|---:|
| CHE | `che_20261010_162131.csv` | 2066.100 | 1696–2624 | 928 | 145.009 |
| PHONG | `phong_20261010_162632.csv` | 2115.160 | 2048–2159 | 111 | 33.590 |
| DEN | `den_20261010_163145.csv` | 2394.010 | 2288–2559 | 271 | 81.199 |

Đơn vị số liệu L là count ADC. DEN dùng đèn mức 1, cách 20 cm. Cả ba phiên không có dòng lỗi, bất thường SEQ hoặc mẫu L chạm 0/4095.

DEN cao hơn PHONG trung bình 278.850 count và hai khoảng không chồng lấn. DEN cao hơn CHE 327.910 count nhưng vẫn chồng lấn khoảng CHE, do CHE dao động lớn. PHONG cao hơn CHE 49.060 count và cũng chồng lấn. Nhánh quang có phản ứng với đèn so với nền phòng, nhưng chưa xác nhận mức nền che ổn định; nguyên nhân dao động cần kiểm tra riêng.

Kết quả đầy đủ, công thức và giải thích nằm trong `data/bpw34/analysis_20261008_220215_report.md`; bảng tổng hợp là `analysis_20261008_220215_summary.csv`. Tên hai file được giữ nguyên dù dữ liệu đo ngày 10/10/2026.

## Trước mỗi lần đo

1. Cấp nguồn cho Blue Pill.
2. Cắm USB–RS485 vào laptop.
3. Không mở PlatformIO Serial Monitor.
4. Nếu Serial Monitor đang chạy, bấm vào Terminal đó và nhấn `Ctrl+C`.
5. Trong VS Code, chọn **Terminal → New Terminal**.

Script Python sẽ thay Serial Monitor để nhận và lưu dữ liệu. Không mở hai công cụ cùng lúc vì chúng không thể dùng chung một cổng COM.

## Cách chọn COM

Sau khi chạy lệnh đo, chương trình sẽ hiện danh sách tương tự:

```text
Cac cong serial hien co:
  1. COM6 - USB-SERIAL CH340
  2. COM8 - ...
Nhap so thu tu hoac ten cong:
```

Nhập số đứng trước USB–RS485 hoặc nhập trực tiếp tên cổng, ví dụ `COM6`, rồi nhấn Enter.

Không mặc định lần sau vẫn là COM6. Nếu không biết cổng nào:

1. Rút USB–RS485 và xem COM nào biến mất.
2. Cắm lại và xem COM nào xuất hiện.
3. Chọn COM đó.

## Đo CHE (đã thu)

1. Che kín hoàn toàn mặt nhận sáng của BPW34 bằng vật không xuyên sáng.
2. Không chạm hoặc làm lệch chân và dây cảm biến.
3. Chờ khoảng 5 giây.
4. Chạy:

```powershell
.\.venv\bin\python.exe tools\capture_bpw34.py CHE
```

5. Chọn COM của USB–RS485 và giữ nguyên vật che đến khi đủ `100/100`.
6. Hoàn thành khi công cụ báo `DU 100 MAU`.

## Đo PHONG (đã thu)

1. Bỏ vật đang che BPW34.
2. Giữ nguyên vị trí và hướng của cảm biến.
3. Không chiếu đèn pin vào cảm biến.
4. Tránh đưa tay hoặc đi qua trước cảm biến.
5. Chờ khoảng 5 giây để số đo ổn định.
6. Chạy lệnh:

```powershell
.\.venv\bin\python.exe tools\capture_bpw34.py PHONG
```

7. Chọn COM của USB–RS485.
8. Không thay đổi ánh sáng trong khoảng 50 giây.
9. Chờ đến khi Terminal hiện:

```text
Tien do: 25/100
Tien do: 50/100
Tien do: 75/100
Tien do: 100/100
Ket qua: DU 100 MAU
```

Khi thấy `DU 100 MAU`, phép đo PHONG đã hoàn thành.

## Đo DEN (đã thu)

1. Đặt đèn pin cách BPW34 khoảng 20 cm.
2. Giữ cố định khoảng cách, hướng chiếu và mức sáng.
3. Chờ khoảng 5 giây.
4. Chạy:

```powershell
.\.venv\bin\python.exe tools\capture_bpw34.py DEN
```

5. Chọn COM của USB–RS485.
6. Khi chương trình hỏi, nhập khoảng cách thực tế bằng cm.
7. Nhập chế độ đèn, ví dụ `muc 1`.
8. Giữ nguyên đèn khoảng 50 giây cho đến khi đủ `100/100`.

Nếu quan sát thấy `L=4095`, tín hiệu đã chạm giới hạn ADC. Không xóa file vừa đo. Đưa đèn ra xa hơn và chạy lại phép đo DEN để tạo một file mới.

## Phân tích sau khi đủ ba điều kiện

Khi đã có đủ CHE, PHONG và DEN, chạy:

```powershell
.\.venv\bin\python.exe tools\analyze_bpw34.py
```

Chương trình sẽ tự chọn file mới nhất của từng điều kiện và tạo:

- Một file CSV tổng hợp.
- Một báo cáo Markdown dễ đọc.

Các kết quả được tính gồm:

- L trung bình, nhỏ nhất và lớn nhất.
- Dao động đỉnh–đỉnh.
- Độ lệch chuẩn mẫu.
- Số mẫu bằng 0 hoặc 4095.
- Bất thường SEQ.
- Chênh lệch giữa CHE, PHONG và DEN.
- Kiểm tra các khoảng min–max có chồng lấn hay không.

## Khi gặp lỗi

### Không mở được COM

Đóng PlatformIO Serial Monitor và các phần mềm terminal khác, sau đó chạy lại lệnh.

### Không có dữ liệu trong 10 giây

Kiểm tra nguồn Blue Pill, USB–RS485 và chọn lại đúng COM.

### Muốn dừng giữa chừng

Nhấn `Ctrl+C`. Dữ liệu đã thu vẫn được lưu, nhưng chương trình sẽ ghi rõ là chưa đủ 100 mẫu.

### Có nhiều file cùng điều kiện

Không cần xóa file cũ. Tên file chứa thời gian đo nên dữ liệu cũ không bị ghi đè. Công cụ phân tích mặc định sử dụng file mới nhất của mỗi điều kiện.
