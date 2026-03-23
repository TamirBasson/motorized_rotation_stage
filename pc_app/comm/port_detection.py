from __future__ import annotations

from dataclasses import dataclass

from pc_app.comm.communication_manager import CommunicationError

try:
    from serial.tools import list_ports  # pyright: ignore[reportMissingImports,reportMissingModuleSource]
except ImportError:  # pragma: no cover - exercised only when pyserial is missing.
    list_ports = None


@dataclass(frozen=True, slots=True)
class SerialPortCandidate:
    device: str
    description: str
    manufacturer: str
    hwid: str


def auto_detect_controller_port() -> str:
    """Return the most likely controller serial port.

    Detection is best-effort: if there is exactly one strong candidate it is
    returned automatically; otherwise an explicit error is raised so the caller
    can request a manual port selection.
    """

    candidates = list_serial_ports()
    if not candidates:
        raise CommunicationError("No serial ports detected. Plug in the controller and try again.")

    ranked = sorted(
        ((_score_candidate(candidate), candidate) for candidate in candidates),
        key=lambda item: item[0],
        reverse=True,
    )
    best_score = ranked[0][0]
    strongest = [candidate for score, candidate in ranked if score == best_score]

    if best_score > 0 and len(strongest) == 1:
        return strongest[0].device
    if len(candidates) == 1:
        return candidates[0].device

    available_ports = ", ".join(candidate.device for candidate in candidates)
    raise CommunicationError(
        "Could not uniquely auto-detect the controller serial port. "
        f"Available ports: {available_ports}. Please specify the port explicitly."
    )


def list_serial_ports() -> list[SerialPortCandidate]:
    if list_ports is None:
        raise CommunicationError("pyserial is required to detect serial ports")

    return [
        SerialPortCandidate(
            device=port.device,
            description=getattr(port, "description", "") or "",
            manufacturer=getattr(port, "manufacturer", "") or "",
            hwid=getattr(port, "hwid", "") or "",
        )
        for port in list_ports.comports()
    ]


def _score_candidate(candidate: SerialPortCandidate) -> int:
    haystack = " ".join(
        [candidate.device, candidate.description, candidate.manufacturer, candidate.hwid]
    ).lower()
    score = 0

    strong_markers = (
        "arduino",
        "ch340",
        "cp210",
        "silicon labs",
        "usb serial",
        "usb-serial",
        "wch",
    )
    medium_markers = (
        "ttyacm",
        "ttyusb",
        "usb",
        "serial",
    )

    for marker in strong_markers:
        if marker in haystack:
            score += 10
    for marker in medium_markers:
        if marker in haystack:
            score += 2
    return score
