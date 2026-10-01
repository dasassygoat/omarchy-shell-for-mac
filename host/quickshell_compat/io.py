"""`import Quickshell.Io` — Process, StdioCollector, SplitParser, FileView, IpcHandler.

These are thin wrappers over QProcess and QFile with Quickshell's property and
signal names, so Omarchy's QML drives them without knowing it left Linux.
"""

import os
import sys
import tempfile
from enum import IntEnum

from PySide6.QtCore import (
    Property,
    QByteArray,
    QEnum,
    QFileSystemWatcher,
    QObject,
    QProcess,
    QProcessEnvironment,
    QTimer,
    Signal,
    Slot,
)
from PySide6.QtQml import QJSValue, QmlElement, QmlUncreatable

QML_IMPORT_NAME = "Quickshell.Io"


def _plain(value):
    """Arrays and objects built at runtime in JS (concat, map, literals in
    functions) reach Python as QJSValue rather than list/dict; unwrap them."""
    if isinstance(value, QJSValue):
        return value.toVariant()
    return value
QML_IMPORT_MAJOR_VERSION = 1


def _warn(message):
    sys.stderr.write(f"quickshell-compat: {message}\n")


_reported_missing = set()


# --------------------------------------------------------------------------- #
# Output parsers
# --------------------------------------------------------------------------- #


@QmlElement
class StdioCollector(QObject):
    """Collects a whole stream; `text` is complete once `streamFinished` fires."""

    textChanged = Signal()
    dataChanged = Signal()
    waitForEndChanged = Signal()
    streamFinished = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._buffer = bytearray()
        self._waitForEnd = True
        self._text = ""

    def _feed(self, chunk):
        self._buffer.extend(bytes(chunk))
        if not self._waitForEnd:
            self._text = self._buffer.decode("utf-8", "replace")
            self.textChanged.emit()
            self.dataChanged.emit()

    def _finish(self):
        self._text = self._buffer.decode("utf-8", "replace")
        self.textChanged.emit()
        self.dataChanged.emit()
        self.streamFinished.emit()

    def _reset(self):
        self._buffer = bytearray()

    def _getText(self):
        return self._text

    def _getData(self):
        return QByteArray(bytes(self._buffer))

    def _getWaitForEnd(self):
        return self._waitForEnd

    def _setWaitForEnd(self, value):
        self._waitForEnd = bool(value)
        self.waitForEndChanged.emit()

    text = Property(str, _getText, notify=textChanged)
    data = Property(QByteArray, _getData, notify=dataChanged)
    waitForEnd = Property(bool, _getWaitForEnd, _setWaitForEnd, notify=waitForEndChanged)


@QmlElement
class SplitParser(QObject):
    """Emits `read(segment)` for every complete `splitMarker`-delimited chunk."""

    splitMarkerChanged = Signal()
    read = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._marker = "\n"
        self._buffer = bytearray()

    def _feed(self, chunk):
        self._buffer.extend(bytes(chunk))
        marker = self._marker.encode("utf-8")
        if not marker:
            self.read.emit(self._buffer.decode("utf-8", "replace"))
            self._buffer = bytearray()
            return
        while True:
            idx = self._buffer.find(marker)
            if idx < 0:
                break
            segment = bytes(self._buffer[:idx])
            del self._buffer[: idx + len(marker)]
            self.read.emit(segment.decode("utf-8", "replace"))

    def _finish(self):
        if self._buffer:
            self.read.emit(bytes(self._buffer).decode("utf-8", "replace"))
            self._buffer = bytearray()

    def _reset(self):
        self._buffer = bytearray()

    def _getMarker(self):
        return self._marker

    def _setMarker(self, value):
        self._marker = str(value)
        self.splitMarkerChanged.emit()

    splitMarker = Property(str, _getMarker, _setMarker, notify=splitMarkerChanged)


# --------------------------------------------------------------------------- #
# Process
# --------------------------------------------------------------------------- #


@QmlElement
class Process(QObject):
    commandChanged = Signal()
    workingDirectoryChanged = Signal()
    environmentChanged = Signal()
    clearEnvironmentChanged = Signal()
    stdoutChanged = Signal()
    stderrChanged = Signal()
    stdinEnabledChanged = Signal()
    manageLifetimeChanged = Signal()
    runningChanged = Signal()
    processIdChanged = Signal()
    started = Signal()
    exited = Signal(int, int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._command = []
        self._cwd = ""
        self._env = {}
        self._clearEnv = False
        self._stdout = None
        self._stderr = None
        self._stdinEnabled = False
        self._manageLifetime = True
        self._proc = None

    # ---- lifecycle -------------------------------------------------------- #

    def _isRunning(self):
        return self._proc is not None and self._proc.state() != QProcess.ProcessState.NotRunning

    def _start(self):
        if self._isRunning():
            return
        if not self._command:
            _warn("Process: cannot start with an empty command")
            return
        proc = QProcess(self)
        proc.setProgram(str(self._command[0]))
        proc.setArguments([str(a) for a in self._command[1:]])
        if self._cwd:
            proc.setWorkingDirectory(self._cwd)
        env = QProcessEnvironment() if self._clearEnv else QProcessEnvironment.systemEnvironment()
        for key, value in (self._env or {}).items():
            if value is None:
                env.remove(str(key))
            else:
                env.insert(str(key), str(value))
        proc.setProcessEnvironment(env)
        proc.readyReadStandardOutput.connect(self._readStdout)
        proc.readyReadStandardError.connect(self._readStderr)
        proc.finished.connect(self._onFinished)
        proc.errorOccurred.connect(self._onError)
        proc.started.connect(self._onStarted)
        for collector in (self._stdout, self._stderr):
            if collector is not None and hasattr(collector, "_reset"):
                collector._reset()
        self._proc = proc
        proc.start()
        if not self._stdinEnabled:
            proc.closeWriteChannel()
        self.runningChanged.emit()

    def _stop(self):
        if not self._isRunning():
            return
        self._proc.terminate()

    def _onStarted(self):
        self.processIdChanged.emit()
        self.started.emit()

    def _readStdout(self):
        if self._proc is None:
            return
        data = bytes(self._proc.readAllStandardOutput())
        if self._stdout is not None and hasattr(self._stdout, "_feed"):
            self._stdout._feed(data)

    def _readStderr(self):
        if self._proc is None:
            return
        data = bytes(self._proc.readAllStandardError())
        if self._stderr is not None and hasattr(self._stderr, "_feed"):
            self._stderr._feed(data)

    def _onFinished(self, code, status):
        self._readStdout()
        self._readStderr()
        for collector in (self._stdout, self._stderr):
            if collector is not None and hasattr(collector, "_finish"):
                collector._finish()
        proc, self._proc = self._proc, None
        if proc is not None:
            proc.deleteLater()
        self.runningChanged.emit()
        self.processIdChanged.emit()
        self.exited.emit(int(code), int(getattr(status, "value", status)))

    def _onError(self, error):
        if error == QProcess.ProcessError.FailedToStart:
            program = str(self._command[0]) if self._command else ""
            if program not in _reported_missing:
                _reported_missing.add(program)
                _warn(f"Process failed to start (further failures of {program!r} are silent): {self._command}")
            proc, self._proc = self._proc, None
            if proc is not None:
                proc.deleteLater()
            self.runningChanged.emit()

    # ---- invokables ------------------------------------------------------- #

    @Slot(str)
    def write(self, data):
        if self._isRunning():
            self._proc.write(str(data).encode("utf-8"))

    @Slot(int)
    def signal(self, sig):
        if self._isRunning():
            os.kill(int(self._proc.processId()), int(sig))

    @Slot()
    def startDetached(self):
        if not self._command:
            return
        QProcess.startDetached(str(self._command[0]), [str(a) for a in self._command[1:]], self._cwd)

    # ---- properties ------------------------------------------------------- #

    def _getCommand(self):
        return list(self._command)

    def _setCommand(self, value):
        value = _plain(value)
        self._command = list(value or [])
        self.commandChanged.emit()

    def _getCwd(self):
        return self._cwd

    def _setCwd(self, value):
        self._cwd = str(value or "")
        self.workingDirectoryChanged.emit()

    def _getEnv(self):
        return dict(self._env)

    def _setEnv(self, value):
        value = _plain(value)
        self._env = dict(value or {})
        self.environmentChanged.emit()

    def _getClearEnv(self):
        return self._clearEnv

    def _setClearEnv(self, value):
        self._clearEnv = bool(value)
        self.clearEnvironmentChanged.emit()

    def _getStdout(self):
        return self._stdout

    def _setStdout(self, value):
        self._stdout = value
        self.stdoutChanged.emit()

    def _getStderr(self):
        return self._stderr

    def _setStderr(self, value):
        self._stderr = value
        self.stderrChanged.emit()

    def _getStdinEnabled(self):
        return self._stdinEnabled

    def _setStdinEnabled(self, value):
        value = bool(value)
        changed = value != self._stdinEnabled
        self._stdinEnabled = value
        # Quickshell semantics: turning stdin off on a running process closes
        # its stdin, which is how plugins signal end-of-input after write().
        if not value and self._isRunning():
            self._proc.closeWriteChannel()
        if changed:
            self.stdinEnabledChanged.emit()

    def _getManageLifetime(self):
        return self._manageLifetime

    def _setManageLifetime(self, value):
        self._manageLifetime = bool(value)
        self.manageLifetimeChanged.emit()

    def _getRunning(self):
        return self._isRunning()

    def _setRunning(self, value):
        if bool(value):
            self._start()
        else:
            self._stop()

    def _getProcessId(self):
        return int(self._proc.processId()) if self._isRunning() else 0

    command = Property("QVariantList", _getCommand, _setCommand, notify=commandChanged)
    workingDirectory = Property(str, _getCwd, _setCwd, notify=workingDirectoryChanged)
    environment = Property("QVariantMap", _getEnv, _setEnv, notify=environmentChanged)
    clearEnvironment = Property(bool, _getClearEnv, _setClearEnv, notify=clearEnvironmentChanged)
    stdout = Property(QObject, _getStdout, _setStdout, notify=stdoutChanged)
    stderr = Property(QObject, _getStderr, _setStderr, notify=stderrChanged)
    stdinEnabled = Property(bool, _getStdinEnabled, _setStdinEnabled, notify=stdinEnabledChanged)
    manageLifetime = Property(bool, _getManageLifetime, _setManageLifetime, notify=manageLifetimeChanged)
    running = Property(bool, _getRunning, _setRunning, notify=runningChanged)
    processId = Property(int, _getProcessId, notify=processIdChanged)


# --------------------------------------------------------------------------- #
# FileView
# --------------------------------------------------------------------------- #


@QmlElement
@QmlUncreatable("FileViewError is an enum holder")
class FileViewError(QObject):
    @QEnum
    class Enum(IntEnum):
        Success = 0
        Unknown = 1
        NotFound = 2
        PermissionDenied = 3
        NotAFile = 4


@QmlElement
class FileView(QObject):
    """Loads a file's contents; optionally watches it and writes it back.

    Matches Quickshell semantics that Omarchy relies on: `loaded` after a read,
    `loadFailed(error)` when the read fails, `fileChanged` when a watched path
    changes on disk (the caller decides whether to `reload()`), and `saved`
    after `setText()`.
    """

    pathChanged = Signal()
    watchChangesChanged = Signal()
    blockLoadingChanged = Signal()
    preloadChanged = Signal()
    printErrorsChanged = Signal()
    atomicWritesChanged = Signal()
    textChanged = Signal()
    loaded = Signal()
    loadFailed = Signal(int)
    fileChanged = Signal()
    saved = Signal()
    saveFailed = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._path = ""
        self._watch = False
        self._blockLoading = False
        self._preload = True
        self._printErrors = True
        self._atomicWrites = False
        self._bytes = b""
        self._watcher = None
        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(60)
        self._debounce.timeout.connect(self._onWatchedChange)
        self._lastMtime = None

    # ---- loading ---------------------------------------------------------- #

    def _errorFor(self, exc):
        if isinstance(exc, FileNotFoundError):
            return int(FileViewError.Enum.NotFound)
        if isinstance(exc, PermissionError):
            return int(FileViewError.Enum.PermissionDenied)
        if isinstance(exc, IsADirectoryError):
            return int(FileViewError.Enum.NotAFile)
        return int(FileViewError.Enum.Unknown)

    def _load(self):
        if not self._path:
            return
        try:
            with open(self._path, "rb") as fh:
                self._bytes = fh.read()
            try:
                self._lastMtime = os.stat(self._path).st_mtime_ns
            except OSError:
                self._lastMtime = None
        except OSError as exc:
            code = self._errorFor(exc)
            if self._printErrors:
                _warn(f"FileView: failed to load {self._path}: {exc}")
            self.loadFailed.emit(code)
            return
        self.textChanged.emit()
        self.loaded.emit()

    def _scheduleLoad(self):
        if self._blockLoading:
            self._load()
        else:
            QTimer.singleShot(0, self._load)

    @Slot()
    def reload(self):
        self._load()

    @Slot()
    def waitForJob(self):
        pass

    @Slot(result=str)
    def text(self):
        return self._bytes.decode("utf-8", "replace")

    @Slot(result=QByteArray)
    def data(self):
        return QByteArray(self._bytes)

    @Slot(str)
    def setText(self, value):
        self._write(str(value).encode("utf-8"))

    @Slot(QByteArray)
    def setData(self, value):
        self._write(bytes(value))

    def _write(self, payload):
        if not self._path:
            return
        try:
            directory = os.path.dirname(self._path) or "."
            os.makedirs(directory, exist_ok=True)
            if self._atomicWrites:
                fd, tmp = tempfile.mkstemp(prefix=".fileview-", dir=directory)
                with os.fdopen(fd, "wb") as fh:
                    fh.write(payload)
                os.replace(tmp, self._path)
            else:
                with open(self._path, "wb") as fh:
                    fh.write(payload)
        except OSError as exc:
            if self._printErrors:
                _warn(f"FileView: failed to save {self._path}: {exc}")
            self.saveFailed.emit(self._errorFor(exc))
            return
        self._bytes = payload
        try:
            self._lastMtime = os.stat(self._path).st_mtime_ns
        except OSError:
            self._lastMtime = None
        self.textChanged.emit()
        self.saved.emit()
        self._rearmWatcher()

    # ---- watching --------------------------------------------------------- #

    def _rearmWatcher(self):
        if self._watcher is None:
            return
        for p in self._watcher.files():
            self._watcher.removePath(p)
        for p in self._watcher.directories():
            self._watcher.removePath(p)
        if not self._path:
            return
        if os.path.exists(self._path):
            self._watcher.addPath(self._path)
        directory = os.path.dirname(self._path) or "."
        if os.path.isdir(directory):
            self._watcher.addPath(directory)

    def _setupWatcher(self):
        if self._watch and self._watcher is None:
            self._watcher = QFileSystemWatcher(self)
            self._watcher.fileChanged.connect(lambda _p: self._debounce.start())
            self._watcher.directoryChanged.connect(lambda _p: self._debounce.start())
        elif not self._watch and self._watcher is not None:
            self._watcher.deleteLater()
            self._watcher = None
        self._rearmWatcher()

    def _onWatchedChange(self):
        self._rearmWatcher()
        try:
            mtime = os.stat(self._path).st_mtime_ns if self._path else None
        except OSError:
            mtime = None
        if mtime == self._lastMtime:
            return
        self._lastMtime = mtime
        self.fileChanged.emit()

    # ---- properties ------------------------------------------------------- #

    def _getPath(self):
        return self._path

    def _setPath(self, value):
        value = str(value or "")
        if value.startswith("file://"):
            value = value[len("file://"):]
        if value == self._path:
            return
        self._path = value
        self.pathChanged.emit()
        self._setupWatcher()
        if self._preload:
            self._scheduleLoad()

    def _getWatch(self):
        return self._watch

    def _setWatch(self, value):
        self._watch = bool(value)
        self.watchChangesChanged.emit()
        self._setupWatcher()

    def _getBlockLoading(self):
        return self._blockLoading

    def _setBlockLoading(self, value):
        self._blockLoading = bool(value)
        self.blockLoadingChanged.emit()

    def _getPreload(self):
        return self._preload

    def _setPreload(self, value):
        self._preload = bool(value)
        self.preloadChanged.emit()

    def _getPrintErrors(self):
        return self._printErrors

    def _setPrintErrors(self, value):
        self._printErrors = bool(value)
        self.printErrorsChanged.emit()

    def _getAtomicWrites(self):
        return self._atomicWrites

    def _setAtomicWrites(self, value):
        self._atomicWrites = bool(value)
        self.atomicWritesChanged.emit()

    path = Property(str, _getPath, _setPath, notify=pathChanged)
    watchChanges = Property(bool, _getWatch, _setWatch, notify=watchChangesChanged)
    blockLoading = Property(bool, _getBlockLoading, _setBlockLoading, notify=blockLoadingChanged)
    preload = Property(bool, _getPreload, _setPreload, notify=preloadChanged)
    printErrors = Property(bool, _getPrintErrors, _setPrintErrors, notify=printErrorsChanged)
    atomicWrites = Property(bool, _getAtomicWrites, _setAtomicWrites, notify=atomicWritesChanged)


# --------------------------------------------------------------------------- #
# IpcHandler
# --------------------------------------------------------------------------- #


# Every live IpcHandler, so the shell can answer a socket call for a plain
# `IpcHandler` the way `qs ipc call` would. Omarchy's ShellIpc subclass also
# registers with qs.Commons.IpcRegistry; third-party plugins often use the
# bare type.
_live_handlers = []


def live_ipc_handlers():
    return [h for h in _live_handlers if h is not None]


@QmlElement
class IpcHandler(QObject):
    """A named IPC target. Functions declared on it in QML become callable
    over the host's socket (see `host/ipc.py` and qs.Commons.IpcRegistry)."""

    targetChanged = Signal()
    enabledChanged = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._target = ""
        self._enabled = True
        _live_handlers.append(self)
        self.destroyed.connect(lambda *_: _live_handlers.remove(self) if self in _live_handlers else None)

    def _getTarget(self):
        return self._target

    def _setTarget(self, value):
        value = str(value or "")
        if value == self._target:
            return
        self._target = value
        self.targetChanged.emit()

    def _getEnabled(self):
        return self._enabled

    def _setEnabled(self, value):
        value = bool(value)
        if value == self._enabled:
            return
        self._enabled = value
        self.enabledChanged.emit()

    target = Property(str, _getTarget, _setTarget, notify=targetChanged)
    enabled = Property(bool, _getEnabled, _setEnabled, notify=enabledChanged)
