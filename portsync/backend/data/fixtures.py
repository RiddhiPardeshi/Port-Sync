"""
fixtures.py — Member 4
All realistic demo data for the PortSync demo scenario.
"""

DEMO_SCENARIO = {
    "vessel": {
        "name": "MV Chennai Star",
        "mmsi": "419001234",
        "flag": "India",
        "container_count": 312,
        "original_eta": "14:00",          # 2:00 PM
        "delayed_eta": "14:45",           # shift of 45 min — triggers renegotiation
        "berth": "JNPT — Nhava Sheva, Berth 7",
        "lat": 18.9543,
        "lon": 72.9398,
    },
    "container": {
        "id": "MSKU7234561",
        "type": "Dry 20ft",
        "contents": "Automotive parts",
        "shipper": "Tata Motors Ltd",
        "consignee": "Maruti Suzuki — Gurugram",
    },
    "driver": {
        "name": "Ramesh Yadav",
        "phone": None,              # filled from .env DEMO_DRIVER_PHONE at runtime
        "truck_number": "MH-04-CX-7821",
        "origin": "Bhiwandi, Maharashtra",
        "origin_lat": 19.2813,
        "origin_lon": 73.0631,
        "language": "hi",           # Hindi
    },
    "port": {
        "name": "JNPT — Nhava Sheva",
        "lat": 18.9543,
        "lon": 72.9398,
        "gates": {
            1: {"name": "Gate 1", "status": "open"},
            2: {"name": "Gate 2", "status": "open"},
            3: {"name": "Gate 3", "status": "open"},
            4: {"name": "Gate 4", "status": "open"},
            5: {"name": "Gate 5", "status": "closed"},
            6: {"name": "Gate 6", "status": "open"},
        },
        "gate_hours": "06:00–22:00",
    },
}

# Initial slot pool — 30-min windows for Gate 4
INITIAL_SLOTS = [
    {"gate": 4, "start": "13:00", "end": "13:30", "status": "occupied",  "truck": "MH-12-AB-1111"},
    {"gate": 4, "start": "13:30", "end": "14:00", "status": "occupied",  "truck": "MH-04-XY-3344"},
    {"gate": 4, "start": "14:00", "end": "14:30", "status": "reserved",  "truck": "MH-04-CX-7821"},  # Ramesh's original
    {"gate": 4, "start": "14:30", "end": "15:00", "status": "available", "truck": None},
    {"gate": 4, "start": "15:00", "end": "15:30", "status": "available", "truck": None},
    {"gate": 4, "start": "15:30", "end": "16:00", "status": "available", "truck": None},
    {"gate": 4, "start": "16:00", "end": "16:30", "status": "occupied",  "truck": "GJ-05-RR-9988"},
]

# Message templates (translated at runtime via deep-translator)
MSG_TEMPLATES = {
    "slot_confirmed": (
        "Namaste {driver_name} ji,\n"
        "Aapka container JNPT Gate {gate} par ready hoga.\n\n"
        "Slot: {start_time}–{end_time}\n"
        "Container: {container_id}\n"
        "Token: {token}\n\n"
        "Route: {route_summary}\n"
        "{departure_time} tak niklo.\n\n"
        "QR code neeche attach hai — gate par scan karo."
    ),
    "slot_updated": (
        "UPDATE: Vessel delay detected.\n"
        "Aapka slot update hua hai:\n\n"
        "New time: {start_time}–{end_time}\n"
        "Gate: {gate} (same)\n"
        "Token: {token} (same)\n\n"
        "Koi fikar nahi — aapka slot secure hai."
    ),
    "gate_ready": (
        "Gate {gate} READY hai.\n"
        "Ab aao — QR scan karo, seedha andar jao.\n"
        "Token: {token}"
    ),
}

# AIS fallback — simulated vessel position updates (used if aisstream is unavailable)
AIS_SIMULATION = [
    {"time_offset_min": 0,  "lat": 18.60, "lon": 72.70, "speed": 12.4, "eta": "14:00"},
    {"time_offset_min": 5,  "lat": 18.65, "lon": 72.74, "speed": 12.1, "eta": "14:00"},
    {"time_offset_min": 10, "lat": 18.72, "lon": 72.80, "speed": 11.8, "eta": "14:05"},
    {"time_offset_min": 15, "lat": 18.79, "lon": 72.84, "speed": 10.2, "eta": "14:20"},  # slowing
    {"time_offset_min": 20, "lat": 18.84, "lon": 72.87, "speed":  8.1, "eta": "14:45"},  # BIG SHIFT — triggers renegotiation
    {"time_offset_min": 25, "lat": 18.88, "lon": 72.90, "speed":  7.9, "eta": "14:45"},
    {"time_offset_min": 30, "lat": 18.92, "lon": 72.93, "speed":  6.0, "eta": "14:50"},
]

# CO2 savings calculation
CO2_KG_PER_HOUR_IDLE = 2.6       # diesel truck idling
AVG_HOURS_SAVED_PER_TRUCK = 4.5  # industry average at JNPT

def calculate_co2_saved(trucks_coordinated: int) -> dict:
    hours_saved = trucks_coordinated * AVG_HOURS_SAVED_PER_TRUCK
    kg_saved = hours_saved * CO2_KG_PER_HOUR_IDLE
    return {
        "trucks": trucks_coordinated,
        "hours_saved": round(hours_saved, 1),
        "kg_co2_saved": round(kg_saved, 1),
        "trees_equivalent": round(kg_saved / 21.7, 1),  # avg tree absorbs 21.7kg/year
    }
