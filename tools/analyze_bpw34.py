"""Analyze real BPW34 CSV captures without modifying the source files."""

from __future__ import annotations

import argparse
import csv
import json
import statistics
from collections import Counter
from datetime import datetime
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data" / "bpw34"
CONDITIONS = ("CHE", "PHONG", "DEN")


def read_capture(path: Path) -> dict:
    rows = []
    with path.open(newline="", encoding="utf-8-sig") as csv_file:
        for row in csv.DictReader(csv_file):
            try:
                condition = row["condition"].upper()
                seq = int(row["seq"])
                current = int(row["I"])
                light = int(row["L"])
            except (KeyError, TypeError, ValueError) as exc:
                raise ValueError(f"Dong CSV khong hop le trong {path}: {row}") from exc
            if condition not in CONDITIONS or not (0 <= current <= 4095 and 0 <= light <= 4095):
                raise ValueError(f"Gia tri ngoai pham vi trong {path}: {row}")
            rows.append((condition, seq, current, light))

    if not rows:
        raise ValueError(f"File khong co mau: {path}")
    condition_counts = Counter(row[0] for row in rows)
    if len(condition_counts) != 1:
        raise ValueError(f"File tron nhieu dieu kien: {path}")

    condition = rows[0][0]
    lights = [row[3] for row in rows]
    seqs = [row[1] for row in rows]
    seq_anomalies = {"jump": 0, "duplicate": 0, "decrease": 0}
    for previous, current in zip(seqs, seqs[1:]):
        if current == previous + 1:
            continue
        if current == previous:
            seq_anomalies["duplicate"] += 1
        elif current < previous:
            seq_anomalies["decrease"] += 1
        else:
            seq_anomalies["jump"] += 1

    return {
        "condition": condition,
        "file": path,
        "n": len(lights),
        "mean": statistics.fmean(lights),
        "min": min(lights),
        "max": max(lights),
        "p2p": max(lights) - min(lights),
        "stdev": statistics.stdev(lights) if len(lights) >= 2 else 0.0,
        "zero": lights.count(0),
        "full_scale": lights.count(4095),
        "seq_anomalies": seq_anomalies,
    }


def latest_capture_per_condition(paths: list[Path]) -> tuple[list[Path], list[str]]:
    selected = []
    notes = []
    for condition in CONDITIONS:
        candidates = []
        for path in paths:
            metadata_path = path.with_suffix(".json")
            if metadata_path.exists():
                try:
                    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
                    if metadata.get("valid_for_analysis") is False:
                        notes.append(f"Bo qua {path.name}: {metadata.get('invalid_reason', 'phien bi danh dau khong hop le')}.")
                        continue
                except (OSError, json.JSONDecodeError):
                    notes.append(f"Khong doc duoc metadata cua {path.name}; van kiem tra CSV.")
            try:
                with path.open(newline="", encoding="utf-8-sig") as csv_file:
                    first = next(csv.DictReader(csv_file), None)
                if first and first.get("condition", "").upper() == condition:
                    candidates.append(path)
            except (OSError, csv.Error):
                continue
        if candidates:
            latest = max(candidates, key=lambda item: item.stat().st_mtime)
            selected.append(latest)
            if len(candidates) > 1:
                notes.append(f"{condition}: chon file moi nhat {latest.name} trong {len(candidates)} file.")
    return selected, notes


def ranges_overlap(left: dict, right: dict) -> bool:
    return max(left["min"], right["min"]) <= min(left["max"], right["max"])


def main() -> int:
    parser = argparse.ArgumentParser(description="Phan tich cac file CSV BPW34 da do.")
    parser.add_argument("files", nargs="*", type=Path,
                        help="CSV can phan tich; bo trong de chon file moi nhat moi dieu kien.")
    args = parser.parse_args()

    notes = []
    if args.files:
        paths = [path.resolve() for path in args.files]
    else:
        all_paths = [path for path in DATA_DIR.glob("*.csv") if not path.name.startswith("analysis_")]
        paths, notes = latest_capture_per_condition(all_paths)

    if not paths:
        print("Chua co CSV do that trong data/bpw34/.")
        return 1

    try:
        results = [read_capture(path) for path in paths]
    except (OSError, ValueError) as exc:
        print(f"Khong phan tich duoc: {exc}")
        return 1

    by_condition = {result["condition"]: result for result in results}
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    summary_path = DATA_DIR / f"analysis_{stamp}_summary.csv"
    report_path = DATA_DIR / f"analysis_{stamp}_report.md"

    with summary_path.open("x", newline="", encoding="utf-8") as output:
        fieldnames = (
            "condition", "source_file", "valid_samples", "L_mean", "L_min", "L_max",
            "L_peak_to_peak", "L_sample_stdev", "count_L_0", "count_L_4095",
            "seq_jump", "seq_duplicate", "seq_decrease",
        )
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        for result in results:
            writer.writerow(
                {
                    "condition": result["condition"],
                    "source_file": result["file"].name,
                    "valid_samples": result["n"],
                    "L_mean": f"{result['mean']:.3f}",
                    "L_min": result["min"],
                    "L_max": result["max"],
                    "L_peak_to_peak": result["p2p"],
                    "L_sample_stdev": f"{result['stdev']:.3f}",
                    "count_L_0": result["zero"],
                    "count_L_4095": result["full_scale"],
                    "seq_jump": result["seq_anomalies"]["jump"],
                    "seq_duplicate": result["seq_anomalies"]["duplicate"],
                    "seq_decrease": result["seq_anomalies"]["decrease"],
                }
            )

    lines = [
        "# Phân tích thử nghiệm BPW34",
        "",
        "> Trục và các thống kê L sử dụng count ADC 12 bit. `timestamp_pc` trong CSV là thời gian laptop nhận dữ liệu.",
        "",
        "| Điều kiện | Mẫu | L trung bình | L min | L max | Đỉnh–đỉnh | Độ lệch chuẩn mẫu | L=0 | L=4095 | Bất thường SEQ |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for result in results:
        anomaly_total = sum(result["seq_anomalies"].values())
        lines.append(
            f"| {result['condition']} | {result['n']} | {result['mean']:.3f} | "
            f"{result['min']} | {result['max']} | {result['p2p']} | {result['stdev']:.3f} | "
            f"{result['zero']} | {result['full_scale']} | {anomaly_total} |"
        )

    lines.extend(["", "## So sánh", ""])
    comparisons = (("PHONG", "CHE"), ("DEN", "CHE"), ("DEN", "PHONG"))
    for high, low in comparisons:
        if high in by_condition and low in by_condition:
            difference = by_condition[high]["mean"] - by_condition[low]["mean"]
            overlap = "có" if ranges_overlap(by_condition[high], by_condition[low]) else "không"
            lines.append(
                f"- Trung bình {high} − {low}: **{difference:.3f} count ADC**; "
                f"khoảng min–max **{overlap} chồng lấn**."
            )
        else:
            lines.append(f"- Chưa so sánh được {high} − {low} vì thiếu dữ liệu.")

    lines.extend(["", "## Nhận xét", ""])
    missing = [condition for condition in CONDITIONS if condition not in by_condition]
    incomplete = [result["condition"] for result in results if result["n"] < 100]
    if missing:
        lines.append(f"- Chưa hoàn thành đủ ba điều kiện; còn thiếu: {', '.join(missing)}.")
    if incomplete:
        lines.append(f"- Các phiên chưa đủ 100 mẫu: {', '.join(incomplete)}.")
    if not missing and not incomplete:
        lines.append("- Đã có đủ 100 mẫu cho cả CHE, PHONG và DEN.")
    lines.extend(
        [
            "- Trung bình biểu diễn mức tín hiệu L của từng điều kiện.",
            "- Đỉnh–đỉnh là khoảng dao động quan sát được trong phiên đo.",
            "- Độ lệch chuẩn mẫu biểu diễn độ phân tán; chưa xác định được nguồn hoặc toàn bộ nhiễu của mạch.",
            "- Phép thử đèn pin không phải phép đo độ nhạy theo lux và không chứng minh khả năng phát hiện Arc Flash.",
        ]
    )
    if notes:
        lines.extend(["", "## Lựa chọn file", "", *[f"- {note}" for note in notes]])

    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Da tao bang tong hop: {summary_path}")
    print(f"Da tao bao cao ngan: {report_path}")
    for result in results:
        print(
            f"{result['condition']}: n={result['n']}, mean={result['mean']:.3f}, "
            f"min={result['min']}, max={result['max']}, p2p={result['p2p']}, "
            f"stdev={result['stdev']:.3f}"
        )
    return 0 if len(by_condition) == 3 and all(item["n"] >= 100 for item in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
