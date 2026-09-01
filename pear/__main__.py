"""Entry point: ``python -m pear`` (and the ``pear`` console script)."""

from __future__ import annotations

import sys


def app_icon():
    """The icon ``tools/make_icon.py`` drew, if it has been run.

    It is generated rather than committed — the offline machine gets the repo
    as one plain-text file, which takes no binaries — so its absence is normal
    and never fatal.
    """
    import os

    from PySide6.QtGui import QIcon

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    for name in ("pear.ico", "pear_icon.png"):
        path = os.path.join(root, name)
        if os.path.exists(path):
            icon = QIcon(path)
            if not icon.isNull():
                return icon
    return None


def main() -> int:
    """Launch the PEAR desktop application."""
    # Import lazily so that importing the package (e.g. for ``--version``)
    # does not require a Qt display.
    if "--version" in sys.argv:
        from pear import __version__

        print(f"PEAR {__version__}")
        return 0

    from PySide6.QtGui import QIcon
    from PySide6.QtWidgets import QApplication

    from pear.ui.main_window import MainWindow
    from pear.ui.theme import apply_theme

    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("PEAR")
    apply_theme(app)
    icon = app_icon()
    if icon is not None:
        app.setWindowIcon(icon)

    win = MainWindow()
    win.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
