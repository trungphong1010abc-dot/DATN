import csv
import importlib.util
import io
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location("capture_module", Path(__file__).resolve().parents[1] / "tools/capture_module.py")
capture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(capture)


def frame(seq, ma=480, flashes=5, alarm=1, flags=0):
    payload = f"DATA,{seq},{seq*1000},{ma},2100,{flashes},{alarm},{flags}"
    check = 0
    for byte in payload.encode(): check ^= byte
    return f"{payload}*{check:02X}\n"


class FakeSerial:
    def __init__(self, lines): self.lines = iter(lines); self.closed = False
    def readline(self): return next(self.lines, b"")
    def reset_input_buffer(self): pass
    def close(self): self.closed = True


class CaptureTests(unittest.TestCase):
    def test_valid_and_corrupt_frame(self):
        self.assertEqual(capture.parse_frame(frame(1)), (1, 1000, 480, 2100, 5, 1, 0))
        with self.assertRaises(ValueError): capture.parse_frame(frame(1).replace("480", "481"))

    def run_session(self, lines):
        fake = FakeSerial([s.encode() for s in lines])
        with tempfile.TemporaryDirectory() as folder:
            with patch.object(capture, "ROOT", Path(folder)), patch("serial.Serial", return_value=fake), \
                 patch("sys.argv", ["capture_module.py", "4", "--port", "TEST"]), \
                 patch("builtins.input", return_value=""), patch.object(capture.time, "sleep"), \
                 patch("sys.stdout", new_callable=io.StringIO):
                result = capture.run()
            paths = list(Path(folder).rglob("*.csv"))
            self.assertEqual(len(paths), 1)
            with paths[0].open(encoding="utf-8-sig", newline="") as stream:
                rows = list(csv.reader(stream, delimiter=";"))
            self.assertTrue(fake.closed)
            return result, rows

    def test_complete_session_exactly_six_columns(self):
        result, rows = self.run_session([frame(i) for i in range(1, 22)])
        self.assertEqual(result, 0)
        self.assertEqual(len(rows), 21) # header + 20 real reports
        self.assertEqual(rows[0], capture.HEADERS)
        self.assertTrue(all(len(row) == 6 for row in rows))
        self.assertEqual(rows[1][2:], ["0,480", "2,100", "5", "Có"])

    def test_missing_frame_stops_without_filling(self):
        result, rows = self.run_session([frame(1), frame(2), frame(4)])
        self.assertEqual(result, 1)
        self.assertEqual(len(rows), 2)

    def test_adc_fault_does_not_become_valid_data(self):
        result, rows = self.run_session([frame(1), frame(2, flags=1)])
        self.assertEqual(result, 1)
        self.assertEqual(len(rows), 1)


if __name__ == "__main__": unittest.main()
