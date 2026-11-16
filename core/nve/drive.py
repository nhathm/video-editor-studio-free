"""Google Drive I/O through rclone, for Claude Code on the user's computer (macOS / Windows / Linux).

The user drives nve from their phone with Remote Control; phone attachments are capped (~30 MB), so big
videos go through Google Drive:

    Drive nve/google-raw-input      ->  <workspace>/google-drive/google-raw-input      (pull)
    Drive nve/google-edited-output  <-  <workspace>/google-drive/google-edited-output  (push)

rclone (MIT, third party) moves the data straight between this computer and Google; the token stays in
rclone's own config on this computer. A pinned rclone is installed into ~/.nve/bin (no admin rights) and its
zip is checked against the SHA-256 below. `setup` signs in through a browser on THIS computer, so it must be
run while the user sits at it; every other command is non-interactive and fails fast. Nothing is ever deleted,
on Drive or locally (the write check in `setup` removes only its own probe file).

Every function returns a dict with `ok`; `reason` explains a refusal (see skills/nve/references/drive.md).
"""
from __future__ import annotations

import hashlib
import io
import json
import os
import platform
import shutil
import subprocess
import sys
import urllib.request
import zipfile
from pathlib import Path

REMOTE = "nve-gdrive"
DRIVE_ROOT = "nve"
IN_DIR = "google-raw-input"
OUT_DIR = "google-edited-output"
LOCAL_ROOT = "google-drive"   # <workspace>/google-drive/{google-raw-input,google-edited-output}
DRIVE_IN = f"{REMOTE}:{DRIVE_ROOT}/{IN_DIR}"
DRIVE_OUT = f"{REMOTE}:{DRIVE_ROOT}/{OUT_DIR}"
LOGIN_TIMEOUT = 300   # seconds to wait for the user to click Allow in the browser
CHECK_TIMEOUT = 45

RCLONE_VERSION = "v1.76.0"
RCLONE_SHA256 = {   # from https://downloads.rclone.org/v1.76.0/SHA256SUMS
    "osx-arm64": "e72dc90b70f4947a7b72b61bde4a4fbba5777b2874fb448951ffdde67ebd0ab7",
    "osx-amd64": "4f5835733d52b818340f97b1fc0348a70461534d123363a183ca2b660219595a",
    "windows-amd64": "8b4fd2737ade4e70c057ef4a49deb7cffe94b0fb9d7587c189d149823f21a1dc",
    "windows-arm64": "c406c8a69a5a408e50624aa990fbb0a6266b3a4e83782a94de3cb96f50f86f10",
    "linux-amd64": "b00f00b3266c3764413afe599d3ec316f6f43b3e0ea8a0bc1d186d2133e46df7",
    "linux-arm64": "ee169016675e23a69d77240565133ff7dbc9b33d16fa8f7053d4af39f1eaeb78",
}
IS_WIN = sys.platform == "win32" or os.name == "nt"
BIN_DIR = Path.home() / ".nve" / "bin"
RCLONE_LOCAL = BIN_DIR / ("rclone.exe" if IS_WIN else "rclone")


def log(*a) -> None:
    print("[nve drive]", *a, file=sys.stderr, flush=True)


def _run(cmd: list[str], *, timeout: float | None = None, stream: bool = False) -> tuple[int, str, str]:
    """(code, stdout, stderr). stream=True passes rclone's progress through to stderr. Never reads stdin."""
    try:
        r = subprocess.run(cmd, stdin=subprocess.DEVNULL, timeout=timeout, text=True,
                           stdout=subprocess.PIPE, stderr=None if stream else subprocess.PIPE)
    except FileNotFoundError as e:
        return -1, "", str(e)
    except subprocess.TimeoutExpired:
        return -2, "", f"timed out after {timeout:.0f} s"
    return r.returncode, r.stdout or "", r.stderr or ""


# ---------- rclone ----------

def find_rclone() -> str | None:
    for c in (str(RCLONE_LOCAL), shutil.which("rclone")):
        if c and Path(c).exists() and _run([c, "version"], timeout=20)[0] == 0:
            return c
    return None


def _platform_key() -> str:
    osn = {"darwin": "osx", "win32": "windows", "linux": "linux"}.get(sys.platform, "windows" if IS_WIN else "")
    arch = {"x86_64": "amd64", "amd64": "amd64", "arm64": "arm64", "aarch64": "arm64"}.get(platform.machine().lower(), "")
    key = f"{osn}-{arch}"
    if key not in RCLONE_SHA256:
        raise RuntimeError(f"no rclone build for {sys.platform}/{platform.machine()}")
    return key


def install_rclone(fetch=None) -> str:
    """Download the pinned rclone, check its SHA-256, unpack the binary into ~/.nve/bin."""
    from nve.util import retry_once
    key = _platform_key()
    url = f"https://downloads.rclone.org/{RCLONE_VERSION}/rclone-{RCLONE_VERSION}-{key}.zip"
    # downloads.rclone.org answers 403 to urllib's default "Python-urllib/x.y" User-Agent.
    fetch = fetch or (lambda u: urllib.request.urlopen(
        urllib.request.Request(u, headers={"User-Agent": f"nve-studio rclone-installer ({RCLONE_VERSION})"}),
        timeout=120).read())
    log("downloading rclone", RCLONE_VERSION)
    data = retry_once(lambda: fetch(url), "rclone download")
    got = hashlib.sha256(data).hexdigest()
    if got != RCLONE_SHA256[key]:
        raise RuntimeError(f"rclone download checksum mismatch ({got[:12]}…)")
    name = "rclone.exe" if key.startswith("windows") else "rclone"
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        member = next((m for m in z.namelist() if m.rsplit("/", 1)[-1] == name), None)
        if not member:
            raise RuntimeError("rclone binary not found in the archive")
        BIN_DIR.mkdir(parents=True, exist_ok=True)
        tmp = RCLONE_LOCAL.with_suffix(".part")
        tmp.write_bytes(z.read(member))
    if not IS_WIN:
        tmp.chmod(0o755)
    os.replace(tmp, RCLONE_LOCAL)
    log("rclone installed at", RCLONE_LOCAL)
    return str(RCLONE_LOCAL)


def _has_remote(rc: str) -> bool:
    return f"{REMOTE}:" in _run([rc, "listremotes"], timeout=20)[1].split()


# ---------- local helpers ----------

def _dirs(ws: Path) -> tuple[Path, Path]:
    d_in, d_out = ws / LOCAL_ROOT / IN_DIR, ws / LOCAL_ROOT / OUT_DIR
    d_in.mkdir(parents=True, exist_ok=True)
    d_out.mkdir(parents=True, exist_ok=True)
    return d_in, d_out


def _snapshot(d: Path) -> dict[str, int]:
    return {p.name: p.stat().st_mtime_ns for p in d.iterdir() if p.is_file() and not p.name.startswith(".")} if d.is_dir() else {}


def drive_id(link: str) -> str | None:
    import re
    m = re.search(r"/d/([A-Za-z0-9_-]{10,})", link) or re.search(r"[?&]id=([A-Za-z0-9_-]{10,})", link)
    if m:
        return m.group(1)
    return link if re.fullmatch(r"[A-Za-z0-9_-]{10,}", link or "") else None


def _safe_name(name: str) -> str | None:
    """A plain file name inside the Drive folder (no folders, no '..')."""
    base = name.replace("\\", "/").rsplit("/", 1)[-1]
    return base if base and base not in (".", "..") and base == name.strip() else None


# ---------- commands ----------

def status() -> dict:
    rc = find_rclone()
    if not rc:
        return {"ok": False, "ready": False, "reason": "rclone_missing"}
    if not _has_remote(rc):
        return {"ok": False, "ready": False, "reason": "not_logged_in"}
    # Non-interactive: fails fast when the token was revoked or there is no network; never opens a browser.
    # Keep rclone's default low-level retries: its pacer backs off on Drive's per-minute rateLimitExceeded,
    # which with --low-level-retries 1 made status report drive_unreachable on a healthy connection.
    code, _, err = _run([rc, "lsf", f"{REMOTE}:{DRIVE_ROOT}", "--dirs-only", "--max-depth", "1",
                         "--contimeout", "15s", "--timeout", "30s", "--retries", "1"],
                        timeout=CHECK_TIMEOUT)
    if code != 0:
        return {"ok": False, "ready": False, "reason": "drive_unreachable", "detail": err.strip()[-400:]}
    return {"ok": True, "ready": True, "rclone": rc, "drive_input": f"{DRIVE_ROOT}/{IN_DIR}",
            "drive_output": f"{DRIVE_ROOT}/{OUT_DIR}"}


def setup(ws: Path, login_timeout: float = LOGIN_TIMEOUT) -> dict:
    try:
        rc = find_rclone() or install_rclone()
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "step": "install", "reason": "rclone_install_failed", "detail": str(e)[:300]}
    if not _has_remote(rc):
        log("A browser window opens on this computer: sign in to Google and click Allow.")
        # rclone serves the OAuth redirect on 127.0.0.1:53682 and opens the browser on THIS machine.
        code, _, err = _run([rc, "config", "create", REMOTE, "drive", "scope=drive"], timeout=login_timeout, stream=True)
        if code == -2 or not _has_remote(rc):
            if code == -2:
                _run([rc, "config", "delete", REMOTE], timeout=20)  # drop a half-made remote
            return {"ok": False, "step": "login", "reason": "login_timeout" if code == -2 else "login_failed_or_cancelled",
                    "detail": err.strip()[-300:]}
    for p in (DRIVE_IN, DRIVE_OUT):
        code, _, err = _run([rc, "mkdir", p], timeout=CHECK_TIMEOUT)
        if code != 0:
            return {"ok": False, "step": "mkdir", "reason": "drive_unreachable", "detail": err.strip()[-300:]}
    probe = f"{DRIVE_OUT}/.nve-check"
    if _run([rc, "touch", probe], timeout=CHECK_TIMEOUT)[0] != 0 or _run([rc, "deletefile", probe], timeout=CHECK_TIMEOUT)[0] != 0:
        return {"ok": False, "step": "verify", "reason": "cannot_write_drive"}
    d_in, d_out = _dirs(ws)
    return {"ok": True, "ready": True, "drive_input": f"{DRIVE_ROOT}/{IN_DIR}", "drive_output": f"{DRIVE_ROOT}/{OUT_DIR}",
            "local_input": str(d_in), "local_output": str(d_out)}


def _drive_files(rc: str, ws: Path) -> list[dict] | None:
    code, out, _ = _run([rc, "lsjson", DRIVE_IN, "--files-only"], timeout=CHECK_TIMEOUT * 2)
    if code != 0:
        return None
    local = _snapshot(ws / LOCAL_ROOT / IN_DIR)
    files = sorted((f for f in json.loads(out or "[]") if not f["Name"].startswith(".")),
                   key=lambda f: f.get("ModTime", ""), reverse=True)   # newest first
    return [{"n": i + 1, "name": f["Name"], "size_mb": round(f.get("Size", 0) / 1048576, 1),
             "modified": f.get("ModTime", ""), "already_local": f["Name"] in local, "_id": f.get("ID", "")}
            for i, f in enumerate(files)]


def _public(files: list[dict]) -> list[dict]:
    return [{k: v for k, v in f.items() if not k.startswith("_")} for f in files]


def list_files(ws: Path) -> dict:
    st = status()
    if not st["ready"]:
        return st
    files = _drive_files(st["rclone"], ws)
    if files is None:
        return {"ok": False, "reason": "list_failed"}
    return {"ok": True, "folder": f"{DRIVE_ROOT}/{IN_DIR}", "files": _public(files)}


def pull(ws: Path, names: list[str] | None = None, link: str | None = None) -> dict:
    """No names: 0 files -> empty, 1 file -> download it, several -> reason "choose" with the list.
    names: exactly those files of nve/google-raw-input. link: one file by Drive share link or id."""
    st = status()
    if not st["ready"]:
        return st
    rc = st["rclone"]
    d_in, _ = _dirs(ws)
    stats = ["--stats", "10s", "--stats-one-line"]
    if link is not None:
        fid = drive_id(link)
        if not fid:
            return {"ok": False, "reason": "bad_link"}
        files = _drive_files(rc, ws) or []
        match = next((f for f in files if f["_id"] == fid), None)
        if match:   # a file of nve/google-raw-input: pull it by name (an identical local copy is skipped)
            names = [match["name"]]
        else:
            # Unknown name: download into a fresh folder so the result always names the file, even when an
            # identical copy is already in google-raw-input (copyid would then change nothing).
            import tempfile
            tmp = Path(tempfile.mkdtemp(prefix=".nve-pull-", dir=d_in))
            try:
                if _run([rc, "backend", "copyid", f"{REMOTE}:", fid, str(tmp) + os.sep, *stats], stream=True)[0] != 0:
                    return {"ok": False, "reason": "pull_failed"}
                got = [q for q in tmp.iterdir() if q.is_file()]
                if not got:
                    return {"ok": False, "reason": "pull_failed"}
                for q in got:
                    os.replace(q, d_in / q.name)
                return {"ok": True, "pulled": [str(d_in / q.name) for q in got], "local_input": str(d_in)}
            finally:
                shutil.rmtree(tmp, ignore_errors=True)
    if not names:
        files = _drive_files(rc, ws)
        if files is None:
            return {"ok": False, "reason": "list_failed"}
        if not files:
            return {"ok": False, "reason": "empty", "folder": f"{DRIVE_ROOT}/{IN_DIR}"}
        if len(files) > 1:
            return {"ok": False, "reason": "choose", "folder": f"{DRIVE_ROOT}/{IN_DIR}", "files": _public(files)}
        names = [files[0]["name"]]
    elif link is None:
        files = _drive_files(rc, ws)
        if files is None:
            return {"ok": False, "reason": "list_failed"}
        known = {f["name"] for f in files}
        for name in names:
            if _safe_name(name) and name not in known:
                return {"ok": False, "reason": "file_not_found", "file": name, "pulled": [],
                        "folder": f"{DRIVE_ROOT}/{IN_DIR}", "files": _public(files)}
    pulled = []
    for name in names:
        safe = _safe_name(name)
        if not safe:
            return {"ok": False, "reason": "bad_name", "file": name, "pulled": pulled}
        # copyto with an exact path: no glob / filter escaping with odd file names; an identical local copy is skipped.
        if _run([rc, "copyto", f"{DRIVE_IN}/{safe}", str(d_in / safe), *stats], stream=True)[0] != 0:
            return {"ok": False, "reason": "pull_failed", "file": safe, "pulled": pulled}
        pulled.append(str(d_in / safe))
    return {"ok": True, "pulled": pulled, "local_input": str(d_in)}


def push(ws: Path, files: list[str]) -> dict:
    """Copy finished renders to <workspace>/google-drive/google-edited-output and up to Drive nve/google-edited-output."""
    st = status()
    if not st["ready"]:
        return st
    if not files:
        return {"ok": False, "reason": "no_files"}
    _, d_out = _dirs(ws)
    pushed = []
    for f in files:
        src = Path(f).expanduser()
        if not src.is_absolute():
            src = (Path.cwd() / src) if (Path.cwd() / src).exists() else ws / src
        if not src.is_file():
            return {"ok": False, "reason": "file_not_found", "file": f, "pushed": pushed}
        local = d_out / src.name
        if src.resolve() != local.resolve():
            shutil.copy2(src, local)
        if _run([st["rclone"], "copyto", str(local), f"{DRIVE_OUT}/{src.name}", "--stats", "10s", "--stats-one-line"],
                stream=True)[0] != 0:
            return {"ok": False, "reason": "push_failed", "file": str(local), "pushed": pushed}
        pushed.append(f"{DRIVE_ROOT}/{OUT_DIR}/{src.name}")
    return {"ok": True, "pushed": pushed, "local_output": str(d_out)}
