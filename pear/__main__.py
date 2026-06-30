"""Entry point: ``python -m pear`` (and the ``pear`` console script)."""

from __future__ import annotations

import sys


def main() -> int:
    """Launch the PEAR desktop application."""
    # Import lazily so that importing the package (e.g. for ``--version``)
    # does not require a Qt display.
    if "--version" in sys.argv:
        from pear import __version__

        print(f"PEAR {__version__}")
        return 0

    from PySide6.QtWidgets import QApplication

    from pear.ui.main_window import MainWindow
    from pear.ui.theme import apply_theme

    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("PEAR")
    apply_theme(app)

    win = MainWindow()
    win.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
