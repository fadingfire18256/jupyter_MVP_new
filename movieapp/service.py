"""第 05 章產生：管理這份教材的本機 Django 服務。

PID 只是編號；停止前還要比對建立時間、工作目錄與啟動指令。
"""
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
import urllib.request

import psutil

ROOT = Path(__file__).resolve().parents[1]


def _paths(root):
    root = Path(root).resolve()
    return root / "server", root / ".classroom-server.json", root / ".classroom-server.log"


def _port_in_use(port, attempts=1):
    """連線成功才算有服務在監聽；Windows 關閉後殘留的 TIME_WAIT 不會讓 bind 誤判。"""
    for attempt in range(attempts):
        with socket.socket() as probe:
            probe.settimeout(0.5)
            if probe.connect_ex(("127.0.0.1", port)) != 0:
                return False
        if attempt + 1 < attempts:
            time.sleep(0.2)
    return True


def _terminate_tree(process, timeout=10):
    """結束行程與它的子行程，等到全部結束才回傳。"""
    # Windows 的 .venv\Scripts\python.exe 是啟動器，真正執行 Django 的是它的子行程。
    # 只結束啟動器時，子行程還會佔住埠號幾百毫秒，立即重啟會誤判埠號被占用。
    children = process.children(recursive=True)
    # psutil 在送出訊號前會再檢查 PID 是否已被其他行程重用。
    process.terminate()
    process.wait(timeout=timeout)
    _, alive = psutil.wait_procs(children, timeout=timeout)
    for child in alive:
        child.terminate()
    psutil.wait_procs(alive, timeout=timeout)


def stop(root=ROOT):
    """只停止身分相符的服務；找不到行程時清除過期紀錄。"""
    server_dir, record_path, _ = _paths(root)
    if not record_path.exists():
        return False
    try:
        record = json.loads(record_path.read_text(encoding="utf-8"))
        pid, created, port = record["pid"], record["created"], record["port"]
        if type(pid) is not int or pid <= 0 or type(created) not in (int, float):
            raise ValueError("invalid process identity")
        if type(port) is not int or not 1 <= port <= 65535:
            raise ValueError("invalid port")
        expected = [str(server_dir / "manage.py"), "runserver", f"127.0.0.1:{port}", "--noreload"]
        process = psutil.Process(pid)
        if (process.create_time() != created
                or Path(process.cwd()).resolve() != server_dir
                or process.cmdline()[1:] != expected):
            raise ValueError("process identity changed")
        _terminate_tree(process)
    except psutil.NoSuchProcess:
        pass
    except (OSError, ValueError, KeyError, TypeError, psutil.Error) as exc:
        raise RuntimeError(
            "無法確認或停止原服務，未強制終止任何其他行程。"
            "請查看 docs/student-guide.md 的服務啟停說明。"
        ) from exc
    record_path.unlink(missing_ok=True)
    return True


def start(port=8008, mode="demo", root=ROOT):
    """重啟這份教材的服務，回傳行程物件；失敗時收回本次啟動的行程。"""
    if type(port) is not int or not 1 <= port <= 65535:
        raise ValueError("port 必須介於 1 與 65535")
    if mode not in {"demo", "live"}:
        raise ValueError("mode 必須是 demo 或 live")
    server_dir, record_path, log_path = _paths(root)
    stopped = stop(root)
    # 剛結束的服務可能還在釋放埠號，多探測幾次再判定被占用；啟動競爭由下方 readiness 處理。
    if _port_in_use(port, attempts=10 if stopped else 1):
        raise RuntimeError(f"埠號 {port} 已被使用，請關閉原服務或換一個 MOVIEAPP_PORT。")
    env = dict(os.environ, MOVIEAPP_MODE=mode, PYTHONIOENCODING="utf-8", PYTHONDONTWRITEBYTECODE="1")
    command = [sys.executable, str(server_dir / "manage.py"), "runserver", f"127.0.0.1:{port}", "--noreload"]
    with log_path.open("w", encoding="utf-8") as log:
        server = psutil.Popen(command, cwd=str(server_dir), env=env, stdout=log,
                              stderr=subprocess.STDOUT,
                              creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    try:
        record = {"pid": server.pid, "created": server.create_time(), "port": port}
        record_path.write_text(json.dumps(record), encoding="utf-8")
        for _ in range(50):
            if server.poll() is not None:
                raise RuntimeError(f"服務啟動失敗，請查看 {log_path}")
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/time/", timeout=1) as response:
                    if response.status == 200:
                        return server
            except OSError:
                pass
            time.sleep(0.2)
        raise RuntimeError(f"啟動逾時，請查看 {log_path}")
    except BaseException:
        if server.poll() is None:
            _terminate_tree(server)
        record_path.unlink(missing_ok=True)
        raise
