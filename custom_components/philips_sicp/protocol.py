"""Low level SICP (Serial Interface Communication Protocol) transport.

Implements the framing described in "The SICP Commands Document V2.10",
chapter 2 (Command Packet Format). This is a from-scratch implementation
that talks TCP/IP directly - it does not depend on any third party
device library.

Frame layout::

    [MsgSize][Control][Group][Data0..DataN][Checksum]

- MsgSize: total number of bytes in the frame, including itself.
- Control: the Monitor ID being addressed (1-255), or 0 for broadcast.
- Group: the Group ID being addressed (1-254), or 0 to address by Monitor ID.
- Data[0] is the command code. Data[1..N] are command parameters.
- Checksum: XOR of every preceding byte (including MsgSize).

A single physical connection (TCP socket) can carry commands for many
Monitor IDs at once: displays that are RS232-daisy-chained from a
LAN-connected display are reached by addressing their Monitor ID over the
same socket, as long as "SICP Serial Port Forwarding" (chapter 7.4) is
enabled on the LAN-connected unit. Because of this, only one request may
be in flight on a connection at a time (the spec: "a new command should
not be sent until the previous command is acknowledged") - SICPClient
serializes all traffic for a given connection with a lock, independent of
how many Monitor IDs are being driven through it.
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass

_LOGGER = logging.getLogger(__name__)

DEFAULT_PORT = 5000
RESPONSE_TIMEOUT = 0.5  # seconds, per spec section 2.2
MAX_RETRIES = 2

ACK = 0x06
NACK = 0x15
NAV = 0x18

_STATUS_NAMES = {ACK: "ACK", NACK: "NACK", NAV: "NAV"}


class SICPError(Exception):
    """Base error for all SICP protocol failures."""


class SICPConnectionError(SICPError):
    """Could not talk to the display at all (socket/timeout)."""


class SICPChecksumError(SICPError):
    """Display replied with a NACK (checksum/format error)."""


class SICPNotAvailableError(SICPError):
    """Display replied with a NAV (command valid but not supported).

    This is the protocol's own "unsupported feature" signal and is used
    directly by the capability-detection logic in coordinator.py: a
    command that NAVs on a given display/platform/firmware simply isn't
    offered as an entity.
    """


@dataclass
class SICPReply:
    monitor_id: int
    group: int
    data: bytes


def _checksum(payload: bytes) -> int:
    value = 0
    for byte in payload:
        value ^= byte
    return value


def encode_frame(monitor_id: int, group: int, data: bytes) -> bytes:
    """Build a full SICP frame for the given target and command data."""
    if not 0 <= monitor_id <= 255:
        raise ValueError(f"monitor_id out of range: {monitor_id}")
    if not 0 <= group <= 254:
        raise ValueError(f"group out of range: {group}")
    body = bytes([monitor_id, group, *data])
    msg_size = len(body) + 2  # +1 for the MsgSize byte itself, +1 for checksum
    frame = bytes([msg_size]) + body
    checksum = _checksum(frame)
    return frame + bytes([checksum])


class _FrameReader:
    """Incrementally reassembles SICP frames out of a byte stream."""

    def __init__(self) -> None:
        self._buffer = bytearray()

    def feed(self, chunk: bytes) -> list[SICPReply]:
        self._buffer.extend(chunk)
        replies: list[SICPReply] = []
        while self._buffer:
            msg_size = self._buffer[0]
            if msg_size < 4:
                # Garbage/resync: drop one byte and try again.
                del self._buffer[0]
                continue
            if len(self._buffer) < msg_size:
                break
            frame = bytes(self._buffer[:msg_size])
            del self._buffer[:msg_size]
            expected = frame[-1]
            actual = _checksum(frame[:-1])
            if expected != actual:
                _LOGGER.debug(
                    "Dropping frame with bad checksum: %s (expected %02x got %02x)",
                    frame.hex(),
                    expected,
                    actual,
                )
                continue
            monitor_id = frame[1]
            group = frame[2]
            data = frame[3:-1]
            replies.append(SICPReply(monitor_id, group, data))
        return replies


@dataclass
class _PendingRequest:
    future: "asyncio.Future[SICPReply]"
    expect_code: int | None


class SICPClient:
    """One TCP connection to a (possibly daisy-chained) SICP display chain."""

    def __init__(self, host: str, port: int = DEFAULT_PORT) -> None:
        self._host = host
        self._port = port
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None
        self._frame_reader = _FrameReader()
        self._send_lock = asyncio.Lock()
        self._read_task: asyncio.Task | None = None
        self._pending: _PendingRequest | None = None
        self._closed = True

    @property
    def connected(self) -> bool:
        return not self._closed and self._writer is not None

    async def connect(self) -> None:
        self._reader, self._writer = await asyncio.open_connection(
            self._host, self._port
        )
        self._closed = False
        self._read_task = asyncio.create_task(self._read_loop())

    async def disconnect(self) -> None:
        self._closed = True
        if self._read_task is not None:
            self._read_task.cancel()
            self._read_task = None
        if self._writer is not None:
            self._writer.close()
            try:
                await self._writer.wait_closed()
            except (ConnectionError, OSError):
                pass
        self._reader = None
        self._writer = None

    async def _read_loop(self) -> None:
        assert self._reader is not None
        try:
            while True:
                chunk = await self._reader.read(4096)
                if not chunk:
                    self._fail_pending(SICPConnectionError("Connection closed"))
                    return
                for reply in self._frame_reader.feed(chunk):
                    self._dispatch(reply)
        except asyncio.CancelledError:
            raise
        except (ConnectionError, OSError) as err:
            self._fail_pending(SICPConnectionError(str(err)))

    def _fail_pending(self, err: Exception) -> None:
        if self._pending and not self._pending.future.done():
            self._pending.future.set_exception(err)

    def _dispatch(self, reply: SICPReply) -> None:
        if self._pending is None or self._pending.future.done():
            _LOGGER.debug("Unsolicited SICP reply ignored: %s", reply)
            return
        self._pending.future.set_result(reply)

    async def request(
        self,
        monitor_id: int,
        group: int,
        data: bytes,
        *,
        expect_code: int | None = None,
        retries: int = MAX_RETRIES,
    ) -> bytes:
        """Send one command and wait for its reply.

        For a Get command, pass expect_code=data[0]; the returned bytes
        are the report's Data[1:]. For a Set command, leave expect_code
        None; on success an empty bytes object is returned. Raises
        SICPNotAvailableError on NAV and SICPChecksumError on NACK.
        """
        if not self.connected or self._writer is None:
            raise SICPConnectionError("Not connected")

        frame = encode_frame(monitor_id, group, data)
        async with self._send_lock:
            last_err: Exception | None = None
            for attempt in range(retries + 1):
                loop = asyncio.get_running_loop()
                fut: asyncio.Future[SICPReply] = loop.create_future()
                self._pending = _PendingRequest(fut, expect_code)
                try:
                    self._writer.write(frame)
                    await self._writer.drain()
                    reply = await asyncio.wait_for(fut, RESPONSE_TIMEOUT)
                    return self._interpret(reply, expect_code)
                except asyncio.TimeoutError as err:
                    last_err = err
                    _LOGGER.debug(
                        "Timeout waiting for reply to %s (attempt %d/%d)",
                        frame.hex(),
                        attempt + 1,
                        retries + 1,
                    )
                    continue
                finally:
                    self._pending = None
            raise SICPConnectionError(
                f"No reply after {retries + 1} attempts"
            ) from last_err

    @staticmethod
    def _interpret(reply: SICPReply, expect_code: int | None) -> bytes:
        if reply.data and reply.data[0] == 0x00 and len(reply.data) >= 2:
            status = reply.data[1]
            if status == ACK:
                return b""
            if status == NAV:
                raise SICPNotAvailableError("Command not supported (NAV)")
            if status == NACK:
                raise SICPChecksumError("Checksum/format error (NACK)")
            # Some very old firmwares echo unknown status bytes; treat as
            # a hard failure rather than silently succeeding.
            raise SICPError(f"Unexpected status byte 0x{status:02X}")
        if expect_code is not None:
            if not reply.data or reply.data[0] != expect_code:
                raise SICPError(
                    f"Unexpected reply, wanted code 0x{expect_code:02X}: {reply.data!r}"
                )
            return reply.data[1:]
        return reply.data
