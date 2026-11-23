"""Render the latest recorded status of one case from structured event evidence."""

import json
from datetime import datetime
from pathlib import Path


TEMPLATES = json.loads(
    Path(__file__).with_name("templates.json").read_text(encoding="utf-8")
)
STATUS_OUTCOMES = {
    "reported": "no_update",
    "assigned": "assigned",
    "completed": "completed",
}


def case_status(case_id, events):
    """Select the latest timestamp and the distinct event IDs supporting its status."""
    timestamps_and_statuses = {}
    for event in events:
        if not isinstance(event, dict) or event.get("case_id") != case_id:
            continue
        event_id = event.get("event_id")
        status = event.get("status")
        if (
            not isinstance(event_id, str)
            or not event_id.strip()
            or not event_id.isprintable()
        ):
            return "no_evidence", []
        if "[" in event_id or "]" in event_id:
            return "no_evidence", []
        if not isinstance(status, str) or status not in STATUS_OUTCOMES:
            return "no_evidence", []
        try:
            timestamp = datetime.fromisoformat(event.get("at"))
        except (TypeError, ValueError):
            return "no_evidence", []
        if timestamp.tzinfo is None:
            return "no_evidence", []

        evidence = (timestamp, status)
        if (
            event_id in timestamps_and_statuses
            and timestamps_and_statuses[event_id] != evidence
        ):
            return "no_evidence", []
        timestamps_and_statuses[event_id] = evidence

    if not timestamps_and_statuses:
        return "no_evidence", []
    latest = max(timestamp for timestamp, _ in timestamps_and_statuses.values())
    citations = sorted(
        key
        for key, (timestamp, _) in timestamps_and_statuses.items()
        if timestamp == latest
    )
    outcomes = {STATUS_OUTCOMES[timestamps_and_statuses[key][1]] for key in citations}
    outcome = outcomes.pop() if len(outcomes) == 1 else "conflict"
    return outcome, citations


def render_answer(language, case_id, events):
    """Return text, citation IDs and outcome for a supplied case's latest status.

    The caller supplies the selected case's event history (plus any other cases).
    Case and event IDs are opaque strings. Each matching event must have a unique
    or consistently repeated ID, a timezone-aware ISO timestamp and a recognized
    status. Unusable matching evidence yields an uncited abstention.
    """
    if not isinstance(language, str) or language not in TEMPLATES:
        raise ValueError("Unsupported answer language")
    if not isinstance(case_id, str) or not case_id.strip():
        raise ValueError("A case ID is required")
    if not isinstance(events, list):
        raise ValueError("Expected a list of events")

    outcome, citations = case_status(case_id, events)
    text = TEMPLATES[language][outcome]
    if citations:
        text += " " + " ".join(f"[{event_id}]" for event_id in citations)
    return {"text": text, "citations": citations, "outcome": outcome}
