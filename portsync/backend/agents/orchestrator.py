"""
orchestrator.py — Member 1
LangGraph-powered orchestrator that coordinates all three agents.
Handles the full negotiation loop end-to-end.
"""

import asyncio
import secrets
import logging
from datetime import datetime
from typing import TypedDict, Optional

from langgraph.graph import StateGraph, END

from agents.container import ContainerAgent
from agents.gate import GateSlotAgent
from agents.truck import TruckAgent
from services.maps import MapsService
from services.notify import NotifyService
from data.fixtures import DEMO_SCENARIO, INITIAL_SLOTS, MSG_TEMPLATES

logger = logging.getLogger("orchestrator")


# ── LangGraph state schema ──────────────────────────────────────────────────

class PortSyncState(TypedDict):
    event: dict                     # the triggering RENEGOTIATE event
    new_slot: Optional[dict]        # chosen gate slot
    route: Optional[dict]           # truck route from Maps API
    token: str                      # JWT-style slot token
    instructions: Optional[dict]    # built instruction payload
    notification_sent: bool
    error: Optional[str]
    agent_log: list[dict]           # accumulated log entries


# ── Node functions (each = one agent step) ─────────────────────────────────

def find_slot_node(state: PortSyncState) -> PortSyncState:
    gate_agent: GateSlotAgent = state["_gate_agent"]
    event = state["event"]

    # Release old slot first
    gate_agent.release_slot(DEMO_SCENARIO["driver"]["truck_number"])

    # Find next available slot after new ETA + 15 min buffer
    new_eta = event["new_eta"]
    h, m = map(int, new_eta.split(":"))
    m += 15
    if m >= 60:
        h += 1
        m -= 60
    search_after = f"{h:02d}:{m:02d}"

    slot = gate_agent.find_next_available(search_after, gate=4)
    if not slot:
        return {**state, "error": "No available slots found", "agent_log": [
            *state["agent_log"], *gate_agent.log
        ]}

    slot = gate_agent.reserve_slot(slot, DEMO_SCENARIO["driver"]["truck_number"])
    return {**state, "new_slot": slot, "agent_log": [*state["agent_log"], *gate_agent.log]}


def calculate_route_node(state: PortSyncState) -> PortSyncState:
    if state.get("error"):
        return state

    truck_agent: TruckAgent = state["_truck_agent"]
    maps_service: MapsService = state["_maps_service"]
    slot = state["new_slot"]
    port = DEMO_SCENARIO["port"]

    route = truck_agent.calculate_route(
        slot_start=slot["start"],
        port_lat=port["lat"],
        port_lon=port["lon"],
        maps_service=maps_service,
    )
    truck_agent.update_slot(slot, route)
    return {**state, "route": route, "agent_log": [*state["agent_log"], *truck_agent.log]}


def notify_driver_node(state: PortSyncState) -> PortSyncState:
    if state.get("error"):
        return state

    truck_agent: TruckAgent = state["_truck_agent"]
    notify_service: NotifyService = state["_notify_service"]
    slot = state["new_slot"]
    route = state["route"]
    token = state["token"]
    event_type = state["event"].get("notification_type", "slot_updated")

    instructions = truck_agent.build_instructions(slot, route, token)
    instructions["container_id"] = DEMO_SCENARIO["container"]["id"]

    notify_service.send(
        phone=DEMO_SCENARIO["driver"]["phone"],
        template_key=event_type,
        instructions=instructions,
    )

    return {
        **state,
        "instructions": instructions,
        "notification_sent": True,
        "agent_log": [*state["agent_log"], {
            "agent": "orchestrator",
            "level": "SUCCESS",
            "message": f"Notification sent to {DEMO_SCENARIO['driver']['name']} — slot {slot['start']}–{slot['end']} Gate {slot['gate']}",
            "timestamp": datetime.now().strftime("%H:%M:%S"),
        }]
    }


def should_notify(state: PortSyncState) -> str:
    return "error" if state.get("error") else "notify"


# ── Build the LangGraph ─────────────────────────────────────────────────────

def build_graph():
    g = StateGraph(PortSyncState)
    g.add_node("find_slot", find_slot_node)
    g.add_node("calculate_route", calculate_route_node)
    g.add_node("notify_driver", notify_driver_node)

    g.set_entry_point("find_slot")
    g.add_conditional_edges("find_slot", should_notify, {
        "notify": "calculate_route",
        "error": END,
    })
    g.add_edge("calculate_route", "notify_driver")
    g.add_edge("notify_driver", END)
    return g.compile()


# ── Orchestrator class ──────────────────────────────────────────────────────

class PortSyncOrchestrator:
    def __init__(self):
        self.container_agent = ContainerAgent(
            container_id=DEMO_SCENARIO["container"]["id"],
            vessel_name=DEMO_SCENARIO["vessel"]["name"],
            booked_eta=DEMO_SCENARIO["vessel"]["original_eta"],
        )
        self.gate_agent = GateSlotAgent(slots=INITIAL_SLOTS)
        self.truck_agent = TruckAgent(
            driver_name=DEMO_SCENARIO["driver"]["name"],
            truck_number=DEMO_SCENARIO["driver"]["truck_number"],
            origin=DEMO_SCENARIO["driver"]["origin"],
            origin_lat=DEMO_SCENARIO["driver"]["origin_lat"],
            origin_lon=DEMO_SCENARIO["driver"]["origin_lon"],
            language=DEMO_SCENARIO["driver"]["language"],
        )
        self.maps_service = MapsService()
        self.notify_service = NotifyService()
        self.graph = build_graph()
        self.event_log: list[dict] = []
        self.trucks_coordinated = 0

    def get_all_logs(self) -> list[dict]:
        logs = []
        logs += self.container_agent.log
        logs += self.gate_agent.log
        logs += self.truck_agent.log
        logs += self.event_log
        return sorted(logs, key=lambda x: x["timestamp"])

    async def process_eta_update(self, new_eta: str) -> Optional[dict]:
        """
        Main entry point. Call this when AIS reports a new ETA.
        Returns result dict if renegotiation happened, else None.
        """
        event = self.container_agent.update_eta(new_eta)
        if not event:
            return None

        logger.info(f"Orchestrator: renegotiation triggered — {event['message']}")
        self.event_log.append({
            "agent": "orchestrator",
            "level": "ALERT",
            "message": f"RENEGOTIATION STARTED — ETA shifted {event['shift_minutes']:+d} min",
            "timestamp": datetime.now().strftime("%H:%M:%S"),
        })

        token = f"PS-{secrets.token_hex(2).upper()}"
        event["notification_type"] = "slot_updated"

        initial_state: PortSyncState = {
            "event": event,
            "new_slot": None,
            "route": None,
            "token": token,
            "instructions": None,
            "notification_sent": False,
            "error": None,
            "agent_log": [],
            # inject agents and services (not in schema but passed through)
            "_gate_agent": self.gate_agent,
            "_truck_agent": self.truck_agent,
            "_maps_service": self.maps_service,
            "_notify_service": self.notify_service,
        }

        result = self.graph.invoke(initial_state)
        self.event_log.extend(result.get("agent_log", []))

        if not result.get("error"):
            self.trucks_coordinated += 1
            slot = result["new_slot"]
            self.container_agent.confirm_slot(slot["start"], slot["end"], slot["gate"])

        return result

    async def send_initial_confirmation(self):
        """Send the first slot confirmation to the driver when demo starts."""
        slot = next(s for s in self.gate_agent.slots if s["status"] == "reserved")
        token = "PS-4821"
        route = self.maps_service.get_route(
            origin_lat=DEMO_SCENARIO["driver"]["origin_lat"],
            origin_lon=DEMO_SCENARIO["driver"]["origin_lon"],
            dest_lat=DEMO_SCENARIO["port"]["lat"],
            dest_lon=DEMO_SCENARIO["port"]["lon"],
            arrival_time_str=slot["start"],
        )
        instructions = self.truck_agent.build_instructions(slot, route, token)
        instructions["container_id"] = DEMO_SCENARIO["container"]["id"]
        self.notify_service.send(
            phone=DEMO_SCENARIO["driver"]["phone"],
            template_key="slot_confirmed",
            instructions=instructions,
        )
        self.event_log.append({
            "agent": "orchestrator",
            "level": "SUCCESS",
            "message": f"Initial slot confirmation sent to {DEMO_SCENARIO['driver']['name']}",
            "timestamp": datetime.now().strftime("%H:%M:%S"),
        })
