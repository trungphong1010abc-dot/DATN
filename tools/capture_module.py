"""Capture real node reports through the ESP32 gateway into six-column CSV."""
from __future__ import annotations
import argparse
import csv
from datetime import datetime
from pathlib import Path
import time

ROOT = Path(__file__).resolve().parents[1]
CASES = {
    "1": ("01_binh_thuong", "Bình thường", "1 trở 50 Ω, LED tắt"),
    "2": ("02_chi_dong", "Chỉ dòng", "2 trở song song, LED tắt"),
    "3": ("03_chi_quang", "Chỉ quang", "1 trở 50 Ω, LED chớp"),
    "4": ("04_ket_hop", "Kết hợp", "2 trở song song, LED chớp"),
}
HEADERS = ["Thời gian", "Trường hợp thử", "Dòng RMS (A)",
           "Điện áp quang đỉnh (V)", "Số chớp", "Cảnh báo hồ quang"]


def parse_frame(text: str) -> tuple[int, int, int, int, int, int, int]:
    payload, sep, check = text.strip().partition("*")
    if not sep or len(check) != 2:
        raise ValueError("Sai khung bản tin")
    checksum = 0
    for byte in payload.encode("ascii"):
        checksum ^= byte
    if checksum != int(check, 16):
        raise ValueError("Sai checksum")
    fields = payload.split(",")
    if len(fields) != 8 or fields[0] != "DATA":
        raise ValueError("Sai số trường")
    values = tuple(int(v) for v in fields[1:])
    seq, ms, ma, mv, flashes, alarm, flags = values
    if any(v < 0 for v in values) or not seq or mv > 3600 or alarm not in (0, 1):
        raise ValueError("Giá trị ngoài phạm vi")
    return seq, ms, ma, mv, flashes, alarm, flags


def run() -> int:
    import serial
    from serial.tools import list_ports

    parser = argparse.ArgumentParser(description="Lưu test module: mỗi trường hợp một CSV, mỗi giây một dòng.")
    parser.add_argument("case", nargs="?", choices=tuple(CASES))
    parser.add_argument("--port")
    parser.add_argument("--seconds", type=int, default=20, help="Số báo cáo 1 giây cần thu (mặc định 20).")
    args = parser.parse_args()
    if args.seconds <= 0:
        parser.error("--seconds phải lớn hơn 0")
    for key, (_, label, condition) in CASES.items():
        print(f"{key}. {label}: {condition}")
    case = args.case or input("Chọn trường hợp 1/2/3/4: ").strip()
    if case not in CASES:
        print("Trường hợp không hợp lệ."); return 2
    if not args.port:
        for port in list_ports.comports():
            print(f"{port.device}: {port.description}")
        args.port = input("Nhập COM của GATEWAY (ví dụ COM3): ").strip()
    stem, label, condition = CASES[case]
    print(f"Chuẩn bị: {condition}. Đóng Serial Monitor trước khi mở cổng.")
    print("Node phải khởi động với LED TẮT trong lúc đo nền (~1 giây).")
    output_dir = ROOT / "data" / "module"
    connection = None
    output = None
    try:
        connection = serial.Serial(args.port, 115200, timeout=0.2)
        # Opening the gateway port can reset ESP32. Warm up before asking to start.
        time.sleep(2)
        input("Khi đã đặt đúng tải và trạng thái LED, nhấn Enter để ghi: ")
        connection.reset_input_buffer()
        # Skip one complete report so the saved interval starts after Enter.
        deadline = time.monotonic() + 10
        while True:
            text = connection.readline().decode("ascii", errors="replace").strip()
            try:
                warmup = parse_frame(text)
            except (ValueError, UnicodeError):
                if time.monotonic() >= deadline:
                    raise RuntimeError("Không có bản tin hợp lệ từ node trong 10 giây.")
                continue
            previous = warmup[:2]
            break
        output_dir.mkdir(parents=True, exist_ok=True)
        output = output_dir / f"{stem}_{datetime.now():%Y%m%d_%H%M%S_%f}.csv"
        saved = 0
        with output.open("x", newline="", encoding="utf-8-sig") as stream:
            # Semicolon delimiter fits Vietnamese Excel; decimal comma.
            writer = csv.writer(stream, delimiter=";")
            writer.writerow(HEADERS)
            stream.flush()
            deadline = time.monotonic() + 5
            while saved < args.seconds:
                text = connection.readline().decode("ascii", errors="replace").strip()
                if not text or text.startswith("#"):
                    if time.monotonic() >= deadline:
                        raise RuntimeError("Mất bản tin 5 giây; dừng, giữ nguyên số liệu đã thu.")
                    continue
                try:
                    seq, ms, ma, mv, flashes, alarm, flags = parse_frame(text)
                except (ValueError, UnicodeError) as exc:
                    raise RuntimeError(f"Bản tin lỗi: {exc}. Chạy lại phiên này.") from exc
                if seq != previous[0] + 1 or ms - previous[1] != 1000:
                    raise RuntimeError("Thiếu/trùng bản tin hoặc node reset; dừng phiên để tránh số liệu sai.")
                if flags:
                    raise RuntimeError(f"Node báo lỗi {flags}: 1=ADC chạm biên, 2=lệch nhịp lấy mẫu, 4=tràn hàng đợi. Chạy lại sau khi sửa.")
                previous = seq, ms
                deadline = time.monotonic() + 5
                row = [datetime.now().astimezone().isoformat(timespec="milliseconds"), label,
                       f"{ma / 1000:.3f}".replace(".", ","),
                       f"{mv / 1000:.3f}".replace(".", ","), flashes, "Có" if alarm else "Không"]
                writer.writerow(row); stream.flush()
                saved += 1
                print(f"{saved}/{args.seconds}: I={ma/1000:.3f} A | quang đỉnh={mv/1000:.3f} V | chớp={flashes} | cảnh báo={row[-1]}")
        print(f"HOÀN TẤT: {output}")
        return 0
    except (serial.SerialException, OSError, RuntimeError) as exc:
        print(f"DỪNG: {exc}")
        if output:
            print(f"Phiên CHƯA ĐỦ, file giữ phần đã thu: {output}")
        return 1
    except KeyboardInterrupt:
        print(f"Đã dừng; giữ phần đã thu: {output or '(chưa tạo file)'}")
        return 1
    finally:
        if connection is not None:
            connection.close()


if __name__ == "__main__":
    raise SystemExit(run())
