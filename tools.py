"""
Tool handlers the voice agent can call.

============================  TASK-SPECIFIC  ============================
At challenge start, add one function per tool the scenario needs and
register it in TOOL_REGISTRY. Each handler takes a dict of arguments and
returns a STRING (what the agent will read back to the caller).

The example below (`book_appointment`) is a placeholder to show the
pattern — delete or rewrite it once you know the real task.
========================================================================
"""
from typing import Any, Callable

from db import save_record


def book_appointment(args: dict[str, Any]) -> str:
    """EXAMPLE placeholder — replace with the real task's tool."""
    name = args.get("name", "the patient")
    date = args.get("date", "the requested date")
    time = args.get("time", "the requested time")
    save_record(
        "appointments",
        {"patient_name": name, "date": date, "time": time},
    )
    return f"Appointment booked for {name} on {date} at {time}."


def lookup_record(args: dict[str, Any]) -> str:
    """EXAMPLE placeholder — e.g. look up an order/patient/account."""
    ref = args.get("id") or args.get("reference", "")
    return f"Record {ref} found. (Replace with real lookup logic.)"


# Map the tool NAME (must match the name in the Vapi assistant config)
# to its handler function.
TOOL_REGISTRY: dict[str, Callable[[dict[str, Any]], str]] = {
    "book_appointment": book_appointment,
    "lookup_record": lookup_record,
}
