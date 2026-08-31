"""The single-file text bundle: it round-trips, and it is not stale.

The bundle is how the code reaches a machine that cannot download anything
(see ``docs/NO-GIT-SETUP.md``). A stale bundle has no symptom on this machine —
it shows up as *missing work* on the other one — so a test has to say so.
"""

from __future__ import annotations

import os
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))

import make_text_bundle as mtb            # noqa: E402

BUNDLE = os.path.join(ROOT, "bundle", "pear_bundle.py")
REBUILD = "python tools/make_text_bundle.py"


def _in_git_repo() -> bool:
    try:
        subprocess.run(["git", "rev-parse", "--git-dir"], cwd=ROOT, check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except (OSError, subprocess.CalledProcessError):
        return False
    return True


# Unpacked copies have no .git, and that is a supported way to run the tool —
# so skip rather than fail there.
needs_git = pytest.mark.skipif(not _in_git_repo(),
                               reason="needs a git checkout (git ls-files)")


@needs_git
def test_bundle_is_current():
    assert os.path.isfile(BUNDLE), f"{BUNDLE} is missing — run: {REBUILD}"
    with open(BUNDLE, encoding="utf-8") as fh:
        on_disk = fh.read()
    fresh = mtb.build(os.path.basename(BUNDLE))
    assert on_disk == fresh, (
        "bundle/pear_bundle.py is out of date — the copy that reaches the "
        "offline machine would be missing this change.\n"
        f"    git add -A && {REBUILD} && git add -A")


@needs_git
def test_bundle_round_trips_byte_for_byte(tmp_path):
    """Every file comes back out exactly as it went in."""
    items = mtb.collect()
    assert items, "git ls-files found nothing"
    text = mtb.build("pear_bundle.py", items=items)

    out = tmp_path / "pear_bundle.py"
    out.write_text(text, encoding="utf-8", newline="\n")
    r = subprocess.run([sys.executable, str(out), "--dest", str(tmp_path / "x")],
                       cwd=str(tmp_path), stdout=subprocess.PIPE,
                       stderr=subprocess.STDOUT)
    assert r.returncode == 0, r.stdout.decode("utf-8", "replace")
    for rel, data in items:
        got = (tmp_path / "x" / rel).read_bytes()
        assert got == data, f"{rel} did not survive the round trip"


@needs_git
def test_bundle_survives_crlf_in_transit(tmp_path):
    """Notepad and mail filters rewrite LF to CRLF; that must not break it.

    This is why the format frames files by *line count* rather than byte
    count — a byte count would corrupt every file after the first.
    """
    items = mtb.collect()[:4]
    text = mtb.build("pear_bundle.py", items=items, total_files=len(items))
    out = tmp_path / "pear_bundle.py"
    out.write_bytes(text.replace("\n", "\r\n").encode("utf-8"))
    r = subprocess.run([sys.executable, str(out), "--dest", str(tmp_path / "x")],
                       cwd=str(tmp_path), stdout=subprocess.PIPE,
                       stderr=subprocess.STDOUT)
    assert r.returncode == 0, r.stdout.decode("utf-8", "replace")
    for rel, data in items:
        assert (tmp_path / "x" / rel).read_bytes() == data


@needs_git
def test_truncated_bundle_is_reported_not_silently_partial(tmp_path):
    """A cut-off paste must fail loudly — a half-repo is worse than none."""
    items = mtb.collect()[:4]
    text = mtb.build("pear_bundle.py", items=items, total_files=len(items))
    lines = text.split("\n")
    out = tmp_path / "cut.py"
    out.write_text("\n".join(lines[:lines.index(mtb.SENTINEL)]) + "\n",
                   encoding="utf-8", newline="\n")
    r = subprocess.run([sys.executable, str(out), "--dest", str(tmp_path / "x")],
                       cwd=str(tmp_path), stdout=subprocess.PIPE,
                       stderr=subprocess.STDOUT)
    assert r.returncode == 2
    assert "截斷" in r.stdout.decode("utf-8", "replace")


@needs_git
def test_tampered_file_is_caught_by_its_sha(tmp_path):
    items = [("a.txt", b"hello\nworld"), ("b.txt", b"second")]
    text = mtb.build("pear_bundle.py", items=items, total_files=2)
    # flip a character inside the data region, leaving the SHA header alone
    text = text.replace("#hello", "#hellO")
    out = tmp_path / "bad.py"
    out.write_text(text, encoding="utf-8", newline="\n")
    r = subprocess.run([sys.executable, str(out), "--dest", str(tmp_path / "x")],
                       cwd=str(tmp_path), stdout=subprocess.PIPE,
                       stderr=subprocess.STDOUT)
    assert r.returncode == 1
    assert "a.txt" in r.stdout.decode("utf-8", "replace")
    # the good file still landed; only the damaged one is withheld
    assert (tmp_path / "x" / "b.txt").read_bytes() == b"second"
    assert not (tmp_path / "x" / "a.txt").exists()


@needs_git
def test_bundle_excludes_itself():
    """Otherwise each build packs the previous build — exponentially."""
    assert not any(rel.startswith("bundle/") for rel, _d in mtb.collect())


def test_data_lines_stay_valid_python():
    """Every data line is commented out, so the bundle still compiles."""
    body = mtb._data_lines([("x.py", b"def f(:\n  \xe3\x80\x8c oops")])
    compile("\n".join(body), "<bundle>", "exec")     # would raise if bare
