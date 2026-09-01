#!/usr/bin/env python3
"""One-click Windows install for PEAR — the part ``install.bat`` calls.

Why the work is here and not in the .bat
----------------------------------------
The repo travels to the fab machine as one plain-text file and that bundle
only accepts LF line endings, but ``cmd.exe`` is unreliable with LF-only
batch files once blocks or ``goto`` appear. So ``install.bat`` is three lines
with neither, and everything that could go wrong lives here, where it can
say what went wrong.

What it does
------------
1. Makes a virtual environment in ``.venv`` (falls back to a ``--user``
   install if the machine forbids one).
2. Installs the three dependencies — **from ``wheels\\`` if that folder
   exists**, which is the whole point on a machine with no download route,
   otherwise from the network.
3. Checks the imports actually work.
4. Draws ``pear.ico``.
5. Puts shortcuts on the Desktop and in the Start Menu, pointing at
   ``PEAR.bat`` with that icon.

    python tools\\install_windows.py            # install
    python tools\\install_windows.py --run      # …and launch it
    python tools\\install_windows.py --no-venv  # install into this Python
    python tools\\install_windows.py --no-shortcuts
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VENV = os.path.join(ROOT, ".venv")
WHEELS = os.path.join(ROOT, "wheels")
MODULES = (("numpy", "numpy"), ("cv2", "opencv-python"),
           ("PySide6.QtWidgets", "PySide6"))


def say(step: str, text: str = "") -> None:
    print(f"\n[{step}] {text}" if text else f"\n[{step}]")


def run(cmd, **kw) -> int:
    """Run a command, showing it first — an install that fails silently is
    worse than one that fails loudly on a machine you cannot debug."""
    print("    > " + subprocess.list2cmdline(cmd))
    return subprocess.call(cmd, cwd=ROOT, **kw)


def venv_python(base: str) -> str:
    exe = "python.exe" if os.name == "nt" else "python"
    sub = "Scripts" if os.name == "nt" else "bin"
    return os.path.join(base, sub, exe)


def make_venv() -> str:
    """The interpreter to install into: the venv's, or this one."""
    if os.path.exists(venv_python(VENV)):
        print(f"    reusing {VENV}")
        return venv_python(VENV)
    if run([sys.executable, "-m", "venv", VENV]) == 0:
        return venv_python(VENV)
    print("    ! could not create a virtual environment — installing into\n"
          "      this Python instead (add --no-venv to skip the attempt)")
    return sys.executable


def install_deps(python: str, user: bool) -> bool:
    """Dependencies, from the local wheel folder if there is one."""
    base = [python, "-m", "pip", "install", "--disable-pip-version-check"]
    if user:
        base.append("--user")
    req = os.path.join(ROOT, "requirements.txt")
    if os.path.isdir(WHEELS):
        print(f"    found {WHEELS} — installing offline from it")
        code = run(base + ["--no-index", "--find-links", WHEELS, "-r", req])
        if code == 0:
            return True
        print("    ! the wheels in that folder did not satisfy "
              "requirements.txt; trying the network")
    return run(base + ["-r", req]) == 0


def check_imports(python: str) -> bool:
    missing = []
    for module, package in MODULES:
        code = subprocess.call([python, "-c", f"import {module}"],
                               stdout=subprocess.DEVNULL,
                               stderr=subprocess.DEVNULL)
        state = "ok" if code == 0 else "MISSING"
        print(f"    {package:<14} {state}")
        if code != 0:
            missing.append(package)
    return not missing


def make_icon(python: str) -> str:
    icon = os.path.join(ROOT, "pear.ico")
    if run([python, os.path.join(ROOT, "tools", "make_icon.py"),
            "--out", icon]) != 0 or not os.path.exists(icon):
        print("    ! icon not drawn — the shortcuts will use the default one")
        return ""
    return icon


def make_shortcuts(icon: str) -> None:
    """Desktop and Start Menu shortcuts, via WScript — no PowerShell.

    Locked-down machines often block PowerShell scripts outright, and
    ``cscript`` is the one scripting host that has always been there.
    """
    if os.name != "nt":
        print("    (skipped: shortcuts are a Windows thing)")
        return
    launcher = os.path.join(ROOT, "PEAR.bat")
    home = os.path.expanduser("~")
    targets = [os.path.join(home, "Desktop", "PEAR.lnk"),
               os.path.join(home, "AppData", "Roaming", "Microsoft",
                            "Windows", "Start Menu", "Programs", "PEAR.lnk")]
    lines = ['Set s = WScript.CreateObject("WScript.Shell")']
    for path in targets:
        folder = os.path.dirname(path)
        if not os.path.isdir(folder):
            print(f"    (skipped: no {folder})")
            continue
        lines += [
            f'Set k = s.CreateShortcut("{path}")',
            f'k.TargetPath = "{launcher}"',
            f'k.WorkingDirectory = "{ROOT}"',
            'k.Description = "PEAR — Pre-EBI Attribute Ranker"',
        ]
        if icon:
            lines.append(f'k.IconLocation = "{icon}"')
        lines.append("k.Save")
        print(f"    {path}")
    if len(lines) == 1:
        return
    with tempfile.NamedTemporaryFile("w", suffix=".vbs", delete=False,
                                     encoding="utf-8") as fh:
        fh.write("\r\n".join(lines) + "\r\n")
        script = fh.name
    try:
        if subprocess.call(["cscript", "//nologo", script]) != 0:
            print("    ! could not write the shortcuts — run PEAR.bat directly")
    except OSError:
        print("    ! cscript is not available — run PEAR.bat directly")
    finally:
        os.unlink(script)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Install PEAR on Windows.")
    ap.add_argument("--no-venv", action="store_true",
                    help="install into the Python running this script")
    ap.add_argument("--no-shortcuts", action="store_true")
    ap.add_argument("--run", action="store_true", help="launch when done")
    args = ap.parse_args(argv)

    print("PEAR — Pre-EBI Attribute Ranker")
    print(f"repo   : {ROOT}")
    print(f"python : {sys.version.split()[0]}  ({sys.executable})")
    if sys.version_info < (3, 9):
        print("\n! PEAR needs Python 3.9 or newer. Install one, then run "
              "install.bat again.")
        return 2

    say("1/5", "virtual environment")
    python = sys.executable if args.no_venv else make_venv()
    user_flag = args.no_venv or python == sys.executable

    say("2/5", "dependencies")
    if not install_deps(python, user_flag):
        print("\n! pip could not install the dependencies.\n"
              "  On a machine with no download route, copy the wheels for\n"
              "  numpy, opencv-python and PySide6 into:\n"
              f"      {WHEELS}\n"
              "  (any machine with internet: pip download -r requirements.txt\n"
              "   -d wheels), then run install.bat again.")
        return 1

    say("3/5", "checking the imports")
    if not check_imports(python):
        print("\n! something did not install cleanly — see the list above.")
        return 1

    say("4/5", "drawing the icon")
    icon = make_icon(python)

    say("5/5", "shortcuts")
    if args.no_shortcuts:
        print("    (skipped)")
    else:
        make_shortcuts(icon)

    print("\nDone. Start PEAR from the Desktop shortcut, or with PEAR.bat.")
    if args.run:
        print("\nLaunching…")
        pyw = python.replace("python.exe", "pythonw.exe")
        subprocess.Popen([pyw if os.path.exists(pyw) else python, "-m", "pear"],
                         cwd=ROOT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
