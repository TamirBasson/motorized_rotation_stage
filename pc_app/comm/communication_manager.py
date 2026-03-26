from __future__ import annotations

import threading
from collections import deque
from typing import TYPE_CHECKING, Any, Callable, Protocol

from pc_app.comm.models import AckMessage, ErrMessage, ParsedInboundMessage, TelemetryState
from pc_app.comm.protocol import ProtocolError, parse_message
from pc_app.comm.telemetry_bus import TelemetryBus, TelemetrySubscription

try:
    import serial
    from serial import SerialException
except ImportError:  # pragma: no cover - exercised only when pyserial is missing.
    serial = None

    class SerialException(Exception):
        pass


if TYPE_CHECKING:
    from serial import Serial


class SerialLike(Protocol):
    def readline(self) -> bytes: ...

    def write(self, payload: bytes) -> int: ...

    def flush(self) -> None: ...

    def close(self) -> None: ...


SerialFactory = Callable[..., SerialLike]


class CommunicationError(RuntimeError):
    """Raised when the communication layer cannot complete an operation."""


class DeviceErrorResponse(CommunicationError):
    """Raised when the controller responds with an ERR message."""

    def __init__(self, error: ErrMessage) -> None:
        super().__init__(f"{error.error_code}: {error.details}")
        self.error = error


class ResponseTimeoutError(CommunicationError):
    """Raised when no ACK or ERR is received in time."""


class CommunicationManager:
    """Single serial owner for all PC-side communication."""

    _owned_ports: set[str] = set()
    _owned_ports_lock = threading.Lock()

    def __init__(
        self,
        port: str,
        baudrate: int = 115200,
        *,
        read_timeout: float = 0.1,
        write_timeout: float = 1.0,
        serial_factory: SerialFactory | None = None,
    ) -> None:
        self._port = port
        self._baudrate = baudrate
        self._read_timeout = read_timeout
        self._write_timeout = write_timeout
        self._serial_factory = serial_factory

        self._serial: SerialLike | None = None
        self._reader_thread: threading.Thread | None = None
        self._running = threading.Event()

        self._command_lock = threading.Lock()
        self._response_condition = threading.Condition()
        self._awaiting_response = False
        self._pending_response: AckMessage | ErrMessage | None = None

        self._telemetry_lock = threading.Lock()
        self._latest_telemetry: TelemetryState | None = None
        self._telemetry_bus = TelemetryBus()

        self._last_ack: AckMessage | None = None
        self._last_error: ErrMessage | None = None
        self._last_protocol_error: str | None = None
        self._async_messages: deque[AckMessage | ErrMessage] = deque()

    @property
    def port(self) -> str:
        return self._port

    def start(self) -> None:
        if self._running.is_set():
            return
        if self._serial_factory is None and serial is None:
            raise CommunicationError("pyserial is required to use the communication manager")

        self._claim_port()
        try:
            serial_factory = self._serial_factory or _default_serial_factory
            self._serial = serial_factory(
                port=self._port,
                baudrate=self._baudrate,
                timeout=self._read_timeout,
                write_timeout=self._write_timeout,
            )
        except Exception:
            self._release_port()
            raise

        self._running.set()
        self._reader_thread = threading.Thread(
            target=self._reader_loop,
            name="rotation-stage-serial-reader",
            daemon=True,
        )
        self._reader_thread.start()

    def stop(self) -> None:
        self._running.clear()
        if self._reader_thread is not None:
            self._reader_thread.join(timeout=1.0)
            self._reader_thread = None

        serial_handle = self._serial
        self._serial = None
        if serial_handle is not None:
            try:
                serial_handle.close()
            finally:
                self._release_port()
        else:
            self._release_port()

        with self._response_condition:
            self._awaiting_response = False
            self._pending_response = None
            self._response_condition.notify_all()

    def __enter__(self) -> CommunicationManager:
        self.start()
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        self.stop()

    def send_command(self, command_line: str, timeout: float = 1.0) -> AckMessage:
        if not command_line.startswith("CMD,"):
            raise CommunicationError("Outbound commands must start with 'CMD,'")

        serial_handle = self._require_serial()
        payload = f"{command_line}\n".encode("ascii")

        with self._command_lock:
            with self._response_condition:
                self._awaiting_response = True
                self._pending_response = None

            try:
                serial_handle.write(payload)
                serial_handle.flush()
            except Exception as exc:
                with self._response_condition:
                    self._awaiting_response = False
                    self._pending_response = None
                    self._response_condition.notify_all()
                raise CommunicationError(f"Failed to write to serial port {self._port}") from exc

            response = self._wait_for_response(timeout=timeout)
            if isinstance(response, ErrMessage):
                self._last_error = response
                raise DeviceErrorResponse(response)

            self._last_ack = response
            return response

    def get_latest_telemetry(self) -> TelemetryState | None:
        with self._telemetry_lock:
            return self._latest_telemetry

    def subscribe_telemetry(
        self,
        callback: Callable[[TelemetryState], None],
        *,
        replay_latest: bool = True,
    ) -> TelemetrySubscription:
        subscription = self._telemetry_bus.subscribe(callback)
        if replay_latest:
            latest = self.get_latest_telemetry()
            if latest is not None:
                callback(latest)
        return subscription

    def get_last_ack(self) -> AckMessage | None:
        return self._last_ack

    def get_last_error(self) -> ErrMessage | None:
        return self._last_error

    def get_last_protocol_error(self) -> str | None:
        return self._last_protocol_error

    def drain_async_messages(self) -> list[AckMessage | ErrMessage]:
        with self._response_condition:
            messages = list(self._async_messages)
            self._async_messages.clear()
            return messages

    def _reader_loop(self) -> None:
        while self._running.is_set():
            serial_handle = self._serial
            if serial_handle is None:
                return

            try:
                raw_line = serial_handle.readline()
            except SerialException as exc:
                self._last_protocol_error = f"Serial read failed: {exc}"
                self._running.clear()
                with self._response_condition:
                    self._awaiting_response = False
                    self._pending_response = None
                    self._response_condition.notify_all()
                return

            if not raw_line:
                continue

            try:
                parsed = parse_message(raw_line.decode("ascii"))
            except (UnicodeDecodeError, ProtocolError) as exc:
                self._last_protocol_error = str(exc)
                continue

            if isinstance(parsed, TelemetryState):
                with self._telemetry_lock:
                    self._latest_telemetry = parsed
                self._telemetry_bus.publish(parsed)
                continue

            self._handle_response(parsed)

    def _handle_response(self, message: AckMessage | ErrMessage) -> None:
        if isinstance(message, AckMessage):
            self._last_ack = message
        else:
            self._last_error = message

        with self._response_condition:
            if self._awaiting_response and self._pending_response is None:
                self._pending_response = message
                self._response_condition.notify_all()
            else:
                self._async_messages.append(message)

    def _wait_for_response(self, timeout: float) -> AckMessage | ErrMessage:
        with self._response_condition:
            received = self._response_condition.wait_for(
                lambda: self._pending_response is not None or not self._running.is_set(),
                timeout=timeout,
            )
            response = self._pending_response
            self._awaiting_response = False
            self._pending_response = None

            if response is None:
                if not received or not self._running.is_set():
                    raise ResponseTimeoutError(
                        f"No ACK or ERR received within {timeout:.2f}s for command on {self._port}"
                    )
                raise CommunicationError("Communication manager stopped while waiting for a response")
            return response

    def _require_serial(self) -> SerialLike:
        serial_handle = self._serial
        if serial_handle is None or not self._running.is_set():
            raise CommunicationError("Communication manager is not started")
        return serial_handle

    def _claim_port(self) -> None:
        with self._owned_ports_lock:
            if self._port in self._owned_ports:
                raise CommunicationError(f"Serial port {self._port} is already owned by a manager")
            self._owned_ports.add(self._port)

    def _release_port(self) -> None:
        with self._owned_ports_lock:
            self._owned_ports.discard(self._port)


def _default_serial_factory(*args: Any, **kwargs: Any) -> Serial:
    return serial.Serial(*args, **kwargs)
