# PortSync — Setup Guide

## What this is
A multi-agent AI backend. No frontend. No dashboard.
Agents coordinate. Driver gets WhatsApp. Gate pre-cleared. Done.

## Project structure
```
backend/
├── demo.py              ← Run this on hackathon day
├── main.py              ← FastAPI (optional, for demo triggers via curl)
├── agents/
│   ├── orchestrator.py  ← LangGraph coordination engine
│   ├── container.py     ← Container agent (tracks vessel ETA)
│   ├── gate.py          ← Gate slot agent (manages port slot pool)
│   └── truck.py         ← Truck agent (calculates driver route)
├── services/
│   ├── ais.py           ← AIS vessel tracking (aisstream.io + simulation)
│   ├── maps.py          ← Google Maps routing
│   └── notify.py        ← Twilio WhatsApp + SMS + QR generator
└── data/
    └── fixtures.py      ← Demo scenario data
```

---

## Accounts to create TODAY (all free)
| Service | URL | Purpose |
|---------|-----|---------|
| Twilio | twilio.com | WhatsApp + SMS |
| AISstream | aisstream.io | Live vessel data |
| Google Cloud | console.cloud.google.com | Maps Directions API |

---

## Setup (one time, do today)
```bash
cd backend
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
# Fill in your keys in .env
```

---

## Member tasks

### Member 1 — Agent engine
Files: `agents/container.py`, `agents/gate.py`, `agents/truck.py`, `agents/orchestrator.py`

Test today:
```python
# test_agents.py
import asyncio
from agents.orchestrator import PortSyncOrchestrator
from data.fixtures import DEMO_SCENARIO

async def test():
    DEMO_SCENARIO["driver"]["phone"] = ""  # dry run
    orc = PortSyncOrchestrator()
    result = await orc.process_eta_update("14:45")
    print(result)

asyncio.run(test())
```
Goal: negotiation prints to terminal, slot renegotiated, no crash.

---

### Member 2 — Notifications
Files: `services/notify.py`, `.env` setup

Test today:
```python
# test_notify.py
import os; os.environ["DEMO_DRIVER_PHONE"] = "+91YOUR_NUMBER"
from services.notify import NotifyService

n = NotifyService()
n.send(
    phone="+91YOUR_NUMBER",
    template_key="slot_confirmed",
    instructions={
        "driver_name": "Ramesh",
        "gate": 4,
        "start_time": "14:00",
        "end_time": "14:30",
        "container_id": "MSKU7234561",
        "token": "PS-4821",
        "route_summary": "NH-48 via Nhava Sheva",
        "departure_time": "13:00",
        "language": "hi",
    }
)
```
Goal: YOUR phone receives a WhatsApp in Hindi. That is the demo moment.

---

### Member 3 — AIS + Maps
Files: `services/ais.py`, `services/maps.py`

Test today:
```python
# test_ais.py
import asyncio
from services.ais import AISService

async def test():
    ais = AISService()
    def on_update(eta):
        print(f"ETA update: {eta}")
    await ais.stream(on_update)  # runs simulation if no API key

asyncio.run(test())
```
```python
# test_maps.py
from services.maps import MapsService
m = MapsService()
route = m.get_route(19.2813, 73.0631, 18.9543, 72.9398, "14:00")
print(route)
```
Goal: AIS streams ETA updates every 5 seconds. Maps returns a route dict.

---

### Member 4 — Integration + demo script
Files: `data/fixtures.py`, `demo.py`

Task today:
- Read all of fixtures.py. Understand every field.
- Run `python demo.py` end to end (dry run without real phone).
- Time it — target under 4 minutes.
- Memorise the demo script below word for word.
- Prepare judge Q&A answers.

---

## Running the demo (hackathon day)
```bash
# Make sure .env has DEMO_DRIVER_PHONE set
python demo.py
```

That is it. No server. No browser. No frontend.
The terminal is the demo. The phone is the proof.

---

## Demo script (memorise this)

**Before judges arrive:**
Run `python demo.py` — it pauses waiting for ENTER.

**Speaking script (4 minutes):**

> "It's 9 AM at JNPT — India's busiest container port.
> MV Chennai Star is en route with container MSKU7234561.
> Ramesh, our driver, is in Bhiwandi.
> He just received his gate slot — on WhatsApp, in Hindi,
> on his basic Android phone. No app. No training. Nothing new."

*[Show phone — first WhatsApp with slot details]*  *[Press ENTER]*

> "At 11 AM, AIS data shows the vessel has slowed down.
> ETA has shifted 45 minutes.
> Normally, Ramesh finds out when he arrives — and joins a 4-hour queue.
> Watch what PortSync does."

*[Terminal shows agents negotiating — read out what each agent is doing]*

> "Container agent detected the shift.
> Gate slot agent released the old slot, found the next available window.
> Truck agent recalculated Ramesh's departure time via Google Maps.
> Entire negotiation — under 10 seconds. No human involved."

*[Show phone — renegotiation WhatsApp in Hindi]*  *[Press ENTER]*

> "Ramesh gets a new WhatsApp. Gate 4 is still his. Slot is secure.
> If he had no signal inside the port yard — which happens — the QR
> was already saved to his phone gallery. Gate scanner reads it offline.
> Same entry. Zero friction. Engine idle time: zero."

> "500 trucks a day at JNPT.
> That is 6,500 kg of CO2 eliminated. Every single day.
> Payback period: under one month."

---

## Judge Q&A

**"How does it scale?"**
Agents are stateless. Each port gets its own orchestrator instance. 10 ports = 10x. Horizontal scaling via Docker on Railway.

**"What if Twilio is down?"**
QR is a signed JWT generated at slot confirmation. Gate scanner works offline — no server call at scan time.

**"How do you handle multiple ports?"**
Each port has its own orchestrator + slot pool + rules config file. One config swap per geography. Language model switches per corridor.

**"Revenue model?"**
SaaS: per-port license + Rs.2–5 per coordination event. 500 trucks/day = Rs.3–7.5 lakh/day in micro-fees. Under 1 month payback.

**"Why not call the driver?"**
Bad cellular inside port yards. Language barriers with centralised dispatch. No auditable record. WhatsApp is async, works on 2G, local language, and every message is timestamped.
