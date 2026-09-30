"""Offscreen smoke test for the Quickshell window types.

    QT_QPA_PLATFORM=offscreen .venv/bin/python tests/smoke_windows.py

Loads tests/smoke_windows.qml, which instantiates PanelWindow, Region masks,
QsWindow attached properties, the pristine OverlayWindow and PopupCard, and
prints their geometry. Exits non-zero if the document fails to load.
"""

import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QUICK_CONTROLS_STYLE", "Basic")

from PySide6.QtCore import QByteArray, QTimer, QUrl  # noqa: E402
from PySide6.QtGui import QGuiApplication  # noqa: E402

app = QGuiApplication([])
import host.quickshell_compat  # noqa: E402,F401

from PySide6.QtQml import QQmlApplicationEngine, QQmlComponent  # noqa: E402

engine = QQmlApplicationEngine()
engine.addImportPath(os.path.join(ROOT, "qml"))
engine.warnings.connect(lambda ws: [print("QMLWARN", w.toString(), flush=True) for w in ws])
component = QQmlComponent(engine)
with open(os.path.join(ROOT, "tests", "smoke_windows.qml"), "rb") as fh:
    component.setData(QByteArray(fh.read()), QUrl.fromLocalFile(os.path.join(ROOT, "tests", "smoke_windows.qml")))
root = component.create()
if root is None:
    for error in component.errors():
        print("ERR", error.toString(), flush=True)
    sys.exit(1)
engine.quit.connect(app.quit)
QTimer.singleShot(5000, app.quit)
app.exec()
print("smoke done", flush=True)
