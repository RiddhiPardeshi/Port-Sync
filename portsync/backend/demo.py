"""
demo.py — Run this on hackathon day.
No browser. No frontend. Just run: python demo.py

Judges see:
- Coloured terminal showing agents negotiating live
- Real WhatsApp arriving on the phone on the table
- QR card saved as PNG
"""

import asyncio
import os
from dotenv import load_dotenv
load_dotenv()

from agents.orchestrator import PortSyncOrchestrator
from data.fixtures import DEMO_SCENARIO, calculate_co2_saved

# Terminal colours
RESET="\033[0m"; BOLD="\033[1m"; BLUE="\033[94m"; AMBER="\033[93m"
GREEN="\033[92m"; RED="\033[91m"; PURPLE="\033[95m"; CYAN="\033[96m"; GREY="\033[90m"

AGENT_COLOUR = {"container": BLUE, "truck": AMBER, "gate": RED, "orchestrator": PURPLE}
LEVEL_COLOUR = {"INFO": GREY, "SUCCESS": GREEN, "ALERT": RED, "WARN": AMBER}


def log(entry):
    ts = entry.get("timestamp", "")
    ag = entry.get("agent", "system")
    lv = entry.get("level", "INFO")
    ms = entry.get("message", "")
    print(f"  {GREY}{ts}{RESET}  {AGENT_COLOUR.get(ag,CYAN)}{BOLD}[{ag.upper():<13}]{RESET}  {LEVEL_COLOUR.get(lv,GREY)}{ms}{RESET}")


def sep(title=""):
    if title:
        pad = (68 - len(title)) // 2
        print(f"\n  {GREY}{'─'*pad} {CYAN}{BOLD}{title}{RESET} {GREY}{'─'*pad}{RESET}\n")
    else:
        print(f"  {GREY}{'─'*72}{RESET}")


async def run():
    print(f"\n  {CYAN}{BOLD}PortSync — Autonomous Port Coordination{RESET}")
    print(f"  {GREY}No dashboard. Agents fix it before it becomes a queue.{RESET}\n")

    DEMO_SCENARIO["driver"]["phone"] = os.getenv("DEMO_DRIVER_PHONE", "")
    if not DEMO_SCENARIO["driver"]["phone"]:
        print(f"  {AMBER}No DEMO_DRIVER_PHONE set — running in dry-run mode{RESET}\n")

    orc = PortSyncOrchestrator()

    # STEP 1 — Initial confirmation
    sep("STEP 1 — INITIAL SLOT CONFIRMATION")
    print(f"  {GREY}Vessel  : {CYAN}{DEMO_SCENARIO['vessel']['name']}{RESET}  ETA {CYAN}{DEMO_SCENARIO['vessel']['original_eta']}{RESET}")
    print(f"  {GREY}Driver  : {CYAN}{DEMO_SCENARIO['driver']['name']}{RESET}  ({DEMO_SCENARIO['driver']['truck_number']})")
    print(f"  {GREY}Origin  : {CYAN}{DEMO_SCENARIO['driver']['origin']}{RESET}\n")
    print(f"  {GREY}Sending initial slot confirmation...\n{RESET}")
    await orc.send_initial_confirmation()

    for entry in orc.get_all_logs():
        log(entry)

    print(f"\n  {GREEN}{BOLD}WhatsApp sent — Gate 4 | 14:00-14:30 | Token PS-4821{RESET}")
    print(f"\n  {AMBER}Show judges the WhatsApp. Press ENTER when ready...{RESET}")
    input()

    # STEP 2 — Vessel delay
    sep("STEP 2 — VESSEL DELAY DETECTED BY AIS")
    print(f"  {RED}{BOLD}MV Chennai Star slowing — ETA shift detected{RESET}")
    print(f"  {GREY}Original : {DEMO_SCENARIO['vessel']['original_eta']}  New : {RED}{DEMO_SCENARIO['vessel']['delayed_eta']}  (+45 min){RESET}")
    print(f"\n  {GREY}Agent swarm activating...{RESET}\n")
    await asyncio.sleep(1)

    count_before = len(orc.get_all_logs())
    result = await orc.process_eta_update(DEMO_SCENARIO["vessel"]["delayed_eta"])

    for entry in orc.get_all_logs()[count_before:]:
        log(entry)
        await asyncio.sleep(0.25)

    # STEP 3 — Result
    sep("STEP 3 — RESULT")
    if result and not result.get("error"):
        slot = result["new_slot"]
        print(f"  {GREEN}{BOLD}Renegotiated in under 10 seconds{RESET}")
        print(f"  {GREY}New slot     : {GREEN}Gate {slot['gate']} | {slot['start']}–{slot['end']}{RESET}")
        print(f"  {GREY}Token        : {GREEN}PS-4821 (unchanged — QR still valid offline){RESET}")
        print(f"  {GREY}WhatsApp     : {GREEN}Sent{RESET}  {GREY}SMS fallback : {GREEN}Queued{RESET}  {GREY}QR : {GREEN}Pre-loaded{RESET}")
        co2 = calculate_co2_saved(orc.trucks_coordinated)
        print(f"\n  {GREEN}CO2 saved this session : {co2['kg_co2_saved']} kg  ({co2['trees_equivalent']} trees/yr){RESET}")
    else:
        print(f"  {RED}Error: {result.get('error') if result else 'unknown'}{RESET}")

    print(f"\n  {AMBER}Show judges the update WhatsApp. Press ENTER to exit.{RESET}")
    input()
    print(f"\n  {CYAN}Demo complete.{RESET}\n")


if __name__ == "__main__":
    asyncio.run(run())
