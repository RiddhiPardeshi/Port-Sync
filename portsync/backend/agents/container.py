"""
container.py — Member 1
Container Agent: tracks vessel ETA via AIS, detects shifts,
fires RENEGOTIATE event to orchestrator.
"""

from datetime import datetime, timedelta
from typing import Optional
import asyncio
import logging

logger = logging.getLogger("container_agent")


class ContainerAgent:
    def __init__(self, container_id: str, vessel_name: str, booked_eta: str):
        self.container_id = container_id
        self.vessel_name = vessel_name
        self.booked_eta = self._parse_time(booked_eta)
        self.current_eta = self.booked_eta
        self.status = "WAITING"           # WAITING | RENEGOTIATING | SLOT_CONFIRMED
        self.shift_threshold_min = 30     # trigger renegotiation if ETA shifts > 30 min
        self.log: list[dict] = []

    def _parse_time(self, t: str) -> datetime:
        today = datetime.now().date()
        h, m = map(int, t.split(":"))
        return datetime(today.year, today.month, today.day, h, m)

    def _fmt(self, dt: datetime) -> str:
        return dt.strftime("%H:%M")

    def update_eta(self, new_eta_str: str) -> Optional[dict]:
        """
        Called by AIS service when vessel position updates.
        Returns a RENEGOTIATE event if shift > threshold, else None.
        """
        new_eta = self._parse_time(new_eta_str)
        shift_minutes = (new_eta - self.current_eta).total_seconds() / 60

        msg = f"Container {self.container_id} | ETA update: {self._fmt(self.current_eta)} → {self._fmt(new_eta)} (shift: {shift_minutes:+.0f} min)"
        self._log("INFO", msg)
        logger.info(msg)

        self.current_eta = new_eta

        if abs(shift_minutes) >= self.shift_threshold_min and self.status == "WAITING":
            self.status = "RENEGOTIATING"
            event = {
                "type": "RENEGOTIATE",
                "agent": "container",
                "container_id": self.container_id,
                "vessel_name": self.vessel_name,
                "old_eta": self._fmt(self.booked_eta),
                "new_eta": self._fmt(new_eta),
                "shift_minutes": int(shift_minutes),
                "message": f"ETA shifted {shift_minutes:+.0f} min — renegotiating slot",
            }
            self._log("ALERT", event["message"])
            return event

        return None

    def confirm_slot(self, slot_start: str, slot_end: str, gate: int):
        self.status = "SLOT_CONFIRMED"
        msg = f"Slot confirmed: Gate {gate} | {slot_start}–{slot_end}"
        self._log("SUCCESS", msg)
        logger.info(msg)

    def _log(self, level: str, message: str):
        self.log.append({
            "agent": "container",
            "level": level,
            "message": message,
            "timestamp": datetime.now().strftime("%H:%M:%S"),
        })

    def get_state(self) -> dict:
        return {
            "container_id": self.container_id,
            "vessel_name": self.vessel_name,
            "booked_eta": self._fmt(self.booked_eta),
            "current_eta": self._fmt(self.current_eta),
            "status": self.status,
            "shift_min": int((self.current_eta - self.booked_eta).total_seconds() / 60),
        }
