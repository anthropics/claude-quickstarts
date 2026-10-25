"""Local RFB peers exercise constructor cleanup without a desktop or model."""

import base64
import io
import socket
import struct
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from unittest.mock import Mock

import pytest
from anthropic.types.beta import BetaComputerScreenshotInput
from PIL import Image
from vnc_computer import VncComputer


def receive(peer, count):
    data = b""
    while len(data) < count:
        chunk = peer.recv(count - len(data))
        assert chunk, "client closed before completing the handshake"
        data += chunk
    return data


@contextmanager
def server(handler):
    with socket.socket() as listener, ThreadPoolExecutor(max_workers=1) as executor:
        listener.bind(("127.0.0.1", 0))
        listener.listen(1)
        listener.settimeout(3)

        def serve():
            with listener.accept()[0] as peer:
                peer.settimeout(3)
                return handler(peer)

        result = executor.submit(serve)
        yield listener.getsockname()[1], result
        result.result(timeout=5)


def handshake(peer, *, version=b"RFB 003.008\n", width=2, height=1, failure=None):
    peer.sendall(version)
    assert receive(peer, 12) == version
    peer.sendall(b"\x01\x01")
    assert receive(peer, 1) == b"\x01"
    if version == b"RFB 003.008\n":
        peer.sendall(struct.pack(">I", 1 if failure == "refused" else 0))
        if failure == "refused":
            return
    assert receive(peer, 1) == b"\x01"
    if failure == "truncated":
        peer.sendall(b"\x00")
        peer.shutdown(socket.SHUT_WR)
        return
    peer.sendall(struct.pack(">HH16xI", width, height, 4) + b"test")
    receive(peer, 28)  # SetPixelFormat and SetEncodings.


def failed_instance(error):
    trace = error.__traceback__
    while trace:
        instance = trace.tb_frame.f_locals.get("self")
        if isinstance(instance, VncComputer):
            return instance
        trace = trace.tb_next
    raise AssertionError("constructor traceback did not retain the driver")


@pytest.mark.parametrize(
    "options, message",
    [
        ({"failure": "refused"}, "refused the connection"),
        ({"failure": "truncated"}, "closed the connection"),
        ({"width": 1921}, "lower it to"),
        ({"height": 1201}, "lower it to"),
    ],
)
def test_failed_initialization_closes_resources_with_traceback_retained(options, message):
    def handle(peer):
        handshake(peer, **options)
        return peer.recv(1)

    with server(handle) as (port, result):
        with pytest.raises(RuntimeError, match=message) as caught:
            VncComputer(port=port, confirm=lambda context: True)
        instance = failed_instance(caught.value)
        try:
            assert instance._stream.closed
            assert instance._socket.fileno() == -1
            assert result.result(timeout=3) == b""
            assert caught.value.__traceback__ is not None
        finally:
            instance.close()  # Also release the unpatched baseline after a failed assertion.


@pytest.mark.parametrize("version", [b"RFB 003.007\n", b"RFB 003.008\n"])
def test_successful_connection_stays_open_until_closed(version):
    def handle(peer):
        handshake(peer, version=version)
        return peer.recv(1)

    with server(handle) as (port, result):
        with VncComputer(port=port, confirm=lambda context: True) as computer:
            assert (computer.width, computer.height) == (2, 1)
            assert not computer._stream.closed
            assert computer._socket.fileno() != -1
        assert result.result(timeout=3) == b""


def test_raw_frame_still_decodes_to_png():
    def handle(peer):
        handshake(peer)
        assert receive(peer, 10) == struct.pack(">BBHHHH", 3, 0, 0, 0, 2, 1)
        peer.sendall(struct.pack(">BBHHHHHi", 0, 0, 1, 0, 0, 2, 1, 0) + b"\xff\0\0\0\0\xff\0\0")
        return peer.recv(1)

    with server(handle) as (port, result):
        with VncComputer(port=port, confirm=lambda context: True) as computer:
            image = computer.screenshot(None, BetaComputerScreenshotInput())
            with Image.open(io.BytesIO(base64.b64decode(image.data))) as png:
                assert png.size == (2, 1)
                assert png.getpixel((0, 0)) == (255, 0, 0)
                assert png.getpixel((1, 0)) == (0, 255, 0)
        assert result.result(timeout=3) == b""


def test_makefile_failure_closes_the_socket(monkeypatch):
    connection = Mock()
    failure = OSError("cannot create buffered reader")
    connection.makefile.side_effect = failure
    monkeypatch.setattr(socket, "create_connection", lambda *args, **kwargs: connection)

    with pytest.raises(OSError) as caught:
        VncComputer(confirm=lambda context: True)

    assert caught.value is failure
    connection.close.assert_called_once()


@pytest.mark.parametrize("failure", [RuntimeError("handshake failed"), KeyboardInterrupt()])
def test_failed_initialization_preserves_original_error_if_reader_close_fails(monkeypatch, failure):
    connection = Mock()
    connection.makefile.return_value.close.side_effect = OSError("close failed")
    monkeypatch.setattr(socket, "create_connection", lambda *args, **kwargs: connection)

    def fail(self):
        raise failure

    monkeypatch.setattr(VncComputer, "_handshake", fail)
    with pytest.raises(type(failure)) as caught:
        VncComputer(confirm=lambda context: True)

    assert caught.value is failure
    connection.makefile.return_value.close.assert_called_once()
    connection.close.assert_called_once()
