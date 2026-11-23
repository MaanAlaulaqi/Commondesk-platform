"""Ordinary JSON console records. No event database or caller-supplied log messages."""

import json
import logging
import re
import sys
import time
import uuid
from contextvars import ContextVar
from functools import wraps

from fastapi import APIRouter, HTTPException, Request, Response
from starlette.datastructures import MutableHeaders

router = APIRouter()
ACTIONS = frozenset(
    """
explore_open report_open search_open insights_open case_open translation_request translation_shown
translation_error report_submit report_saved search_submit filter_apply help_open control_button
control_link control_select control_checkbox control_file control_field control_other interface_language
theme_change source_select answer_submit report_prepare status_update service_select map_interact
report_language_select answer_language_select page_previous page_next list_view map_view clear_selection
photo_remove location_apply location_current location_clear report_edit related_search translation_retry control_retry
""".split()
)
MAX_EVENT_BYTES = 320
MAX_EVENTS_PER_MINUTE = 600
UUID4 = re.compile(
    rb"[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}", re.I
)
UI_LANGUAGES = {b"en", b"ar", b"th", b"hi", b"ur"}
ui_language = ContextVar("ui_language", default=None)
correlation_id = ContextVar("correlation_id", default=None)
logger = logging.getLogger("commondesk.console")
if not logger.handlers:
    logger.addHandler(logging.StreamHandler(sys.stdout))
logger.setLevel(logging.INFO)
logger.propagate = False


def emit(event, **fields):
    logger.info(
        json.dumps(
            {
                "event": event,
                "correlationId": correlation_id.get(),
                "uiLanguage": ui_language.get(),
                **fields,
            },
            separators=(",", ":"),
        )
    )


def operation(fn):
    """Measure named application operations without inspecting call arguments or results."""

    @wraps(fn)
    def call(*args, **kwargs):
        token = None
        if correlation_id.get() is None:  # detached index worker
            token = correlation_id.set(str(uuid.uuid4()))
        start = time.monotonic()
        outcome = "error"
        try:
            result = fn(*args, **kwargs)
            outcome = "ok"
            return result
        finally:
            emit(
                "operation",
                function=fn.__name__,
                outcome=outcome,
                durationMs=round((time.monotonic() - start) * 1000),
            )
            if token is not None:
                correlation_id.reset(token)

    return call


class RequestConsole:
    def __init__(self, app):
        self.app = app
        self.minute = -1
        self.event_requests = 0

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        is_event = scope["method"] == "POST" and scope["path"] == "/api/ui-events"
        if is_event:
            # Fixed memory per server process. Limit before parsing bodies or emitting lines.
            minute = int(time.monotonic() // 60)
            if self.minute != minute:
                self.minute = minute
                self.event_requests = 0
            if self.event_requests >= MAX_EVENTS_PER_MINUTE:
                return await Response(status_code=429, headers={"Retry-After": "60"})(
                    scope, receive, send
                )
            self.event_requests += 1

        supplied = [v for k, v in scope["headers"] if k == b"x-correlation-id"]
        valid = len(supplied) == 1 and UUID4.fullmatch(supplied[0]) is not None
        cid = supplied[0].decode("ascii").lower() if valid else str(uuid.uuid4())
        languages = [v for k, v in scope["headers"] if k == b"x-ui-language"]
        lang = (
            languages[0].decode("ascii")
            if len(languages) == 1 and languages[0] in UI_LANGUAGES
            else None
        )
        language_token = ui_language.set(lang)
        token = correlation_id.set(cid)
        scope["commondesk_valid_id"] = valid
        started = time.monotonic()
        status = 500

        async def respond(message):
            nonlocal status
            if message["type"] == "http.response.start":
                status = message["status"]
                MutableHeaders(scope=message)["X-Correlation-ID"] = cid
            await send(message)

        try:
            await self.app(scope, receive, respond)
        finally:
            # Only framework-declared route templates and handler names reach the logger.
            route = scope.get("route")
            method = scope["method"]
            fields = dict(
                method=method
                if method
                in {"GET", "POST", "OPTIONS", "HEAD", "PUT", "PATCH", "DELETE"}
                else "OTHER",
                route=getattr(route, "path", None)
                or ("/api/ui-events" if is_event else "unmatched"),
                function=getattr(route, "name", None) or "unmatched",
                status=status,
                durationMs=round((time.monotonic() - started) * 1000),
            )
            if "commondesk_action" in scope:
                fields["action"] = scope["commondesk_action"]
            emit("ui" if is_event else "api", **fields)
            correlation_id.reset(token)
            ui_language.reset(language_token)


@router.post("/api/ui-events", status_code=204)
async def ui_event(request: Request):
    if not request.scope.get("commondesk_valid_id"):
        raise HTTPException(422, "A UUIDv4 correlation ID is required.")
    if (
        request.scope.get("query_string")
        or request.headers.get("content-type", "").split(";")[0].lower().strip()
        != "application/json"
    ):
        raise HTTPException(422, "Expected a JSON action.")
    raw = await request.body()
    if len(raw) > MAX_EVENT_BYTES:
        raise HTTPException(413, "Action too large.")

    def unique_keys(pairs):
        result = dict(pairs)
        if len(result) != len(pairs):
            raise ValueError("Duplicate field")
        return result

    try:
        data = json.loads(raw, object_pairs_hook=unique_keys)
    except (ValueError, UnicodeError):
        raise HTTPException(422, "Invalid action.") from None
    if (
        not isinstance(data, dict)
        or set(data) != {"action"}
        or not isinstance(data["action"], str)
        or data["action"] not in ACTIONS
    ):
        raise HTTPException(422, "Invalid action.")
    request.scope["commondesk_action"] = data["action"]
    return Response(status_code=204)
