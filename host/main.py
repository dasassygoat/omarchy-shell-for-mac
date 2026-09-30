"""Entry point: `python -m host.main [run | ipc <target> <method> [args...]]`."""

import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def run_shell(argv):
    os.environ.setdefault("QT_QUICK_CONTROLS_STYLE", "Basic")
    os.environ.setdefault("QS_SHELL_DIR", os.path.join(ROOT, "shell"))
    os.environ.setdefault("QS_SHELL_PATH", os.path.join(ROOT, "shell", "shell.qml"))

    from PySide6.QtCore import QUrl
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtQml import QQmlApplicationEngine

    app = QGuiApplication([sys.argv[0], *argv])
    app.setApplicationName("omarchy-shell-mac")
    app.setOrganizationName("omarchy-shell-mac")
    app.setQuitOnLastWindowClosed(False)

    from host import ipc  # noqa: WPS433
    from host.quickshell_compat import mac  # registers QML modules via package import

    mac.hide_from_dock()

    engine = QQmlApplicationEngine()
    engine.addImportPath(os.path.join(ROOT, "qml"))
    server = ipc.IpcServer(ipc.socket_path())
    engine.rootContext().setContextProperty("ipcServer", server)

    def on_warnings(warnings):
        for w in warnings:
            sys.stderr.write("qml: " + w.toString() + "\n")

    engine.warnings.connect(on_warnings)
    engine.objectCreationFailed.connect(lambda _url: sys.exit(1))
    engine.load(QUrl.fromLocalFile(os.path.join(ROOT, "shell", "shell.qml")))
    if not engine.rootObjects():
        sys.stderr.write("omarchy-shell-mac: failed to load shell/shell.qml\n")
        return 1
    sys.stderr.write(f"omarchy-shell-mac: running, ipc socket {server.path}\n")
    return app.exec()


def run_ipc(argv):
    quiet = False
    if argv and argv[0] == "-q":
        quiet = True
        argv = argv[1:]
    if len(argv) < 2:
        if not quiet:
            sys.stderr.write("usage: omarchy-shell [-q] <target> <method> [args...]\n")
        return 0 if quiet else 1
    target, method, args = argv[0], argv[1], argv[2:]
    if target == "shell" and method in ("summon", "toggle") and len(args) == 1:
        args = [*args, "{}"]
    from host import ipc

    try:
        ran, output = ipc.call(target, method, args)
    except OSError as exc:
        if not quiet:
            sys.stderr.write(f"omarchy-shell: no running shell ({exc})\n")
        return 0 if quiet else 1
    if not ran:
        if not quiet:
            sys.stderr.write(f"omarchy-shell: no handler for {target}.{method} with {len(args)} argument(s)\n")
        return 0 if quiet else 1
    if output and not quiet:
        sys.stdout.write(output if output.endswith("\n") else output + "\n")
    return 0


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == "ipc":
        return run_ipc(argv[1:])
    if argv and argv[0] == "run":
        argv = argv[1:]
    return run_shell(argv)


if __name__ == "__main__":
    sys.exit(main())
