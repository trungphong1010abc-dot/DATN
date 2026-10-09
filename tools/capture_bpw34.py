"""Capture BPW34 ADC readings from the existing STM32 RS485 firmware."""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import time
from datetime import datetime
from pathlib import Path

import serial
from serial.tools import list_ports


LINE_PATTERN = re.compile(r"^SEQ=(\d+),I=(\d+),L=(\d+)$")
PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data" / "bpw34"


def parse_log_line(text: str) -> tuple[int, int, int] | None:
    match = LINE_PATTERN.fullmatch(text.strip())
    if not match:
        return None
    seq, current, light = map(int, match.groups())
    if not (0 <= current <= 4095 and 0 <= light <= 4095):
        return None
    return seq, current, light


def choose_port(requested: str | None) -> str:
    if requested:
        return requested

    ports = list(list_ports.comports())
    print("Cac cong serial hien co:")
    if ports:
        for index, port in enumerate(ports, start=1):
            print(f"  {index}. {port.device} - {port.description}")
    else:
        print("  Khong tim thay cong nao tu dong.")

    choice = input("Nhap so thu tu trong danh sach (vi du 3) hoac ten cong (vi du COM6): ").strip()
    if choice.isdigit():
        number = int(choice)
        if 1 <= number <= len(ports):
            return ports[number - 1].device
        com_name = f"COM{number}"
        if any(port.device.upper() == com_name for port in ports):
            return com_name
    if choice:
        return choice
    raise ValueError("Chua chon cong serial.")


def unique_output_path(condition: str) -> Path:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base = DATA_DIR / f"{condition.lower()}_{stamp}"
    path = base.with_suffix(".csv")
    counter = 1
    while path.exists():
        path = DATA_DIR / f"{base.name}_{counter}.csv"
        counter += 1
    return path


def classify_sequence(previous: int | None, current: int) -> str | None:
    if previous is None or current == previous + 1:
        return None
    if current == previous:
        return "duplicate"
    if current < previous:
        return "decrease"
    return "jump"


def main() -> int:
    parser = argparse.ArgumentParser(description="Thu log BPW34 tu STM32 qua RS485.")
    parser.add_argument("condition", choices=("CHE", "PHONG", "DEN"), type=str.upper)
    parser.add_argument("--port", help="Cong COM; bo trong de chon tu danh sach.")
    parser.add_argument("--samples", type=int, default=100)
    parser.add_argument("--idle-timeout", type=float, default=10.0,
                        help="Dung neu khong nhan dong nao trong N giay.")
    parser.add_argument("--max-seconds", type=float, default=120.0,
                        help="Gioi han tong thoi gian cua mot phien thu.")
    parser.add_argument("--distance-cm", type=float, help="Khoang cach den cho dieu kien DEN.")
    parser.add_argument("--light-mode", help="Che do den pin cho dieu kien DEN.")
    args = parser.parse_args()

    if args.samples <= 0:
        parser.error("--samples phai lon hon 0")

    try:
        port = choose_port(args.port)
    except ValueError as exc:
        print(f"Loi: {exc}", file=sys.stderr)
        return 2

    if args.condition == "DEN":
        if args.distance_cm is None:
            raw = input("Khoang cach den thuc te (cm, Enter neu khong ghi): ").strip()
            if raw:
                try:
                    args.distance_cm = float(raw)
                except ValueError:
                    print("Khoang cach khong hop le.", file=sys.stderr)
                    return 2
        if not args.light_mode:
            args.light_mode = input("Che do den (vi du: muc 1, Enter neu khong ghi): ").strip() or None

    output_path = unique_output_path(args.condition)
    metadata_path = output_path.with_suffix(".json")
    invalid_lines = 0
    seq_counts = {"jump": 0, "duplicate": 0, "decrease": 0}
    valid_count = 0
    previous_seq: int | None = None
    interrupted = False
    started = datetime.now().astimezone()

    try:
        connection = serial.Serial(
            port=port,
            baudrate=9600,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=1.0,
        )
    except serial.SerialException as exc:
        print(f"Khong mo duoc {port}: {exc}", file=sys.stderr)
        print("Hay dong PlatformIO Serial Monitor va cac phan mem dang giu cong.", file=sys.stderr)
        return 1

    print(f"Dang thu {args.condition} tu {port} tai 9600 8-N-1.")
    print(f"Du lieu se luu vao: {output_path}")
    print("Nhan Ctrl+C de dung; phan da thu van duoc luu.")
    last_received = time.monotonic()
    deadline = time.monotonic() + args.max_seconds

    try:
        with output_path.open("x", newline="", encoding="utf-8") as csv_file:
            writer = csv.DictWriter(
                csv_file,
                fieldnames=("condition", "sample_index", "timestamp_pc", "seq", "I", "L"),
            )
            writer.writeheader()

            while valid_count < args.samples:
                if time.monotonic() >= deadline:
                    print(f"Het gioi han {args.max_seconds:g} giay.")
                    break

                raw = connection.readline()
                if not raw:
                    if time.monotonic() - last_received >= args.idle_timeout:
                        print(f"Khong nhan du lieu trong {args.idle_timeout:g} giay.")
                        break
                    continue

                last_received = time.monotonic()
                text = raw.decode("ascii", errors="replace").strip()
                parsed = parse_log_line(text)
                if parsed is None:
                    invalid_lines += 1
                    continue

                seq, current, light = parsed
                anomaly = classify_sequence(previous_seq, seq)
                if anomaly:
                    seq_counts[anomaly] += 1
                    print(f"Canh bao SEQ ({anomaly}): {previous_seq} -> {seq}")
                previous_seq = seq

                valid_count += 1
                writer.writerow(
                    {
                        "condition": args.condition,
                        "sample_index": valid_count,
                        "timestamp_pc": datetime.now().astimezone().isoformat(timespec="milliseconds"),
                        "seq": seq,
                        "I": current,
                        "L": light,
                    }
                )
                csv_file.flush()
                if valid_count % 25 == 0 or valid_count == args.samples:
                    print(f"Tien do: {valid_count}/{args.samples}")
    except KeyboardInterrupt:
        interrupted = True
        print("\nDa nhan Ctrl+C; dang luu phan du lieu da thu.")
    finally:
        connection.close()

    finished = datetime.now().astimezone()
    metadata = {
        "condition": args.condition,
        "port": port,
        "baudrate": 9600,
        "requested_samples": args.samples,
        "valid_samples": valid_count,
        "complete": valid_count == args.samples,
        "valid_for_analysis": True,
        "interrupted": interrupted,
        "invalid_lines": invalid_lines,
        "sequence_anomalies": seq_counts,
        "started_pc": started.isoformat(timespec="seconds"),
        "finished_pc": finished.isoformat(timespec="seconds"),
        "elapsed_seconds": round((finished - started).total_seconds(), 3),
        "distance_cm": args.distance_cm,
        "light_mode": args.light_mode,
        "timestamp_note": "timestamp_pc la thoi gian laptop nhan dong, khong phai thoi diem STM32 lay mau.",
    }
    metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")

    status = "DU 100 MAU" if valid_count == args.samples else "CHUA DU MAU"
    print(f"Ket qua: {status} ({valid_count}/{args.samples})")
    print(f"Dong sai dinh dang/pham vi: {invalid_lines}")
    print(f"Bat thuong SEQ: {seq_counts}")
    print(f"CSV: {output_path}")
    print(f"Thong tin phien: {metadata_path}")
    return 0 if valid_count == args.samples else 1


if __name__ == "__main__":
    raise SystemExit(main())
