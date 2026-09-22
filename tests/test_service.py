"""服務紀錄不等於行程身分：不啟動或停止真實使用者行程的回歸測試。"""
import json
from pathlib import Path
import tempfile
import shutil
import socket
import subprocess
import sys
import urllib.request
import unittest
from unittest.mock import Mock, patch

import psutil
from movieapp import service


class ServiceIdentityTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name).resolve()
        self.server_dir = self.root / "server"
        self.server_dir.mkdir()
        self.record = self.root / ".classroom-server.json"
        self.record.write_text(json.dumps({"pid": 43210, "created": 100.5, "port": 8008}))
        self.process = Mock()
        self.process.create_time.return_value = 100.5
        self.process.cwd.return_value = str(self.server_dir)
        self.process.cmdline.return_value = ["python", str(self.server_dir / "manage.py"),
                                             "runserver", "127.0.0.1:8008", "--noreload"]
        self.process.children.return_value = []   # 一般直譯器沒有子行程；啟動器情境另外測試

    def test_matching_process_can_be_stopped_after_kernel_restart(self):
        with patch.object(service.psutil, "Process", return_value=self.process):
            self.assertTrue(service.stop(self.root))
        self.process.terminate.assert_called_once()
        self.process.wait.assert_called_once_with(timeout=10)
        self.assertFalse(self.record.exists())

    def test_children_of_matching_launcher_are_stopped_before_returning(self):
        """Windows 的 .venv 啟動器會另開真正的直譯器；stop() 也要等它結束，埠號才會釋放。"""
        child = Mock()
        self.process.children.return_value = [child]
        with (patch.object(service.psutil, "Process", return_value=self.process),
              patch.object(service.psutil, "wait_procs",
                           side_effect=[([], [child]), ([child], [])]) as wait_procs):
            self.assertTrue(service.stop(self.root))
        self.process.children.assert_called_once_with(recursive=True)
        self.process.terminate.assert_called_once()
        child.terminate.assert_called_once()
        self.assertEqual(wait_procs.call_count, 2)
        self.assertFalse(self.record.exists())

    def test_reused_pid_or_different_project_is_never_terminated(self):
        changes = {"create_time": 999.0, "cwd": str(self.root),
                   "cmdline": ["python", "another_app.py"]}
        for method, value in changes.items():
            with self.subTest(method=method):
                original = getattr(self.process, method).return_value
                getattr(self.process, method).return_value = value
                with patch.object(service.psutil, "Process", return_value=self.process):
                    with self.assertRaises(RuntimeError):
                        service.stop(self.root)
                self.process.terminate.assert_not_called()
                self.assertTrue(self.record.exists())
                getattr(self.process, method).return_value = original

    def test_missing_process_only_removes_stale_record(self):
        with patch.object(service.psutil, "Process", side_effect=psutil.NoSuchProcess(43210)):
            self.assertTrue(service.stop(self.root))
        self.assertFalse(self.record.exists())

    def test_invalid_record_does_not_look_up_or_kill_process(self):
        for text in ["43210", "not json", "[]", '{"pid":0,"created":100,"port":8008}']:
            with self.subTest(text=text):
                self.record.write_text(text)
                with patch.object(service.psutil, "Process") as process:
                    with self.assertRaises(RuntimeError):
                        service.stop(self.root)
                process.assert_not_called()

    def test_access_denied_preserves_record_for_manual_inspection(self):
        self.process.cwd.side_effect = psutil.AccessDenied(43210)
        with patch.object(service.psutil, "Process", return_value=self.process):
            with self.assertRaises(RuntimeError):
                service.stop(self.root)
        self.process.terminate.assert_not_called()
        self.assertTrue(self.record.exists())

    def test_no_record_is_noop(self):
        self.record.unlink()
        with patch.object(service.psutil, "Process") as process:
            self.assertFalse(service.stop(self.root))
        process.assert_not_called()

    def test_occupied_port_does_not_start_or_kill_a_process(self):
        self.record.unlink()
        with patch.object(service.socket, "socket") as socket, patch.object(service.psutil, "Popen") as popen:
            socket.return_value.__enter__.return_value.connect_ex.return_value = 0
            with self.assertRaisesRegex(RuntimeError, "已被使用"):
                service.start(root=self.root)
            popen.assert_not_called()



class ServiceLifecycleTests(unittest.TestCase):
    def test_restart_and_stop_from_new_interpreter(self):
        """在隔離副本重現 Windows 立即重啟與 kernel 重開後關閉服務。"""
        first = second = None
        with tempfile.TemporaryDirectory(prefix="classroom-service-test-") as folder:
            root = Path(folder)
            for name in ("movieapp", "server"):
                shutil.copytree(service.ROOT / name, root / name,
                                ignore=shutil.ignore_patterns("__pycache__"))
            shutil.copy2(service.ROOT / ".env.example", root / ".env.example")
            with socket.socket() as probe:
                probe.bind(("127.0.0.1", 0))
                port = probe.getsockname()[1]
            try:
                first = service.start(port=port, mode="demo", root=root)
                with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/movies/", timeout=5) as response:
                    self.assertEqual(len(json.load(response)["movies"]), 3)
                second = service.start(port=port, mode="demo", root=root)
                self.assertNotEqual(first.pid, second.pid)
                subprocess.run([sys.executable, "-B", "-c", "from movieapp import service; assert service.stop()"],
                               cwd=root, check=True, timeout=20, capture_output=True)
                with socket.socket() as probe:
                    probe.settimeout(1)
                    self.assertNotEqual(probe.connect_ex(("127.0.0.1", port)), 0)
                self.assertFalse((root / ".classroom-server.json").exists())
            finally:
                for process in (second, first):
                    if process is not None and process.poll() is None:
                        process.terminate()
                        process.wait(timeout=10)


if __name__ == "__main__":
    unittest.main()
