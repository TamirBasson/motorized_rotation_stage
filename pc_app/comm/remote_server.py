from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
import queue
import socket
import threading
import time
from typing import Any
from uuid import uuid4

from pc_app.comm.communication_manager import (
    CommunicationError,
    CommunicationManager,
    DeviceErrorResponse,
    ResponseTimeoutError,
)
from pc_app.comm.models import AckMessage, TelemetryState
from pc_app.comm.protocol import build_set_telemetry_rate_command
from pc_app.comm.remote_protocol import (
    decode_message,
    encode_message,
    serialize_ack,
    serialize_err,
    serialize_telemetry,
)
from pc_app.comm.telemetry_bus import TelemetrySubscription


DEFAULT_SERVER_HOST = "127.0.0.1"
DEFAULT_SERVER_PORT = 8765


@dataclass(slots=True)
class _QueuedCommand:
    session_id: str
    request_id: str
    command_line: str
    timeout: float
    command_name: str


@dataclass(slots=True)
class _ServerSession:
    server: RemoteCommunicationServer
    client_socket: socket.socket
    address: tuple[str, int]
    session_id: str = field(default_factory=lambda: str(uuid4()))
    initialized: bool = False
    client_type: str = "unknown"
    client_name: str = ""
    _send_queue: queue.Queue[dict[str, Any] | None] = field(default_factory=queue.Queue)
    _closed: threading.Event = field(default_factory=threading.Event)
    _writer_thread: threading.Thread | None = None
    _reader_thread: threading.Thread | None = None

    def start(self) -> None:
        self._writer_thread = threading.Thread(
            target=self._writer_loop,
            name=f"rotation-stage-remote-writer-{self.session_id}",
            daemon=True,
        )
        self._reader_thread = threading.Thread(
            target=self._reader_loop,
            name=f"rotation-stage-remote-reader-{self.session_id}",
            daemon=True,
        )
        self._writer_thread.start()
        self._reader_thread.start()

    def send(self, message: dict[str, Any]) -> None:
        if self._closed.is_set():
            return
        self._send_queue.put(message)

    def close(self) -> None:
        if self._closed.is_set():
            return
        self._closed.set()
        try:
            self.client_socket.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        try:
            self.client_socket.close()
        except OSError:
            pass
        self._send_queue.put(None)

    def _writer_loop(self) -> None:
        while True:
            message = self._send_queue.get()
            if message is None:
                return
            try:
                self.client_socket.sendall(encode_message(message))
            except OSError:
                self.close()
                return

    def _reader_loop(self) -> None:
        try:
            file_handle = self.client_socket.makefile("r", encoding="utf-8", newline="\n")
            with file_handle:
                for raw_line in file_handle:
                    if self._closed.is_set():
                        break
                    try:
                        message = decode_message(raw_line)
                    except Exception as exc:
                        self.send(
                            {
                                "type": "event",
                                "event": "protocol_error",
                                "message": f"Invalid JSON message: {exc}",
                            }
                        )
                        continue
                    self.server._handle_client_message(self, message)
        except OSError:
            pass
        finally:
            self.server._handle_session_closed(self)
            self.close()


class RemoteCommunicationServer:
    """Cross-process communication server that is the only serial owner."""

    def __init__(
        self,
        manager: CommunicationManager,
        *,
        host: str = DEFAULT_SERVER_HOST,
        port: int = DEFAULT_SERVER_PORT,
        connect_settle_seconds: float = 0.0,
    ) -> None:
        self._manager = manager
        self._host = host
        self._port = port
        self._connect_settle_seconds = max(connect_settle_seconds, 0.0)

        self._sessions_lock = threading.RLock()
        self._sessions: dict[str, _ServerSession] = {}
        self._telemetry_preferences: dict[str, int] = {}
        self._current_effective_telemetry_rate_hz: int | None = None
        self._virtual_zero_offset_deg: float | None = None
        self._api_control_owner_session_id: str | None = None
        self._queued_commands: deque[_QueuedCommand] = deque()
        self._queue_condition = threading.Condition(self._sessions_lock)

        self._telemetry_subscription: TelemetrySubscription | None = None
        self._listener_socket: socket.socket | None = None
        self._accept_thread: threading.Thread | None = None
        self._queue_worker_thread: threading.Thread | None = None
        self._running = threading.Event()

    @classmethod
    def from_serial_port(
        cls,
        *,
        port: str,
        baudrate: int = 115200,
        read_timeout: float = 0.1,
        write_timeout: float = 1.0,
        host: str = DEFAULT_SERVER_HOST,
        server_port: int = DEFAULT_SERVER_PORT,
        connect_settle_seconds: float = 2.5,
    ) -> RemoteCommunicationServer:
        return cls(
            CommunicationManager(
                port=port,
                baudrate=baudrate,
                read_timeout=read_timeout,
                write_timeout=write_timeout,
            ),
            host=host,
            port=server_port,
            connect_settle_seconds=connect_settle_seconds,
        )

    @classmethod
    def from_simulator(
        cls,
        *,
        port: str = "SIMULATED_CONTROLLER",
        baudrate: int = 115200,
        read_timeout: float = 0.05,
        write_timeout: float = 1.0,
        host: str = DEFAULT_SERVER_HOST,
        server_port: int = DEFAULT_SERVER_PORT,
        simulator_config: Any = None,
    ) -> RemoteCommunicationServer:
        from pc_app.sim.controller_simulator import build_simulated_serial_factory

        return cls(
            CommunicationManager(
                port=port,
                baudrate=baudrate,
                read_timeout=read_timeout,
                write_timeout=write_timeout,
                serial_factory=build_simulated_serial_factory(simulator_config),
            ),
            host=host,
            port=server_port,
        )

    @property
    def host(self) -> str:
        return self._host

    @property
    def port(self) -> int:
        return self._port

    def start(self) -> None:
        if self._running.is_set():
            return

        self._manager.start()
        try:
            if self._connect_settle_seconds > 0:
                time.sleep(self._connect_settle_seconds)
            self._telemetry_subscription = self._manager.subscribe_telemetry(
                self._handle_telemetry,
                replay_latest=True,
                priority="high",
            )

            listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            listener.bind((self._host, self._port))
            listener.listen()
            self._port = int(listener.getsockname()[1])
            self._listener_socket = listener
            self._running.set()

            self._accept_thread = threading.Thread(
                target=self._accept_loop,
                name="rotation-stage-remote-accept",
                daemon=True,
            )
            self._queue_worker_thread = threading.Thread(
                target=self._queue_worker_loop,
                name="rotation-stage-remote-queue-worker",
                daemon=True,
            )
            self._accept_thread.start()
            self._queue_worker_thread.start()
        except Exception:
            if self._telemetry_subscription is not None:
                self._telemetry_subscription.unsubscribe()
                self._telemetry_subscription = None
            self._manager.stop()
            raise

    def stop(self) -> None:
        if not self._running.is_set():
            return

        self._running.clear()

        listener = self._listener_socket
        self._listener_socket = None
        if listener is not None:
            try:
                listener.close()
            except OSError:
                pass

        if self._telemetry_subscription is not None:
            self._telemetry_subscription.unsubscribe()
            self._telemetry_subscription = None

        with self._queue_condition:
            sessions = list(self._sessions.values())
            self._sessions.clear()
            self._queued_commands.clear()
            self._api_control_owner_session_id = None
            self._telemetry_preferences.clear()
            self._queue_condition.notify_all()

        for session in sessions:
            session.close()

        if self._accept_thread is not None:
            self._accept_thread.join(timeout=1.0)
            self._accept_thread = None
        if self._queue_worker_thread is not None:
            self._queue_worker_thread.join(timeout=1.0)
            self._queue_worker_thread = None

        self._manager.stop()

    def _accept_loop(self) -> None:
        listener = self._listener_socket
        if listener is None:
            return

        while self._running.is_set():
            try:
                client_socket, address = listener.accept()
            except OSError:
                return
            session = _ServerSession(server=self, client_socket=client_socket, address=address)
            session.start()

    def _handle_client_message(self, session: _ServerSession, message: dict[str, Any]) -> None:
        if message.get("type") != "request":
            session.send(
                self._build_error_response(
                    request_id=str(message.get("request_id", "")),
                    kind="protocol",
                    message_text="Only request messages are accepted",
                )
            )
            return

        request_id = str(message.get("request_id", ""))
        action = str(message.get("action", ""))

        if not session.initialized:
            if action != "hello":
                session.send(self._build_error_response(request_id=request_id, kind="protocol", message_text="hello required"))
                return
            self._handle_hello(session, request_id=request_id, message=message)
            return

        if action == "send_command":
            self._handle_send_command(session, request_id=request_id, message=message)
            return
        if action == "get_latest_telemetry":
            latest = self._manager.get_latest_telemetry()
            session.send(
                {
                    "type": "response",
                    "request_id": request_id,
                    "status": "ok",
                    "result": {"telemetry": serialize_telemetry(latest)} if latest is not None else {"telemetry": None},
                }
            )
            return
        if action == "get_virtual_zero_offset":
            session.send(
                {
                    "type": "response",
                    "request_id": request_id,
                    "status": "ok",
                    "result": {"virtual_zero_offset_deg": self._virtual_zero_offset_deg},
                }
            )
            return
        if action == "set_telemetry_rate":
            self._handle_set_telemetry_rate(session, request_id=request_id, message=message)
            return
        if action == "acquire_api_control":
            self._handle_acquire_api_control(session, request_id=request_id)
            return
        if action == "release_api_control":
            self._handle_release_api_control(session, request_id=request_id)
            return

        session.send(
            self._build_error_response(
                request_id=request_id,
                kind="protocol",
                message_text=f"Unsupported action {action!r}",
            )
        )

    def _handle_hello(self, session: _ServerSession, *, request_id: str, message: dict[str, Any]) -> None:
        client_type = str(message.get("client_type", ""))
        if client_type not in {"ui", "api"}:
            session.send(
                self._build_error_response(
                    request_id=request_id,
                    kind="protocol",
                    message_text="client_type must be 'ui' or 'api'",
                )
            )
            return

        session.client_type = client_type
        session.client_name = str(message.get("client_name", "")).strip() or client_type.upper()
        session.initialized = True
        with self._queue_condition:
            self._sessions[session.session_id] = session
        latest = self._manager.get_latest_telemetry()
        session.send(
            {
                "type": "response",
                "request_id": request_id,
                "status": "ok",
                "result": {
                    "session_id": session.session_id,
                    "server_host": self._host,
                    "server_port": self._port,
                    "latest_telemetry": serialize_telemetry(latest) if latest is not None else None,
                    "virtual_zero_offset_deg": self._virtual_zero_offset_deg,
                    "control_state": self._build_control_state_payload(),
                },
            }
        )

    def _handle_send_command(self, session: _ServerSession, *, request_id: str, message: dict[str, Any]) -> None:
        command_line = str(message.get("command_line", ""))
        timeout = float(message.get("timeout", 1.0))
        command_name = _extract_command_name(command_line)
        if command_name is None:
            session.send(
                self._build_error_response(
                    request_id=request_id,
                    kind="protocol",
                    message_text="Invalid command_line",
                )
            )
            return

        if self._should_queue_command(session, command_name):
            with self._queue_condition:
                self._queued_commands.append(
                    _QueuedCommand(
                        session_id=session.session_id,
                        request_id=request_id,
                        command_line=command_line,
                        timeout=timeout,
                        command_name=command_name,
                    )
                )
                queue_position = len(self._queued_commands)
                self._queue_condition.notify_all()
            session.send(
                {
                    "type": "response",
                    "request_id": request_id,
                    "status": "queued",
                    "command_name": command_name,
                    "queue_position": queue_position,
                    "message": "Command queued until the API releases control.",
                }
            )
            self._broadcast_control_state()
            return

        session.send(self._execute_command_response(command_line=command_line, timeout=timeout, request_id=request_id))

    def _handle_set_telemetry_rate(self, session: _ServerSession, *, request_id: str, message: dict[str, Any]) -> None:
        requested_rate_hz = int(message.get("rate_hz", 0))
        with self._queue_condition:
            self._telemetry_preferences[session.session_id] = requested_rate_hz
            desired_rate_hz = _select_effective_telemetry_rate(self._telemetry_preferences.values())

        if desired_rate_hz == self._current_effective_telemetry_rate_hz:
            ack = AckMessage(command_type="TLM", parameters=(str(desired_rate_hz),))
            session.send(
                {
                    "type": "response",
                    "request_id": request_id,
                    "status": "ok",
                    "result": {
                        "ack": serialize_ack(ack),
                        "effective_rate_hz": desired_rate_hz,
                    },
                }
            )
            return

        response = self._execute_command_response(
            command_line=build_set_telemetry_rate_command(desired_rate_hz),
            timeout=float(message.get("timeout", 1.0)),
            request_id=request_id,
        )
        if response["status"] == "ok":
            self._current_effective_telemetry_rate_hz = desired_rate_hz
            response["result"]["effective_rate_hz"] = desired_rate_hz
        session.send(response)

    def _handle_acquire_api_control(self, session: _ServerSession, *, request_id: str) -> None:
        if session.client_type != "api":
            session.send(
                self._build_error_response(
                    request_id=request_id,
                    kind="protocol",
                    message_text="Only API clients may acquire control",
                )
            )
            return

        with self._queue_condition:
            owner_session_id = self._api_control_owner_session_id
            if owner_session_id is None or owner_session_id == session.session_id:
                self._api_control_owner_session_id = session.session_id
                result = self._build_control_state_payload()
            else:
                owner = self._sessions.get(owner_session_id)
                owner_name = owner.client_name if owner is not None else owner_session_id
                session.send(
                    self._build_error_response(
                        request_id=request_id,
                        kind="communication",
                        message_text=f"API control is already held by {owner_name}",
                    )
                )
                return

        session.send(
            {
                "type": "response",
                "request_id": request_id,
                "status": "ok",
                "result": result,
            }
        )
        self._broadcast_control_state()

    def _handle_release_api_control(self, session: _ServerSession, *, request_id: str) -> None:
        with self._queue_condition:
            if self._api_control_owner_session_id == session.session_id:
                self._api_control_owner_session_id = None
                self._queue_condition.notify_all()
            result = self._build_control_state_payload()

        session.send(
            {
                "type": "response",
                "request_id": request_id,
                "status": "ok",
                "result": result,
            }
        )
        self._broadcast_control_state()

    def _handle_session_closed(self, session: _ServerSession) -> None:
        with self._queue_condition:
            self._sessions.pop(session.session_id, None)
            telemetry_preferences_changed = self._telemetry_preferences.pop(session.session_id, None) is not None
            if self._api_control_owner_session_id == session.session_id:
                self._api_control_owner_session_id = None
            self._queued_commands = deque(
                queued_command
                for queued_command in self._queued_commands
                if queued_command.session_id != session.session_id
            )
            self._queue_condition.notify_all()
            desired_rate_hz = _select_effective_telemetry_rate(self._telemetry_preferences.values())

        if telemetry_preferences_changed and desired_rate_hz != self._current_effective_telemetry_rate_hz:
            try:
                self._manager.send_command(build_set_telemetry_rate_command(desired_rate_hz), timeout=1.0)
            except CommunicationError:
                pass
            else:
                self._current_effective_telemetry_rate_hz = desired_rate_hz

        self._broadcast_control_state()

    def _handle_telemetry(self, telemetry: TelemetryState) -> None:
        event = {
            "type": "event",
            "event": "telemetry",
            "telemetry": serialize_telemetry(telemetry),
        }
        with self._sessions_lock:
            sessions = list(self._sessions.values())
        for session in sessions:
            session.send(event)

    def _queue_worker_loop(self) -> None:
        while self._running.is_set():
            with self._queue_condition:
                self._queue_condition.wait_for(
                    lambda: not self._running.is_set()
                    or (
                        self._queued_commands
                        and self._api_control_owner_session_id is None
                    )
                )
                if not self._running.is_set():
                    return
                queued_command = self._queued_commands.popleft()
                session = self._sessions.get(queued_command.session_id)

            if session is None:
                continue

            response = self._execute_command_response(
                command_line=queued_command.command_line,
                timeout=queued_command.timeout,
                request_id=queued_command.request_id,
            )
            if response["status"] == "ok":
                session.send(
                    {
                        "type": "event",
                        "event": "queued_command_executed",
                        "request_id": queued_command.request_id,
                        "ack": response["result"]["ack"],
                    }
                )
            else:
                session.send(
                    {
                        "type": "event",
                        "event": "queued_command_failed",
                        "request_id": queued_command.request_id,
                        "error": response.get("error", {}),
                    }
                )
            self._broadcast_control_state()

    def _execute_command_response(self, *, command_line: str, timeout: float, request_id: str) -> dict[str, Any]:
        try:
            ack = self._manager.send_command(command_line, timeout=timeout)
        except DeviceErrorResponse as exc:
            return {
                "type": "response",
                "request_id": request_id,
                "status": "error",
                "error": {
                    "kind": "device",
                    "message": str(exc),
                    "device_error": serialize_err(exc.error),
                },
            }
        except ResponseTimeoutError as exc:
            return self._build_error_response(request_id=request_id, kind="timeout", message_text=str(exc))
        except CommunicationError as exc:
            return self._build_error_response(request_id=request_id, kind="communication", message_text=str(exc))

        self._update_server_state_from_command(command_line)
        return {
            "type": "response",
            "request_id": request_id,
            "status": "ok",
            "result": {"ack": serialize_ack(ack)},
        }

    def _should_queue_command(self, session: _ServerSession, command_name: str) -> bool:
        with self._sessions_lock:
            return (
                session.client_type == "ui"
                and self._api_control_owner_session_id is not None
                and command_name not in {"STOP", "TLM"}
            )

    def _update_server_state_from_command(self, command_line: str) -> None:
        parts = command_line.strip().split(",")
        if len(parts) < 2:
            return
        command_name = parts[1]
        if command_name == "ROT_ABS" and len(parts) >= 4:
            self._virtual_zero_offset_deg = float(parts[3])
        elif command_name == "ROT_VZERO" and len(parts) >= 3:
            self._virtual_zero_offset_deg = float(parts[2])

    def _broadcast_control_state(self) -> None:
        payload = {
            "type": "event",
            "event": "control_state",
            "control_state": self._build_control_state_payload(),
        }
        with self._sessions_lock:
            sessions = list(self._sessions.values())
        for session in sessions:
            session.send(payload)

    def _build_control_state_payload(self) -> dict[str, Any]:
        with self._sessions_lock:
            owner_session_id = self._api_control_owner_session_id
            owner_name = self._sessions[owner_session_id].client_name if owner_session_id in self._sessions else None
            return {
                "api_control_active": owner_session_id is not None,
                "api_control_owner_session_id": owner_session_id,
                "api_control_owner_name": owner_name,
                "queued_ui_command_count": len(self._queued_commands),
            }

    @staticmethod
    def _build_error_response(*, request_id: str, kind: str, message_text: str) -> dict[str, Any]:
        return {
            "type": "response",
            "request_id": request_id,
            "status": "error",
            "error": {
                "kind": kind,
                "message": message_text,
            },
        }


def _select_effective_telemetry_rate(requested_rates: Any) -> int:
    rates = [int(rate) for rate in requested_rates]
    if not rates:
        return 0
    if -1 in rates:
        return -1
    return max(rates)


def _extract_command_name(command_line: str) -> str | None:
    parts = command_line.strip().split(",")
    if len(parts) < 2 or parts[0] != "CMD":
        return None
    return parts[1]
