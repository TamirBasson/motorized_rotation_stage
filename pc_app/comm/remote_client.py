from __future__ import annotations

from dataclasses import dataclass
import socket
import threading
from typing import Any, Callable
from uuid import uuid4

from pc_app.comm.communication_manager import CommunicationError, DeviceErrorResponse, ResponseTimeoutError
from pc_app.comm.models import AckMessage, ErrMessage, TelemetryState
from pc_app.comm.remote_protocol import (
    decode_message,
    deserialize_ack,
    deserialize_err,
    deserialize_telemetry,
    encode_message,
)
from pc_app.comm.remote_server import DEFAULT_SERVER_HOST, DEFAULT_SERVER_PORT
from pc_app.comm.telemetry_bus import TelemetryBus, TelemetryPriority, TelemetrySubscription


class CommandQueuedError(CommunicationError):
    def __init__(self, command_name: str, queue_position: int, message: str) -> None:
        super().__init__(message)
        self.command_name = command_name
        self.queue_position = queue_position


@dataclass(slots=True)
class _PendingResponse:
    event: threading.Event
    response: dict[str, Any] | None = None


class RemoteCommunicationClient:
    """Client for the shared localhost communication server."""

    def __init__(
        self,
        *,
        host: str = DEFAULT_SERVER_HOST,
        port: int = DEFAULT_SERVER_PORT,
        client_type: str,
        client_name: str,
        auto_acquire_control: bool = False,
        connect_timeout: float = 2.0,
    ) -> None:
        if client_type not in {"ui", "api"}:
            raise ValueError("client_type must be 'ui' or 'api'")

        self._host = host
        self._port = port
        self._client_type = client_type
        self._client_name = client_name
        self._auto_acquire_control = auto_acquire_control
        self._connect_timeout = connect_timeout

        self._socket: socket.socket | None = None
        self._reader_thread: threading.Thread | None = None
        self._running = threading.Event()
        self._send_lock = threading.Lock()
        self._pending_lock = threading.Lock()
        self._pending: dict[str, _PendingResponse] = {}
        self._telemetry_bus = TelemetryBus()
        self._latest_telemetry_lock = threading.Lock()
        self._latest_telemetry: TelemetryState | None = None
        self._virtual_zero_offset_deg: float | None = None
        self._control_state_lock = threading.Lock()
        self._control_state: dict[str, Any] = {}
        self._session_id: str | None = None
        self._control_lease_held = False

    def start(self) -> None:
        if self._running.is_set():
            return

        try:
            self._socket = socket.create_connection((self._host, self._port), timeout=self._connect_timeout)
            self._socket.settimeout(None)
        except OSError as exc:
            raise CommunicationError(
                f"Could not connect to shared communication server at {self._host}:{self._port}"
            ) from exc

        self._running.set()
        self._reader_thread = threading.Thread(
            target=self._reader_loop,
            name=f"rotation-stage-remote-client-{self._client_type}",
            daemon=True,
        )
        self._reader_thread.start()

        try:
            result = self._send_request(
                action="hello",
                payload={
                    "client_type": self._client_type,
                    "client_name": self._client_name,
                },
                timeout=self._connect_timeout,
            )
        except Exception:
            self.stop()
            raise
        hello_result = result["result"]
        self._session_id = str(hello_result["session_id"])
        latest = hello_result.get("latest_telemetry")
        if latest is not None:
            telemetry = deserialize_telemetry(latest)
            with self._latest_telemetry_lock:
                self._latest_telemetry = telemetry
        self._virtual_zero_offset_deg = hello_result.get("virtual_zero_offset_deg")
        with self._control_state_lock:
            self._control_state = dict(hello_result.get("control_state", {}))

        if self._auto_acquire_control and self._client_type == "api":
            self.acquire_control()

    def stop(self) -> None:
        if not self._running.is_set():
            return

        if self._control_lease_held:
            try:
                self.release_control(timeout=1.0)
            except CommunicationError:
                pass

        self._running.clear()
        socket_handle = self._socket
        self._socket = None
        if socket_handle is not None:
            try:
                socket_handle.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            try:
                socket_handle.close()
            except OSError:
                pass

        if self._reader_thread is not None:
            self._reader_thread.join(timeout=1.0)
            self._reader_thread = None

        self._fail_pending_requests(CommunicationError("Remote communication client stopped"))

    def send_command(self, command_line: str, timeout: float = 1.0) -> AckMessage:
        response = self._send_request(
            action="send_command",
            payload={
                "command_line": command_line,
                "timeout": timeout,
            },
            timeout=timeout + 2.0,
        )
        if response["status"] == "queued":
            raise CommandQueuedError(
                command_name=str(response.get("command_name", "UNKNOWN")),
                queue_position=int(response.get("queue_position", 0)),
                message=str(response.get("message", "Command queued")),
            )

        ack = deserialize_ack(response["result"]["ack"])
        self._update_virtual_zero_from_command(command_line)
        return ack

    def set_telemetry_rate(self, rate_hz: int, *, timeout: float = 1.0) -> AckMessage:
        response = self._send_request(
            action="set_telemetry_rate",
            payload={
                "rate_hz": rate_hz,
                "timeout": timeout,
            },
            timeout=timeout + 2.0,
        )
        return deserialize_ack(response["result"]["ack"])

    def get_latest_telemetry(self) -> TelemetryState | None:
        with self._latest_telemetry_lock:
            return self._latest_telemetry

    def subscribe_telemetry(
        self,
        callback: Callable[[TelemetryState], None],
        *,
        replay_latest: bool = True,
        priority: TelemetryPriority = "high",
    ) -> TelemetrySubscription:
        subscription = self._telemetry_bus.subscribe(callback, priority=priority)
        if replay_latest:
            latest = self.get_latest_telemetry()
            if latest is not None:
                callback(latest)
        return subscription

    def get_virtual_zero_offset_deg(self) -> float | None:
        return self._virtual_zero_offset_deg

    def acquire_control(self, *, timeout: float = 1.0) -> dict[str, Any]:
        response = self._send_request(action="acquire_api_control", payload={}, timeout=timeout + 1.0)
        self._update_control_state(response["result"])
        return response["result"]

    def release_control(self, *, timeout: float = 1.0) -> dict[str, Any]:
        response = self._send_request(action="release_api_control", payload={}, timeout=timeout + 1.0)
        self._update_control_state(response["result"])
        return response["result"]

    def get_control_state(self) -> dict[str, Any]:
        with self._control_state_lock:
            return dict(self._control_state)

    def _send_request(self, *, action: str, payload: dict[str, Any], timeout: float) -> dict[str, Any]:
        if not self._running.is_set() or self._socket is None:
            raise CommunicationError("Remote communication client is not started")

        request_id = str(uuid4())
        pending = _PendingResponse(event=threading.Event())
        with self._pending_lock:
            self._pending[request_id] = pending

        message = {
            "type": "request",
            "request_id": request_id,
            "action": action,
            **payload,
        }
        try:
            with self._send_lock:
                if self._socket is None:
                    raise CommunicationError("Remote communication socket is unavailable")
                self._socket.sendall(encode_message(message))
        except OSError as exc:
            with self._pending_lock:
                self._pending.pop(request_id, None)
            raise CommunicationError("Failed to write to the shared communication server") from exc

        if not pending.event.wait(timeout):
            with self._pending_lock:
                self._pending.pop(request_id, None)
            raise ResponseTimeoutError(f"Remote request {action!r} timed out after {timeout:.2f}s")

        response = pending.response
        if response is None:
            raise CommunicationError("Remote request completed without a response")
        if response["status"] == "error":
            self._raise_remote_error(response["error"])
        return response

    def _reader_loop(self) -> None:
        socket_handle = self._socket
        if socket_handle is None:
            return

        try:
            file_handle = socket_handle.makefile("r", encoding="utf-8", newline="\n")
            with file_handle:
                for raw_line in file_handle:
                    if not self._running.is_set():
                        break
                    message = decode_message(raw_line)
                    message_type = message.get("type")
                    if message_type == "response":
                        self._handle_response_message(message)
                    elif message_type == "event":
                        self._handle_event_message(message)
        except OSError:
            pass
        finally:
            self._running.clear()
            self._fail_pending_requests(
                CommunicationError(
                    f"Disconnected from shared communication server at {self._host}:{self._port}"
                )
            )

    def _handle_response_message(self, message: dict[str, Any]) -> None:
        request_id = str(message.get("request_id", ""))
        with self._pending_lock:
            pending = self._pending.pop(request_id, None)
        if pending is None:
            return
        pending.response = message
        pending.event.set()

    def _handle_event_message(self, message: dict[str, Any]) -> None:
        event_type = str(message.get("event", ""))
        if event_type == "telemetry":
            telemetry = deserialize_telemetry(message["telemetry"])
            with self._latest_telemetry_lock:
                self._latest_telemetry = telemetry
            self._telemetry_bus.publish(telemetry)
            return
        if event_type == "control_state":
            self._update_control_state(message.get("control_state", {}))
            return

    def _update_control_state(self, control_state: dict[str, Any]) -> None:
        with self._control_state_lock:
            self._control_state = dict(control_state)
            owner_session_id = self._control_state.get("api_control_owner_session_id")
            self._control_lease_held = bool(owner_session_id) and owner_session_id == self._session_id

    def _update_virtual_zero_from_command(self, command_line: str) -> None:
        parts = command_line.strip().split(",")
        if len(parts) < 2:
            return
        if parts[1] == "ROT_ABS" and len(parts) >= 4:
            self._virtual_zero_offset_deg = float(parts[3])
        elif parts[1] == "ROT_VZERO" and len(parts) >= 3:
            self._virtual_zero_offset_deg = float(parts[2])

    def _raise_remote_error(self, payload: dict[str, Any]) -> None:
        kind = str(payload.get("kind", "communication"))
        message = str(payload.get("message", "Remote server error"))
        if kind == "device":
            raise DeviceErrorResponse(deserialize_err(payload["device_error"]))
        if kind == "timeout":
            raise ResponseTimeoutError(message)
        raise CommunicationError(message)

    def _fail_pending_requests(self, exc: Exception) -> None:
        with self._pending_lock:
            pending_items = list(self._pending.items())
            self._pending.clear()
        for _, pending in pending_items:
            pending.response = {
                "type": "response",
                "request_id": "",
                "status": "error",
                "error": {
                    "kind": "communication",
                    "message": str(exc),
                },
            }
            pending.event.set()
