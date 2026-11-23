"""Check capture/report behavior with simulated independent UART endpoints."""
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
spec = importlib.util.spec_from_file_location("axu_serial_test", ROOT / "scripts/serial_test.py")
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


class SerialReport(unittest.TestCase):
    def run_capture(self, board_id, failures, echo=False, echo_passed=True):
        with tempfile.TemporaryDirectory(prefix="AXU capture ") as directory:
            folder = Path(directory)
            output = folder / "result.json"
            expected = "a" * 64
            (folder / "config.json").write_text(json.dumps(dict(BOARD_NAME="AXU4EV-F", CONFIG_ID=expected,
                PL_UART=True)), encoding="utf-8")
            echo_result = "[PASS] PL UART CP2102 echo: received pattern\r\n" if echo and echo_passed else ""
            console = Port((echo_result + f"AXU4EV_DIAG_END config={board_id} pass=8 fail={failures} skip=0 manual=7\r\n").encode())
            pattern = bytes((0x55, 0xaa, 0x12, 0x34, 0x5a, 0xa5, 0x87, 0x78))
            peer = Port(pattern if echo_passed else b"")
            def serial_port(name, *args, **kwargs):
                return console if name == "PS-CONSOLE" else peer
            argv = ["serial_test.py", "--console", "PS-CONSOLE", "--hardware", str(folder), "--output", str(output)]
            if echo:
                argv.extend(["--pl-echo", "PL-ECHO"])
            with patch.object(sys, "argv", argv), patch.object(capture.serial, "Serial", side_effect=serial_port), contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                status = capture.main()
            report = json.loads(output.read_text())
            self.assertTrue(console.closed)
            self.assertIn("AXU4EV_DIAG_END", output.with_suffix(".uart.log").read_text())
            if echo:
                self.assertEqual(peer.written, pattern if echo_passed else b"")
                self.assertTrue(peer.closed)
            return status, report

    def test_success_preserves_manual_checks_and_echoes_separate_port(self):
        status, report = self.run_capture("a" * 64, 0, echo=True)
        self.assertEqual(status, 0)
        self.assertEqual(report["manual"], 7)
        self.assertTrue(report["config_matches"])
        self.assertTrue(report["pl_echo_verified"])

    def test_echo_requested_but_firmware_skipped_it(self):
        status, report = self.run_capture("a" * 64, 0, echo=True, echo_passed=False)
        self.assertEqual(status, 1)
        self.assertFalse(report["pl_echo_verified"])

    def test_wrong_hardware_configuration_fails(self):
        status, report = self.run_capture("b" * 64, 0)
        self.assertEqual(status, 1)
        self.assertFalse(report["config_matches"])

    def test_a_peripheral_failure_fails_the_capture(self):
        status, report = self.run_capture("a" * 64, 1)
        self.assertEqual(status, 1)
        self.assertEqual(report["fail"], 1)


if __name__ == "__main__":
    unittest.main()
