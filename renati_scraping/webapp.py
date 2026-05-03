from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import threading
import time
import webbrowser
from dataclasses import dataclass, field
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


PROJECT_ROOT = Path(__file__).resolve().parents[1]
STATIC_ROOT = Path(__file__).resolve().parent / "static"

PROGRESS_RE = re.compile(r"\[(\d+)\s*/\s*(\d+)\]")


@dataclass(slots=True)
class ScrapingJob:
    id: str
    command: list[str]
    status: str = "running"
    logs: list[str] = field(default_factory=list)
    returncode: int | None = None
    output_path: str = ""
    started_at: float = field(default_factory=time.time)
    finished_at: float | None = None
    progress_current: int = 0
    progress_total: int = 0
    process: object | None = None

    def snapshot(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "status": self.status,
            "command": self.command,
            "logs": self.logs[-600:],
            "returncode": self.returncode,
            "output_path": self.output_path,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "progress": {
                "current": self.progress_current,
                "total": self.progress_total,
            },
        }


class JobManager:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._current: ScrapingJob | None = None

    def current(self) -> ScrapingJob | None:
        with self._lock:
            return self._current

    def start(self, payload: dict[str, Any]) -> ScrapingJob:
        with self._lock:
            if self._current and self._current.status == "running":
                raise RuntimeError("Ya existe una corrida en ejecucion. Cancelala antes de iniciar otra.")
            command = build_cli_command(payload)
            limit = _extract_limit(command)
            job = ScrapingJob(id=str(int(time.time())), command=command, progress_total=limit)
            self._current = job
        thread = threading.Thread(target=self._run_job, args=(job,), daemon=True)
        thread.start()
        return job

    def cancel(self) -> bool:
        with self._lock:
            job = self._current
            if not job or job.status != "running" or job.process is None:
                return False
            process = job.process
        try:
            process.terminate()
            try:
                process.wait(timeout=4)
            except Exception:
                process.kill()
        except Exception:
            return False
        return True

    def _run_job(self, job: ScrapingJob) -> None:
        job.logs.append("$ " + " ".join(job.command))
        try:
            process = subprocess.Popen(
                job.command,
                cwd=PROJECT_ROOT,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
            )
            job.process = process
            assert process.stdout is not None
            for line in process.stdout:
                clean = line.rstrip()
                job.logs.append(clean)
                if clean.startswith("Excel generado:"):
                    job.output_path = clean.split(":", 1)[1].strip()
                match = PROGRESS_RE.search(clean)
                if match:
                    current, total = int(match.group(1)), int(match.group(2))
                    job.progress_current = current
                    if total:
                        job.progress_total = total
            job.returncode = process.wait()
            if job.status == "running":
                job.status = "completed" if job.returncode == 0 else "failed"
        except Exception as exc:  # pragma: no cover - safety net for live UI
            job.status = "failed"
            job.returncode = -1
            job.logs.append(f"ERROR: {exc}")
        finally:
            job.finished_at = time.time()
            job.process = None
            if job.status == "running":
                job.status = "completed" if job.returncode == 0 else "failed"


JOBS = JobManager()


class RenatiWebHandler(SimpleHTTPRequestHandler):
    server_version = "RENATIWeb/0.2"

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, directory=str(STATIC_ROOT), **kwargs)

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path == "/api/jobs/current":
            job = JOBS.current()
            self._send_json(job.snapshot() if job else {"status": "idle", "logs": [], "progress": {"current": 0, "total": 0}})
            return
        if parsed.path == "/api/health":
            self._send_json({"ok": True, "version": self.server_version})
            return
        if parsed.path == "/":
            self.path = "/index.html"
        return super().do_GET()

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path == "/api/run":
            try:
                payload = self._read_json()
                job = JOBS.start(payload)
                self._send_json(job.snapshot(), status=202)
            except Exception as exc:
                self._send_json({"error": str(exc)}, status=400)
            return
        if parsed.path == "/api/jobs/cancel":
            ok = JOBS.cancel()
            self._send_json({"cancelled": ok}, status=200 if ok else 409)
            return
        if parsed.path == "/api/open-output":
            job = JOBS.current()
            target = (job.output_path if job else "") or ""
            opened = _open_in_explorer(target)
            self._send_json({"opened": opened, "path": target}, status=200 if opened else 404)
            return
        self.send_error(404)

    def log_message(self, format: str, *args: Any) -> None:
        return

    def _read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        return json.loads(self.rfile.read(length) or b"{}")

    def _send_json(self, payload: dict[str, Any], status: int = 200) -> None:
        raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(raw)


def build_cli_command(payload: dict[str, Any]) -> list[str]:
    topic = str(payload.get("topic") or "").strip()
    if not topic:
        raise ValueError("El tema es obligatorio.")
    limit = _int_or_default(payload.get("limit"), 300)
    if limit < 1 or limit > 2000:
        raise ValueError("El limite debe estar entre 1 y 2000.")

    command = [
        sys.executable,
        str(PROJECT_ROOT / "cli.py"),
        "--source",
        _choice(payload.get("source"), {"browser-export", "browser", "csv", "renati"}, "browser-export"),
        "--topic",
        topic,
        "--limit",
        str(limit),
        "--no-interactive",
    ]
    optional_text = {
        "--degree": payload.get("degree"),
        "--region": payload.get("region"),
        "--university": payload.get("university"),
        "--output-file": payload.get("output_file"),
        "--csv-path": payload.get("csv_path"),
    }
    for flag, value in optional_text.items():
        value = str(value or "").strip()
        if value:
            command.extend([flag, value])
    for flag, key in (("--start-year", "start_year"), ("--end-year", "end_year"), ("--max-pages", "max_pages")):
        value = str(payload.get(key) or "").strip()
        if value:
            int(value)
            command.extend([flag, value])
    if payload.get("headless"):
        command.append("--headless")
    if payload.get("allow_missing_summary"):
        command.append("--allow-missing-summary")
    if payload.get("no_detail_browser_fallback"):
        command.append("--no-detail-browser-fallback")
    return command


def run_server(host: str = "127.0.0.1", port: int = 8765, open_browser: bool = True) -> None:
    server = ThreadingHTTPServer((host, port), RenatiWebHandler)
    url = f"http://{host}:{port}"
    print(f"RENATI Web listo: {url}")
    print("Presiona Ctrl+C para detener el servidor.")
    if open_browser:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServidor detenido.")
    finally:
        server.server_close()


def _choice(value: object, allowed: set[str], default: str) -> str:
    candidate = str(value or default).strip()
    return candidate if candidate in allowed else default


def _int_or_default(value: object, default: int) -> int:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return default


def _extract_limit(command: list[str]) -> int:
    try:
        idx = command.index("--limit")
        return int(command[idx + 1])
    except (ValueError, IndexError):
        return 0


def _open_in_explorer(path: str) -> bool:
    if not path:
        return False
    target = Path(path)
    if not target.exists():
        return False
    try:
        if sys.platform.startswith("win"):
            os.startfile(str(target))  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(target)])
        else:
            subprocess.Popen(["xdg-open", str(target)])
        return True
    except Exception:
        return False
