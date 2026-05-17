"""
main.py — PortSync backend
No frontend. No dashboard.
Agents run. WhatsApp/SMS/QR fires. That is the product.

Run: uvicorn main:app --reload --port 8000
"""

import asyncio
import logging
import os
import jwt

from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI
from fastapi import HTTPException
from services.notify import NotifyService  # your existing service
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from twilio.rest import Client
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
    datefmt="%H:%M:%S",
)

from agents.orchestrator import PortSyncOrchestrator
from services.ais import AISService
from data.fixtures import DEMO_SCENARIO, calculate_co2_saved

# Initialize orchestrator and AIS service
orchestrator = PortSyncOrchestrator()
ais_service  = AISService()
DEMO_SCENARIO["driver"]["phone"] = os.getenv("DEMO_DRIVER_PHONE", "")

# Background AIS task
async def ais_background_task():
    async def on_eta_update(new_eta: str):
        await orchestrator.process_eta_update(new_eta)
    await ais_service.stream(on_eta_update)

@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(ais_background_task())
    yield
    task.cancel()

app = FastAPI(title="PortSync", version="1.0.0", lifespan=lifespan,
              docs_url=None, redoc_url=None, openapi_url=None)

app.mount("/static", StaticFiles(directory="static"), name="static")

# -------------------
# Health & Status
# -------------------
@app.get("/health")
def health():
    return {"status": "ok", "time": datetime.now().strftime("%H:%M:%S")}

@app.get("/")
def read_root():
    return {"message": "PortSync backend is running"}

@app.get("/status")
def status():
    return {
        "vessel": orchestrator.container_agent.get_state(),
        "truck":  orchestrator.truck_agent.get_state(),
        "slots":  orchestrator.gate_agent.get_slots(),
        "co2":    calculate_co2_saved(orchestrator.trucks_coordinated),
        "log":    orchestrator.get_all_logs()[-10:],
    }

# -------------------
# Demo Endpoints
# -------------------
@app.post("/demo/start")
async def demo_start():
    instructions = {
        "token": "PS-4827",
        "gate": "A1",
        "start_time": "2026-03-31T10:00:00",
        "end_time": "2026-03-31T12:00:00",
        "language": "en",
        "container_id": "CONT123"
    }
   
    qr_path = orchestrator.notify_service._generate_qr(instructions)
    await orchestrator.send_initial_confirmation()
    
    return {
        "sent": True,
        "qr_path":f"/static/qr_codes/portsync_qr_{instructions['token']}.png"
    }

@app.post("/demo/trigger-delay")
async def trigger_delay():
    """Step 2 of demo: vessel ETA shifts, agents renegotiate, WhatsApp fired."""
    new_eta = DEMO_SCENARIO["vessel"]["delayed_eta"]
    result  = await orchestrator.process_eta_update(new_eta)
    if not result:
        return {"triggered": False}
    if result.get("error"):
        return JSONResponse(status_code=500, content={"error": result["error"]});
    return {
        "triggered": True,
        "new_slot": result.get("new_slot"),
        "notification_sent": result.get("notification_sent", False),
        "co2": calculate_co2_saved(orchestrator.trucks_coordinated),
    }

@app.post("/demo/reset")
async def reset():
    global orchestrator
    orchestrator = PortSyncOrchestrator()
    DEMO_SCENARIO["driver"]["phone"] = os.getenv("DEMO_DRIVER_PHONE", "")
    return {"reset": True}

# -------------------
# New Notify Endpoint
# -------------------
class NotifyRequest(BaseModel):
    phone: str
    message: str

@app.post("/notify")
async def notify(req: NotifyRequest):
    """Standalone endpoint to send WhatsApp/SMS via Twilio."""
    account_sid = os.getenv("TWILIO_ACCOUNT_SID")
    auth_token = os.getenv("TWILIO_AUTH_TOKEN")
    #from_number = os.getenv("TWILIO_PHONE_NUMBER")
    from_number = os.getenv("TWILIO_WHATSAPP_FROM")

    if not account_sid or not auth_token or not from_number:
        return {"status": "DRY RUN", "message": f"Would send to {req.phone}: {req.message}"}

    client = Client(account_sid, auth_token)
    message = client.messages.create(
        #from_=f"whatsapp:{from_number}",
        from_=from_number,
        to=f"whatsapp:{req.phone}",
        body=req.message
    )
    return {"status": "SENT", "sid": message.sid}

@app.get("/verify")
def verify_qr(token: str):
    result = NotifyService.verify_qr(token)

    if "error" in result:
        return {
            "status": "INVALID",
            "reason": result["error"]
        }

    return {
        "status": "VALID",
        "data": {
            "token": result["token"],
            "gate": result["gate"],
            "time_slot": f"{result['start']} - {result['end']}",
            "container_id": result["container"]
        }
    }



SECRET_KEY = os.getenv("JWT_SECRET")  # read secret key from .env

@app.post("/verify")
def verify_qr(token: str):
    try:
        # Decode JWT
        data = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])

        # Clean structured output
        return {
            "status": "VALID ",
            "data": {
                "gate": data.get("gate"),
                "time_slot": data.get("time"),
                "phone": data.get("phone")
            }
        }

    except jwt.ExpiredSignatureError:
        return {"status": "EXPIRED ", "reason": "Token has expired"}

    except jwt.InvalidTokenError:
        return {"status": "INVALID ", "reason": "Token is not valid"}














# """
# main.py — PortSync backend
# No frontend. No dashboard.
# Agents run. WhatsApp/SMS/QR fires. That is the product.

# Run: uvicorn main:app --reload --port 8000
# """

# import asyncio
# import logging
# import os
# from contextlib import asynccontextmanager
# from datetime import datetime

# from fastapi import FastAPI
# app = FastAPI(
#     docs_url=None,         # disables /docs
#     redoc_url=None,        # disables /redoc
#     openapi_url=None       # disables /openapi.json
# )

# from fastapi.responses import JSONResponse
# from dotenv import load_dotenv

# load_dotenv()
# logging.basicConfig(
#     level=logging.INFO,
#     format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
#     datefmt="%H:%M:%S",
# )

# from agents.orchestrator import PortSyncOrchestrator
# from services.ais import AISService
# from data.fixtures import DEMO_SCENARIO, calculate_co2_saved

# orchestrator = PortSyncOrchestrator()
# ais_service  = AISService()
# DEMO_SCENARIO["driver"]["phone"] = os.getenv("DEMO_DRIVER_PHONE", "")


# async def ais_background_task():
#     async def on_eta_update(new_eta: str):
#         await orchestrator.process_eta_update(new_eta)
#     await ais_service.stream(on_eta_update)


# @asynccontextmanager
# async def lifespan(app: FastAPI):
#     task = asyncio.create_task(ais_background_task())
#     yield
#     task.cancel()


# app = FastAPI(title="PortSync", version="1.0.0", lifespan=lifespan)


# @app.get("/health")
# def health():
#     return {"status": "ok", "time": datetime.now().strftime("%H:%M:%S")}

# @app.get("/")
# def read_root():
#     return {"message": "PortSync backend is running"}


# @app.get("/status")
# def status():
#     return {
#         "vessel": orchestrator.container_agent.get_state(),
#         "truck":  orchestrator.truck_agent.get_state(),
#         "slots":  orchestrator.gate_agent.get_slots(),
#         "co2":    calculate_co2_saved(orchestrator.trucks_coordinated),
#         "log":    orchestrator.get_all_logs()[-10:],
#     }


# @app.post("/demo/start")
# async def demo_start():
#     """Step 1 of demo: send initial slot confirmation to driver phone."""
#     await orchestrator.send_initial_confirmation()
#     return {"sent": True}


# @app.post("/demo/trigger-delay")
# async def trigger_delay():
#     """Step 2 of demo: vessel ETA shifts, agents renegotiate, WhatsApp fired."""
#     new_eta = DEMO_SCENARIO["vessel"]["delayed_eta"]
#     result  = await orchestrator.process_eta_update(new_eta)
#     if not result:
#         return {"triggered": False}
#     if result.get("error"):
#         return JSONResponse(status_code=500, content={"error": result["error"]})
#     return {
#         "triggered": True,
#         "new_slot": result.get("new_slot"),
#         "notification_sent": result.get("notification_sent", False),
#         "co2": calculate_co2_saved(orchestrator.trucks_coordinated),
#     }


# @app.post("/demo/reset")
# async def reset():
#     global orchestrator
#     orchestrator = PortSyncOrchestrator()
#     DEMO_SCENARIO["driver"]["phone"] = os.getenv("DEMO_DRIVER_PHONE", "")
#     return {"reset": True}
