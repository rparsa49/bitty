from __future__ import annotations

import asyncio
import os
import uuid
from dataclasses import dataclass, field


@dataclass
class ToolCall:
    id: str
    name: str
    args: dict


@dataclass
class Response:
    text: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)

    def blocks(self) -> list[dict]:
        out: list[dict] = []
        if self.text:
            out.append({"type": "text", "text": self.text})
        out += [{"type": "tool_use", "id": c.id, "name": c.name, "input": c.args}
                for c in self.tool_calls]
        return out


class MockBackend:
    """Offline stand-in so you can develop the creature without an API key.
    Try: "what time is it", "add a note: buy milk", "find resume"."""

    async def step(self, history: list[dict], tools: list[dict], system: str) -> Response:
        await asyncio.sleep(0.8)
        last = history[-1]
        if isinstance(last["content"], list):
            results = " ".join(str(b["content"]) for b in last["content"])
            return Response(text=f"Done! {results}")
        msg = last["content"]
        low = msg.lower()
        call = lambda name, **args: Response(
            text="On it!", tool_calls=[ToolCall(uuid.uuid4().hex[:8], name, args)])
        if "time" in low:
            return call("current_time")
        if "note" in low:
            return call("add_note", text=msg.split(":", 1)[-1].strip())
        if "find" in low or "search" in low:
            return call("search_files", pattern=msg.split()[-1])
        return Response(text=f"You said: {msg}")


class AnthropicBackend:
    """pip install anthropic; export ANTHROPIC_API_KEY=...
    Override the model with CRITTER_MODEL."""

    def __init__(self, model: str | None = None) -> None:
        import anthropic

        self.client = anthropic.AsyncAnthropic()
        self.model = model or os.getenv("CRITTER_MODEL", "claude-sonnet-5-5")

    async def step(self, history: list[dict], tools: list[dict], system: str) -> Response:
        r = await self.client.messages.create(
            model=self.model, max_tokens=1024, system=system,
            tools=tools, messages=history,
        )
        resp = Response()
        for b in r.content:
            if b.type == "text":
                resp.text += b.text
            elif b.type == "tool_use":
                resp.tool_calls.append(ToolCall(b.id, b.name, dict(b.input)))
        return resp
