from __future__ import annotations

from . import events as E


def state_for(ev: E.Event) -> str | None:
    k, p = ev.kind, ev.payload
    if k == E.MOOD:
        return p.get("state")
    if k == E.USER_MESSAGE:
        return "alert"
    if k == E.THINKING:
        return "thinking"
    if k == E.TOOL_STARTED:
        return p.get("state") or "working"
    if k == E.TOOL_FINISHED:
        return "thinking" if p.get("ok", True) else "confused"
    if k == E.PERMISSION_REQUEST:
        return "curious"
    if k == E.DONE:
        return "happy"
    if k == E.ERROR:
        return "confused"
    return None
