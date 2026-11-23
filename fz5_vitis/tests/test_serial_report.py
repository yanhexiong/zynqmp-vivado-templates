"""Check FZ5 capture/report behavior with simulated UART and RS485 echo endpoints."""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("fz5_serial_test", ROOT / "scripts/serial_test.py")
capture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(capture)


class Port:
    def __init__(self, data):
        self.data, self.written, self.closed = data, b"", False

    def read(self, count):
        data, self.data = self.data[:count], self.data[count:]
        return data

    def write(self, data):
        self.written += data

    def close(self):
        self.closed = True

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


class Fz5SerialReport(unittest.TestCase):
    def run_capture(self, board_id, failures, echo=False, echo_passed=True):
        with tempfile.TemporaryDirectory(prefix="FZ5 capture ") as directory:
            folder = Path(directory)
            output = folder / "result.json"
            expected = "f" * 64
            (folder / "config.json").write_text(
                json.dumps(dict(BOARD_NAME="FZ5D", CONFIG_ID=expected, PS_UART1=True)),
                encoding="utf-8",
            )
            echo_result = "[PASS] UART1 RS485 echo: delayed echo passed\r\n" if echo and echo_passed else ""
            console = Port(
                (echo_result + f"FZ5_DIAG_END config={board_id} pass=12 fail={failures} skip=3 manual=6\r\n").encode()
            )
            pattern = bytes((0x55, 0xAA, 0x12, 0x34))
            peer = Port(pattern if echo_passed else b"")

            def serial_port(name, *args, **kwargs):
                return console if name == "PS-CONSOLE" else peer

            argv = ["serial_test.py", "--console", "PS-CONSOLE", "--hardware", str(folder), "--output", str(output), "--echo-delay-ms", "0"]
            if echo:
                argv.extend(["--pl-echo", "RS485-PEER"])
            with (
                patch.object(sys, "argv", argv),
                patch.object(capture.serial, "Serial", side_effect=serial_port),
                contextlib.redirect_stdout(io.StringIO()),
                contextlib.redirect_stderr(io.StringIO()),
            ):
                status = capture.main()
            report = json.loads(output.read_text())
            self.assertTrue(console.closed)
            self.assertIn("FZ5_DIAG_END", output.with_suffix(".uart.log").read_text())
            if echo:
                self.assertEqual(peer.written, pattern if echo_passed else b"")
                self.assertTrue(peer.closed)
            return status, report

    def test_success_and_rs485_echo(self):
        status, report = self.run_capture("f" * 64, 0, echo=True)
        self.assertEqual(status, 0)
        self.assertTrue(report["config_matches"])
        self.assertTrue(report["pl_echo_verified"])

    def test_wrong_config_fails(self):
        status, report = self.run_capture("0" * 64, 0)
        self.assertEqual(status, 1)
        self.assertFalse(report["config_matches"])


if __name__ == "__main__":
    unittest.main()
