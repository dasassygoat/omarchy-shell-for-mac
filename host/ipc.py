"""Socket IPC compatible with Omarchy's `omarchy-shell` client protocol.

Request:  target \\x1f method \\x1f arg... \\x1e
Reply:    OK \\x1f output \\x1e     when the call ran
          SKIP \\x1e               when nothing matched (unknown target/method,
                                  wrong argument count)

The server does not dispatch itself; it emits `requested` and the QML shell
answers through `IpcRegistry.call(...)` then calls `reply(...)`.
"""

import os
import socket
import sys
import tempfile
import uuid

from PySide6.QtCore import QObject, Signal, Slot
from PySide6.QtNetwork import QLocalServer, QLocalSocket

RS = b"\x1e"
US = b"\x1f"


def socket_path():
    override = os.environ.get("OMARCHY_SHELL_MAC_SOCKET")
    if override:
        return override
    return os.path.join(tempfile.gettempdir(), "omarchy-shell-mac.sock")


class IpcServer(QObject):
    requested = Signal(str, str, str, "QVariantList")

    def __init__(self, path, parent=None):
        super().__init__(parent)
        self._path = path
        self._pending = {}
        self._buffers = {}
        QLocalServer.removeServer(path)
        self._server = QLocalServer(self)
        self._server.newConnection.connect(self._accept)
        if not self._server.listen(path):
            sys.stderr.write(f"omarchy-shell-mac: ipc listen failed on {path}: {self._server.errorString()}\n")
        else:
            try:
                os.chmod(path, 0o600)
            except OSError:
                pass

    @property
    def path(self):
        return self._path

    def _accept(self):
        while self._server.hasPendingConnections():
            sock = self._server.nextPendingConnection()
            self._buffers[sock] = bytearray()
            sock.readyRead.connect(lambda s=sock: self._read(s))
            sock.disconnected.connect(lambda s=sock: self._buffers.pop(s, None))

    def _read(self, sock):
        buf = self._buffers.get(sock)
        if buf is None:
            return
        buf.extend(bytes(sock.readAll()))
        idx = buf.find(RS)
        if idx < 0:
            return
        raw = bytes(buf[:idx])
        del buf[: idx + 1]
        fields = [f.decode("utf-8", "replace") for f in raw.split(US)] if raw else []
        if len(fields) < 2:
            self._send(sock, b"SKIP" + RS)
            return
        request_id = uuid.uuid4().hex
        self._pending[request_id] = sock
        self.requested.emit(request_id, fields[0], fields[1], fields[2:])

    def _send(self, sock, payload):
        sock.write(payload)
        sock.flush()
        sock.disconnectFromServer()

    @Slot(str, bool, str)
    def reply(self, request_id, ran, output):
        sock = self._pending.pop(request_id, None)
        if sock is None:
            return
        if ran:
            self._send(sock, b"OK" + US + str(output).encode("utf-8") + RS)
        else:
            self._send(sock, b"SKIP" + RS)


def call(target, method, args, timeout=2.0):
    """Client side: returns (ran, output). Raises OSError if no shell answers."""
    request = US.join(s.encode("utf-8") for s in [target, method, *args]) + RS
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
        sock.settimeout(timeout)
        sock.connect(socket_path())
        sock.sendall(request)
        reply = bytearray()
        while RS not in reply:
            chunk = sock.recv(65536)
            if not chunk:
                break
            reply.extend(chunk)
    idx = reply.find(RS)
    body = bytes(reply[:idx]) if idx >= 0 else bytes(reply)
    if body.startswith(b"OK" + US):
        return True, body[3:].decode("utf-8", "replace")
    return False, ""
