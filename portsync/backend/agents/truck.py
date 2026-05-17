"""
truck.py — Member 1
Truck Agent: receives new slot time, calls Maps API for optimal
route and departure time, returns driver instructions.
"""

from datetime import datetime
from typing import Optional
import logging

logger = logging.getLogger("truck_agent")


class TruckAgent:
    def __init__(self, driver_name: str, truck_number: str,
                 origin: str, origin_lat: float, origin_lon: float,
                 language: str = "hi"):
        self.driver_name = driver_name
        self.truck_number = truck_number
        self.origin = origin
        self.origin_lat = origin_lat
        self.origin_lon = origin_lon
        self.language = language
        self.current_slot: Optional[dict] = None
        self.status = "STANDBY"    # STANDBY | EN_ROUTE | ARRIVING | DONE
        self.log: list[dict] = []

    def calculate_route(self, slot_start: str, port_lat: float, port_lon: float,
                        maps_service) -> dict:
        """
        Uses Maps service to calculate route from origin to port,
        arriving by slot_start time. Returns route instructions.
        """
        msg = f"Truck agent: calculating route for {self.driver_name} → Gate arrival by {slot_start}"
        self._log("INFO", msg)
        logger.info(msg)

        route = maps_service.get_route(
            origin_lat=self.origin_lat,
            origin_lon=self.origin_lon,
            dest_lat=port_lat,
            dest_lon=port_lon,
            arrival_time_str=slot_start,
        )

        self.status = "EN_ROUTE"
        self._log("SUCCESS", f"Route found: {route['summary']} | Depart by {route['departure_time']}")
        return route

    def update_slot(self, new_slot: dict, route: dict):
        """Called when gate agent confirms a new/updated slot."""
        self.current_slot = new_slot
        msg = (f"Slot update for {self.driver_name}: "
               f"Gate {new_slot['gate']} | {new_slot['start']}–{new_slot['end']} | "
               f"Depart by {route.get('departure_time', 'ASAP')}")
        self._log("SUCCESS", msg)
        logger.info(msg)

    def build_instructions(self, slot: dict, route: dict, token: str) -> dict:
        """Builds the full instruction payload for the notification service."""
        return {
            "driver_name": self.driver_name,
            "gate": slot["gate"],
            "start_time": slot["start"],
            "end_time": slot["end"],
            "container_id": None,    # filled by orchestrator
            "token": token,
            "route_summary": route.get("summary", "NH-48, Nhava Sheva exit"),
            "departure_time": route.get("departure_time", "ASAP"),
            "language": self.language,
        }

    def _log(self, level: str, message: str):
        self.log.append({
            "agent": "truck",
            "level": level,
            "message": message,
            "timestamp": datetime.now().strftime("%H:%M:%S"),
        })

    def get_state(self) -> dict:
        return {
            "driver": self.driver_name,
            "truck": self.truck_number,
            "status": self.status,
            "current_slot": self.current_slot,
        }
