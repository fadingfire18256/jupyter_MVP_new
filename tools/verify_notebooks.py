"""在暫存教材副本依序執行六本 Notebook；略過套件安裝格，封鎖對外網路。"""
import argparse
import json
import os
from pathlib import Path
import shutil
import socket
import sys
import tempfile

import nbformat
from nbclient import NotebookClient
from jupyter_client import KernelManager

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from build_modules import generated_sources


def verify(output):
    output = Path(output).resolve()
    if output == ROOT or ROOT.is_relative_to(output) or output.is_relative_to(ROOT / "notebooks"):
        raise ValueError("執行輸出不可覆蓋專案根目錄或來源講義，請使用 .lesson-runs")
    output.mkdir(parents=True, exist_ok=True)
    generated = {target.relative_to(ROOT).as_posix() for _, target, _ in generated_sources()}
    with tempfile.TemporaryDirectory(prefix="aiclass-notebooks-") as temporary:
        temp = Path(temporary).resolve()
        project = temp / "course"
        def ignore(folder, names):
            relative = Path(folder).relative_to(ROOT)
            return [name for name in names if name in {".git", ".env", ".venv", "venv", "__pycache__", ".ipynb_checkpoints",
                    ".lesson-runs", ".classroom-server.pid", ".classroom-server.json"}
                    or (relative / name).as_posix() in generated or name.endswith(".log")
                    or ((name.startswith(".env.") and name != ".env.example"))
                    or (Path(folder) / name).resolve() == output]
        shutil.copytree(ROOT, project, ignore=ignore)
        guard = temp / "guard"
        guard.mkdir()
        (guard / "sitecustomize.py").write_text('''
import socket
_original_connect = socket.socket.connect
_original_lookup = socket.getaddrinfo
def _local(host):
    return host in ("127.0.0.1", "::1", "localhost", socket.gethostname(), None)
def _connect(self, address):
    if isinstance(address, tuple) and not _local(address[0]):
        raise AssertionError("Notebook verification blocked external network")
    return _original_connect(self, address)
def _lookup(host, *args, **kwargs):
    if not _local(host):
        raise AssertionError("Notebook verification blocked external DNS")
    return _original_lookup(host, *args, **kwargs)
socket.socket.connect = _connect
socket.getaddrinfo = _lookup
''', encoding="utf-8")
        with socket.socket() as port_probe:
            port_probe.bind(("127.0.0.1", 0))
            port = port_probe.getsockname()[1]
        env = dict(os.environ, MOVIEAPP_MODE="demo", MOVIEAPP_PORT=str(port),
                   PYTHONDONTWRITEBYTECODE="1", PYTHONIOENCODING="utf-8",
                   PYTHONPATH=str(guard), TMDB_READ_ACCESS_TOKEN="", GEMINI_API_KEY="")
        summary = []
        for path in sorted((project / "notebooks").glob("*.ipynb")):
            print("Executing", path.name, flush=True)
            nb = nbformat.read(path, as_version=4)
            nbformat.validate(nb)
            km = KernelManager(kernel_name="python3")
            km.kernel_spec.argv = [sys.executable, "-m", "ipykernel_launcher", "-f", "{connection_file}"]
            client = NotebookClient(nb, km=km, timeout=120, record_timing=False,
                                    skip_cells_with_tag="install",
                                    resources={"metadata": {"path": str(path.parent)}})
            try:
                client.execute(env=env)
            except Exception:
                nbformat.write(nb, output / path.name)
                raise
            finally:
                # Explicitly clean up our KernelManager (nbclient does not own it).
                if client.kc is not None and km.has_kernel:
                    cleanup = chr(10).join([
                        'if "server" in globals() and server.poll() is None:',
                        '    server.terminate()',
                        '    server.wait(timeout=10)',
                    ])
                    message_id = client.kc.execute(cleanup, silent=True, store_history=False)
                    while True:
                        response = client.kc.get_shell_msg(timeout=15)
                        if response.get("parent_header", {}).get("msg_id") == message_id:
                            break
                if km.has_kernel:
                    km.shutdown_kernel(now=True)
                km.cleanup_resources()
                if client.kc is not None:
                    client.kc.stop_channels()
            nbformat.write(nb, output / path.name)
            checks = sum("learning-check" in c.metadata.get("tags", []) for c in nb.cells)
            summary.append({"notebook": path.name, "status": "passed", "learning_checks": checks})
            print("Passed", path.name, "learning checks:", checks, flush=True)
        (output / "execution-summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, help="執行結果的目錄，原始講義保持乾淨")
    args = parser.parse_args()
    verify(args.output)
