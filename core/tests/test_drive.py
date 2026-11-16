"""Google Drive in / out (core/nve/drive.py): every edition, Claude Code on the computer only.
Uses a fake rclone (a shell script over a local "drive" folder); no network, no Google account."""
from pathlib import Path

import pytest


# ── Google Drive in / out (fake rclone: a shell script over a local "drive" folder) ──

FAKE_RCLONE = r'''#!/bin/sh
# minimal rclone stand-in: remote "nve-gdrive:" maps to $FAKE_DRIVE
d() { echo "$1" | sed "s#^nve-gdrive:#$FAKE_DRIVE/#"; }
case "$1" in
  version) echo "rclone v0-fake";;
  listremotes) [ -f "$FAKE_DRIVE/.logged_in" ] && echo "nve-gdrive:";;
  lsf) [ -n "$FAKE_OFFLINE" ] && { echo "offline" >&2; exit 1; }; ls "$(d "$2")" >/dev/null;;
  lsjson) python3 -c "import json,os,sys,datetime;p=sys.argv[1];print(json.dumps([{'Name':n,'ID':'id_'+n.replace(' ','_').replace('.','_')+'_0123456789','Size':os.path.getsize(os.path.join(p,n)),'ModTime':datetime.datetime.fromtimestamp(os.path.getmtime(os.path.join(p,n))).isoformat()} for n in os.listdir(p)]))" "$(d "$2")";;
  copyto) cp "$(d "$2")" "$(d "$3")";;
  backend) cp "$FAKE_DRIVE/byid/$4" "$5";;
  mkdir) mkdir -p "$(d "$2")";;
  touch) touch "$(d "$2")";;
  deletefile) rm "$(d "$2")";;
  config) [ "$2" = create ] && touch "$FAKE_DRIVE/.logged_in";;
esac
'''


@pytest.fixture
def fake_drive(tmp_path, monkeypatch):
    from nve import drive
    drv = tmp_path / "drive"
    (drv / "nve" / "google-raw-input").mkdir(parents=True)
    (drv / "byid").mkdir()
    rc = tmp_path / "rclone"
    rc.write_text(FAKE_RCLONE)
    rc.chmod(0o755)
    monkeypatch.setenv("FAKE_DRIVE", str(drv))
    monkeypatch.setattr(drive, "RCLONE_LOCAL", rc)
    monkeypatch.setattr(drive.shutil, "which", lambda name: None)
    ws = tmp_path / "ws"
    ws.mkdir()
    return drive, drv, ws


def test_drive_needs_setup_and_never_blocks(fake_drive, monkeypatch):
    drive, drv, ws = fake_drive
    assert drive.status()["reason"] == "not_logged_in"
    assert drive.pull(ws)["reason"] == "not_logged_in"       # remote request before setup: refuses at once
    monkeypatch.setattr(drive, "RCLONE_LOCAL", drv / "missing")
    assert drive.status()["reason"] == "rclone_missing"


def test_drive_setup_pull_push(fake_drive, monkeypatch):
    drive, drv, ws = fake_drive
    res = drive.setup(ws)
    assert res["ok"] and (ws / "google-drive" / "google-raw-input").is_dir() and (drv / "nve" / "google-edited-output").is_dir()
    assert not (drv / "nve" / "google-edited-output" / ".nve-check").exists()
    assert drive.pull(ws)["reason"] == "empty"
    raw = drv / "nve" / "google-raw-input"
    (raw / "a.mp4").write_bytes(b"a" * 10)
    one = drive.pull(ws)
    assert one["ok"] and Path(one["pulled"][0]).read_bytes() == b"a" * 10
    (raw / "b b.mov").write_bytes(b"b")
    many = drive.pull(ws)
    assert many["reason"] == "choose" and {f["name"]: f["already_local"] for f in many["files"]} == {"a.mp4": True, "b b.mov": False}
    assert drive.pull(ws, ["b b.mov"])["pulled"] == [str(ws / "google-drive" / "google-raw-input" / "b b.mov")]
    assert drive.pull(ws, ["../x"])["reason"] == "bad_name"
    miss = drive.pull(ws, ["nope.mp4"])   # a name not on Drive: file_not_found with the list, not pull_failed
    assert miss["reason"] == "file_not_found" and {f["name"] for f in miss["files"]} == {"a.mp4", "b b.mov"}
    assert all("_id" not in f for f in miss["files"])
    # a link to a file of the folder that is already local still names it
    again = drive.pull(ws, link="https://drive.google.com/file/d/id_a_mp4_0123456789/view")
    assert again["ok"] and [Path(p).name for p in again["pulled"]] == ["a.mp4"]
    (drv / "byid" / "1AbCdEfGhIjK").write_bytes(b"c")
    got = drive.pull(ws, link="https://drive.google.com/file/d/1AbCdEfGhIjK/view?usp=sharing")
    assert got["ok"] and [Path(p).name for p in got["pulled"]] == ["1AbCdEfGhIjK"]
    twice = drive.pull(ws, link="https://drive.google.com/file/d/1AbCdEfGhIjK/view")   # identical copy already local
    assert twice["ok"] and [Path(p).name for p in twice["pulled"]] == ["1AbCdEfGhIjK"]
    assert not [q for q in (ws / "google-drive" / "google-raw-input").iterdir() if q.name.startswith(".nve-pull-")]
    assert drive.pull(ws, link="https://example.com/nope")["reason"] == "bad_link"
    render = ws / "projects" / "p" / "renders" / "final_v1.mp4"
    render.parent.mkdir(parents=True)
    render.write_bytes(b"final")
    up = drive.push(ws, [str(render)])
    assert up["pushed"] == ["nve/google-edited-output/final_v1.mp4"]
    assert (drv / "nve" / "google-edited-output" / "final_v1.mp4").read_bytes() == b"final"
    assert (ws / "google-drive" / "google-edited-output" / "final_v1.mp4").exists() and render.exists()
    assert drive.push(ws, ["nope.mp4"])["reason"] == "file_not_found"
    monkeypatch.setenv("FAKE_OFFLINE", "1")
    assert drive.status()["reason"] == "drive_unreachable"


def test_drive_rclone_install_checks_sha256(tmp_path, monkeypatch):
    import hashlib
    import io
    import zipfile
    from nve import drive
    monkeypatch.setattr(drive, "BIN_DIR", tmp_path / "bin")
    monkeypatch.setattr(drive, "RCLONE_LOCAL", tmp_path / "bin" / "rclone")
    monkeypatch.setattr(drive, "_platform_key", lambda: "osx-arm64")
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("rclone-v1.76.0-osx-arm64/rclone", "#!/bin/sh\necho ok\n")
    data = buf.getvalue()
    with pytest.raises(RuntimeError, match="checksum"):
        drive.install_rclone(fetch=lambda u: data)
    monkeypatch.setitem(drive.RCLONE_SHA256, "osx-arm64", hashlib.sha256(data).hexdigest())
    assert drive.install_rclone(fetch=lambda u: data) == str(tmp_path / "bin" / "rclone")
    assert drive.drive_id("https://drive.google.com/open?id=1AbCdEfGhIjKl") == "1AbCdEfGhIjKl"


def test_drive_rclone_download_sends_own_user_agent(tmp_path, monkeypatch):
    # downloads.rclone.org answers 403 to urllib's default "Python-urllib/x.y" User-Agent
    from nve import drive
    seen = {}

    class Resp:
        def read(self):
            return b"not a zip"

    def fake_urlopen(req, timeout=None):
        seen["ua"] = req.get_header("User-agent")
        return Resp()

    monkeypatch.setattr(drive.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(drive, "_platform_key", lambda: "osx-arm64")
    with pytest.raises(RuntimeError, match="checksum"):
        drive.install_rclone()
    assert seen["ua"] and not seen["ua"].startswith("Python-urllib")
