"""
Thorlabs MCLS1 4-Channel Fiber-Coupled Laser Source — pyserial wrapper.

Protocol reference: Thorlabs MCLS Series Operating Manual, 18659-D02 Rev B.
Serial: 115200 8N1, no flow control. Commands lowercase, terminated with \\r.
Device echoes a ">" prompt after every accepted command.

The MCLS1 has a stateful "active channel" — most commands act on whichever
channel was most recently selected via `channel=n`. This wrapper hides that
by re-selecting the channel on every per-channel call.

Usage:
    with MCLS1("COM5") as laser:
        print(laser.id())
        laser.set_current(channel=1, current_mA=20.0)
        laser.set_enable(channel=1, on=True)
        laser.system_enable(True)
        print(laser.power(channel=1))
        laser.system_enable(False)
"""

from __future__ import annotations

import time
from contextlib import contextmanager
from dataclasses import dataclass

import serial


class MCLS1Error(RuntimeError):
    """Raised when the MCLS1 returns an error string or a malformed reply."""


@dataclass
class MCLS1Status:
    """Decoded status word (`statword`). Bit layout per Thorlabs convention:
    bits 0..3 = channel enables (1..4), bit 4 = system enable, bit 5 = interlock.
    Confirm against your unit; older firmware variants exist."""

    raw: int
    ch1_enabled: bool
    ch2_enabled: bool
    ch3_enabled: bool
    ch4_enabled: bool
    system_enabled: bool
    interlock_ok: bool


class MCLS1:
    """Serial driver for the Thorlabs MCLS1 multi-channel laser source."""

    BAUDRATE = 115200
    EOL = b"\r"
    PROMPT = b">"
    NUM_CHANNELS = 4

    def __init__(self, port: str, timeout: float = 1.0):
        self.port = port
        self.timeout = timeout
        self._ser: serial.Serial | None = None
        self._active_channel: int | None = None

    # ---- connection ----

    def open(self) -> None:
        self._ser = serial.Serial(
            port=self.port,
            baudrate=self.BAUDRATE,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=self.timeout,
            xonxoff=False,
            rtscts=False,
            dsrdtr=False,
        )
        # Drain any stale boot banner / prompt.
        time.sleep(0.05)
        self._ser.reset_input_buffer()
        self._ser.reset_output_buffer()

    def close(self) -> None:
        if self._ser is not None:
            try:
                # Best-effort: leave the system disabled on disconnect.
                try:
                    self.system_enable(False)
                except Exception:
                    pass
            finally:
                self._ser.close()
                self._ser = None

    def __enter__(self) -> "MCLS1":
        self.open()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    # ---- low-level I/O ----

    def _write(self, line: str) -> None:
        if self._ser is None:
            raise MCLS1Error("Port not open. Call open() or use as context manager.")
        payload = line.strip().encode("ascii") + self.EOL
        self._ser.reset_input_buffer()
        self._ser.write(payload)
        self._ser.flush()

    def _read_response(self) -> str:
        """Read until the '>' prompt. Strip the echoed command and prompt.
        Returns the body of the response (may be empty for set commands)."""
        if self._ser is None:
            raise MCLS1Error("Port not open.")
        buf = bytearray()
        deadline = time.monotonic() + self.timeout * 4
        while time.monotonic() < deadline:
            chunk = self._ser.read(64)
            if chunk:
                buf.extend(chunk)
                if self.PROMPT in buf:
                    break
            else:
                if buf:
                    # We got something but no prompt — give it one more beat.
                    time.sleep(0.02)
        text = buf.decode("ascii", errors="replace")
        # Drop the trailing prompt and any whitespace.
        text = text.split(">")[0]
        # Lines come back as: <echoed cmd>\r\n<reply>\r\n
        lines = [ln.strip() for ln in text.replace("\r", "\n").split("\n") if ln.strip()]
        if not lines:
            return ""
        # First line is usually the echoed command; drop it.
        if "=" in lines[0] or "?" in lines[0] or lines[0] in {"save", "statword"}:
            lines = lines[1:]
        body = "\n".join(lines).strip()
        if "error" in body.lower() or "cmd_not_defined" in body.lower():
            raise MCLS1Error(f"Device error: {body!r}")
        return body

    def query(self, keyword: str) -> str:
        """Send `keyword?` and return the response body."""
        self._write(f"{keyword}?")
        return self._read_response()

    def command(self, keyword: str, value: int | float | str | None = None) -> str:
        """Send `keyword=value` (or bare keyword for action commands)."""
        if value is None:
            self._write(keyword)
        else:
            self._write(f"{keyword}={value}")
        return self._read_response()

    # ---- channel selection ----

    def _select_channel(self, channel: int) -> None:
        if not 1 <= channel <= self.NUM_CHANNELS:
            raise ValueError(f"channel must be 1..{self.NUM_CHANNELS}, got {channel}")
        if self._active_channel != channel:
            self.command("channel", channel)
            self._active_channel = channel

    # ---- commands (mirror manual section 6.3) ----

    def list_commands(self) -> str:
        """`?` — list available commands."""
        return self.query("")

    def id(self) -> str:
        """`id?` — model number and firmware version."""
        return self.query("id")

    def get_channel(self) -> int:
        """`channel?` — currently active channel."""
        return int(self.query("channel").strip().split()[-1])

    def set_channel(self, channel: int) -> None:
        """`channel=n` — set active channel."""
        self._select_channel(channel)

    def get_target(self, channel: int) -> float:
        """`target?` — target temperature for given channel (°C)."""
        self._select_channel(channel)
        return float(self.query("target").strip().split()[-1])

    def set_target(self, channel: int, temp_C: float) -> None:
        """`target=n` — set target temperature (20.00–30.00 °C)."""
        if not 20.0 <= temp_C <= 30.0:
            raise ValueError("target temperature out of range (20.00–30.00 °C)")
        self._select_channel(channel)
        self.command("target", f"{temp_C:.2f}")

    def temperature(self, channel: int) -> float:
        """`temp?` — actual temperature for given channel (°C)."""
        self._select_channel(channel)
        return float(self.query("temp").strip().split()[-1])

    def get_current(self, channel: int) -> float:
        """`current?` — drive current for given channel (mA)."""
        self._select_channel(channel)
        return float(self.query("current").strip().split()[-1])

    def set_current(self, channel: int, current_mA: float) -> None:
        """`current=n` — set drive current (mA)."""
        if current_mA < 0:
            raise ValueError("current_mA must be non-negative")
        self._select_channel(channel)
        self.command("current", f"{current_mA:.2f}")

    def power(self, channel: int) -> float:
        """`power?` — optical power for given channel (mW)."""
        self._select_channel(channel)
        return float(self.query("power").strip().split()[-1])

    def get_enable(self, channel: int) -> bool:
        """`enable?` — channel enable state."""
        self._select_channel(channel)
        return self.query("enable").strip().endswith("1")

    def set_enable(self, channel: int, on: bool) -> None:
        """`enable=n` — enable/disable a channel (does not turn laser on alone;
        the system master enable must also be set)."""
        self._select_channel(channel)
        self.command("enable", 1 if on else 0)

    def get_system(self) -> bool:
        """`system?` — master system enable state."""
        return self.query("system").strip().endswith("1")

    def system_enable(self, on: bool) -> None:
        """`system=n` — master system enable. Lasers turn on ~3 s after this
        is set, on whichever channels have their per-channel enable set."""
        self.command("system", 1 if on else 0)

    def specs(self, channel: int) -> str:
        """`specs?` — laser diode specifications for the active channel."""
        self._select_channel(channel)
        return self.query("specs")

    def get_step(self) -> float:
        """`step?` — arrow-key increment."""
        return float(self.query("step").strip().split()[-1])

    def set_step(self, value: float) -> None:
        """`step=n` — set arrow-key increment."""
        self.command("step", value)

    def save(self) -> None:
        """`save` — persist current settings."""
        self.command("save")

    def status(self) -> MCLS1Status:
        """`statword` — decoded status word.
        NOTE: bit layout assumed; verify against your firmware before relying on it."""
        raw_str = self.query("statword").strip().split()[-1]
        try:
            raw = int(raw_str, 0)  # accept dec or 0x-prefixed hex
        except ValueError:
            raise MCLS1Error(f"could not parse statword: {raw_str!r}")
        return MCLS1Status(
            raw=raw,
            ch1_enabled=bool(raw & 0x01),
            ch2_enabled=bool(raw & 0x02),
            ch3_enabled=bool(raw & 0x04),
            ch4_enabled=bool(raw & 0x08),
            system_enabled=bool(raw & 0x10),
            interlock_ok=bool(raw & 0x20),
        )

    # ---- convenience ----

    @contextmanager
    def laser_on(self, channel: int):
        """Context manager: enable a channel + system, guarantee shutdown on exit."""
        self.set_enable(channel, True)
        self.system_enable(True)
        try:
            yield
        finally:
            self.system_enable(False)
            self.set_enable(channel, False)


if __name__ == "__main__":
    # Smoke test — adjust COM port for your system.
    import sys

    port = sys.argv[1] if len(sys.argv) > 1 else "COM5"
    with MCLS1(port) as laser:
        print("ID:", laser.id())
        print("Active channel:", laser.get_channel())
        for ch in range(1, 5):
            try:
                t = laser.temperature(ch)
                tgt = laser.get_target(ch)
                i = laser.get_current(ch)
                print(f"  Ch{ch}: T={t:.2f}°C (target {tgt:.2f}), I={i:.2f} mA")
            except MCLS1Error as e:
                print(f"  Ch{ch}: error — {e}")
