"""
maps.py — Member 4
Google Maps Directions API wrapper.
Returns route summary, duration, and optimal departure time.
Falls back to realistic hardcoded data if API key not set.
"""

import os
import logging
import requests
from datetime import datetime, timedelta

logger = logging.getLogger("maps_service")

JNPT_ADDRESS = "Nhava Sheva, JNPT, Navi Mumbai, Maharashtra 400707"


class MapsService:
    def __init__(self):
        self.api_key = os.getenv("GOOGLE_MAPS_API_KEY", "")
        if not self.api_key:
            logger.warning("Google Maps API key not set — using fallback route data")

    def get_route(self, origin_lat: float, origin_lon: float,
                  dest_lat: float, dest_lon: float,
                  arrival_time_str: str) -> dict:
        """
        Returns route dict with summary, duration_min, departure_time.
        """
        if not self.api_key:
            return self._fallback_route(arrival_time_str)

        try:
            return self._call_maps_api(
                origin_lat, origin_lon, dest_lat, dest_lon, arrival_time_str
            )
        except Exception as e:
            logger.error(f"Maps API error: {e} — using fallback")
            return self._fallback_route(arrival_time_str)

    def _call_maps_api(self, orig_lat, orig_lon, dest_lat, dest_lon, arrival_time_str) -> dict:
        today = datetime.now().date()
        h, m = map(int, arrival_time_str.split(":"))
        arrival_dt = datetime(today.year, today.month, today.day, h, m)
        arrival_ts = int(arrival_dt.timestamp())

        url = "https://maps.googleapis.com/maps/api/directions/json"
        params = {
            "origin": f"{orig_lat},{orig_lon}",
            "destination": f"{dest_lat},{dest_lon}",
            "arrival_time": arrival_ts,
            "key": self.api_key,
            "mode": "driving",
            "region": "in",
        }
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()

        if data["status"] != "OK":
            raise ValueError(f"Maps API status: {data['status']}")

        route = data["routes"][0]
        leg = route["legs"][0]
        duration_min = leg["duration"]["value"] // 60
        departure_dt = arrival_dt - timedelta(minutes=duration_min + 15)  # 15 min buffer

        return {
            "summary": leg.get("summary", route.get("summary", "NH-48")),
            "duration_min": duration_min,
            "distance_km": round(leg["distance"]["value"] / 1000, 1),
            "departure_time": departure_dt.strftime("%H:%M"),
            "arrival_time": arrival_time_str,
            "steps_count": len(leg["steps"]),
        }

    def _fallback_route(self, arrival_time_str: str) -> dict:
        """Realistic fallback for Bhiwandi → JNPT."""
        h, m = map(int, arrival_time_str.split(":"))
        arrival_dt = datetime.now().replace(hour=h, minute=m, second=0, microsecond=0)
        departure_dt = arrival_dt - timedelta(minutes=90 + 15)

        return {
            "summary": "NH-48 via Nhava Sheva Rd",
            "duration_min": 90,
            "distance_km": 58.4,
            "departure_time": departure_dt.strftime("%H:%M"),
            "arrival_time": arrival_time_str,
            "steps_count": 4,
        }
