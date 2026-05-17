"""
gate.py — Member 1
Gate Slot Agent: manages the port's slot pool, finds optimal
slots, resolves conflicts, pre-clears gate on arrival.
"""

from datetime import datetime, timedelta
from typing import Optional
import logging
import copy

logger = logging.getLogger("gate_agent")


class GateSlotAgent:
    def __init__(self, slots: list[dict]):
        # Deep copy so we don't mutate fixtures
        self.slots = copy.deepcopy(slots)
        self.log: list[dict] = []

    def find_next_available(self, after_time_str: str, gate: int = 4) -> Optional[dict]:
        """
        Finds the next available slot at the given gate after a time.
        Returns the slot dict or None.
        """
        after = self._parse_time(after_time_str)
        for slot in self.slots:
            if slot["gate"] != gate:
                continue
            if slot["status"] != "available":
                continue
            slot_start = self._parse_time(slot["start"])
            if slot_start >= after:
                msg = f"Found available slot: Gate {gate} | {slot['start']}–{slot['end']}"
                self._log("INFO", msg)
                logger.info(msg)
                return slot
        self._log("WARN", f"No available slot found after {after_time_str} at Gate {gate}")
        return None

    def reserve_slot(self, slot: dict, truck_number: str) -> dict:
        """Marks a slot as reserved for a truck."""
        for s in self.slots:
            if s["gate"] == slot["gate"] and s["start"] == slot["start"]:
                s["status"] = "reserved"
                s["truck"] = truck_number
                msg = f"Slot reserved: Gate {s['gate']} | {s['start']}–{s['end']} → {truck_number}"
                self._log("SUCCESS", msg)
                logger.info(msg)
                return s
        return slot

    def release_slot(self, truck_number: str):
        """Releases any previously reserved slot for a truck (used on renegotiation)."""
        for s in self.slots:
            if s.get("truck") == truck_number and s["status"] == "reserved":
                old_start = s["start"]
                s["status"] = "available"
                s["truck"] = None
                msg = f"Slot released: Gate {s['gate']} | {old_start} (was reserved for {truck_number})"
                self._log("INFO", msg)
                logger.info(msg)

    def preclear_gate(self, slot: dict) -> dict:
        """Called when truck is ~10 min away. Pre-clears gate for instant entry."""
        for s in self.slots:
            if s["gate"] == slot["gate"] and s["start"] == slot["start"]:
                s["status"] = "precleared"
                msg = f"Gate {s['gate']} PRE-CLEARED for {slot['start']}–{slot['end']} — truck arriving"
                self._log("SUCCESS", msg)
                logger.info(msg)
                return s
        return slot

    def get_slots(self) -> list[dict]:
        return self.slots

    def _parse_time(self, t: str) -> datetime:
        today = datetime.now().date()
        h, m = map(int, t.split(":"))
        return datetime(today.year, today.month, today.day, h, m)

    def _log(self, level: str, message: str):
        self.log.append({
            "agent": "gate",
            "level": level,
            "message": message,
            "timestamp": datetime.now().strftime("%H:%M:%S"),
        })
