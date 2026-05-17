"""
ais.py — Member 4
AIS vessel tracking service.
Primary: aisstream.io websocket (real live data)
Fallback: simulated vessel position from fixtures
"""

import asyncio
import json
import os
import logging
from typing import Optional, Callable
import websockets
from data.fixtures import AIS_SIMULATION, DEMO_SCENARIO

logger = logging.getLogger("ais_service")


class AISService:
    def __init__(self):
        self.api_key = os.getenv("AIS_API_KEY", "")
        self.mmsi = DEMO_SCENARIO["vessel"]["mmsi"]
        self.current_eta: Optional[str] = DEMO_SCENARIO["vessel"]["original_eta"]
        self._sim_index = 0
        self._use_simulation = not bool(self.api_key)

        if self._use_simulation:
            logger.warning("AIS API key not set — using simulation mode")

    async def stream(self, on_update: Callable[[str], None]):
        """
        Streams vessel ETA updates. Calls on_update(new_eta_str) on each update.
        Uses real AISstream websocket if API key is set, else simulation.
        """
        if self._use_simulation:
            await self._simulate(on_update)
        else:
            await self._stream_live(on_update)

    async def _stream_live(self, on_update: Callable[[str], None]):
        url = "wss://stream.aisstream.io/v0/stream"
        subscribe_msg = {
            "APIKey": self.api_key,
            "BoundingBoxes": [[
                [18.5, 72.5],   # SW corner — covers approach to JNPT
                [19.2, 73.2],   # NE corner
            ]],
            "FilterMessageTypes": ["PositionReport"],
        }
        logger.info("Connecting to AISstream...")
        async with websockets.connect(url) as ws:
            await ws.send(json.dumps(subscribe_msg))
            async for raw in ws:
                try:
                    data = json.loads(raw)
                    mmsi = str(data.get("MetaData", {}).get("MMSI", ""))
                    if mmsi != self.mmsi:
                        continue
                    # Extract ETA from message (approximate from speed + distance)
                    eta = self._estimate_eta_from_position(data)
                    if eta and eta != self.current_eta:
                        self.current_eta = eta
                        await on_update(eta)
                except Exception as e:
                    logger.error(f"AIS parse error: {e}")

    def _estimate_eta_from_position(self, data: dict) -> Optional[str]:
        """
        Rough ETA estimate from current speed and distance to JNPT.
        In production this would use proper nautical calculation.
        """
        try:
            lat = data["Message"]["PositionReport"]["Latitude"]
            lon = data["Message"]["PositionReport"]["Longitude"]
            sog = data["Message"]["PositionReport"]["Sog"]  # speed over ground in knots

            # Simple distance calc (degrees to nautical miles approx)
            dlat = DEMO_SCENARIO["vessel"]["lat"] - lat
            dlon = DEMO_SCENARIO["vessel"]["lon"] - lon
            dist_nm = ((dlat**2 + dlon**2) ** 0.5) * 60

            if sog < 0.5:
                return self.current_eta  # vessel stopped, keep last ETA

            hours_to_arrive = dist_nm / sog
            from datetime import datetime, timedelta
            eta_dt = datetime.now() + timedelta(hours=hours_to_arrive)
            return eta_dt.strftime("%H:%M")
        except Exception:
            return None

    async def _simulate(self, on_update: Callable[[str], None]):
        """Plays back pre-defined AIS simulation with 5-second intervals."""
        logger.info("AIS simulation mode — replaying vessel approach to JNPT")
        for step in AIS_SIMULATION:
            await asyncio.sleep(5)  # 5 seconds between updates for demo pacing
            eta = step["eta"]
            logger.info(f"AIS sim: vessel at ({step['lat']:.2f},{step['lon']:.2f}) "
                       f"speed={step['speed']}kn ETA={eta}")
            if eta != self.current_eta:
                self.current_eta = eta
                await on_update(eta)
