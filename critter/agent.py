"""Agent loop"""
from __future__ import annotations

import asyncio
import threading
import uuid

from . import events as E
from .tools import ToolRegistry

SYSTEM = (
    "You are a tiny desktop creature that helps your owner. Be warm, brief and "
    "a little playful. Use tools when they help; keep replies to a sentence or two."
)
MAX_STEPS = 4
PERMISSION_TIMEOUT_S = 120


class Agent:
    def __init__(self, backend, registry: ToolRegistry, bus: E.EventBus, system: str = SYSTEM):
        self.backend, self.registry, self.bus, self.system = backend, registry, bus, system
        self.history: list[dict] = []
        self.loop: asyncio.AbstractEventLoop | None = None
        self._pending: dict[str, asyncio.Future] = {}

    async def handle(self, text: str) -> None:
        self.bus.publish(E.USER_MESSAGE, text=text)
        self.history.append({"role": "user", "content": text})
        try:
            for _ in range(MAX_STEPS):
                self.bus.publish(E.THINKING)
                resp = await self.backend.step(self.history, self.registry.schemas(), self.system)
                self.history.append({"role": "assistant", "content": resp.blocks()})
                if resp.text:
                    self.bus.publish(E.ASSISTANT_TEXT, text=resp.text)
                if not resp.tool_calls:
                    break
                results = [await self._run_tool(c) for c in resp.tool_calls]
                self.history.append({"role": "user", "content": results})
            self.bus.publish(E.DONE)
        except Exception as e:
            self.bus.publish(E.ERROR, message=f"{type(e).__name__}: {e}")

    async def _run_tool(self, call) -> dict:
        def result(content: str, is_error: bool = False) -> dict:
            return {"type": "tool_result", "tool_use_id": call.id,
                    "content": content, "is_error": is_error}

        t = self.registry.get(call.name)
        if t is None:
            return result(f"Unknown tool {call.name}", True)
        if t.tier == "ask" and not await self._ask(call):
            self.bus.publish(E.TOOL_FINISHED, name=call.name, ok=False, result="denied")
            return result("The user denied permission.", True)
        self.bus.publish(E.TOOL_STARTED, name=call.name, args=call.args, state=t.state)
        try:
            out = str(await asyncio.to_thread(t.fn, **call.args))
            self.bus.publish(E.TOOL_FINISHED, name=call.name, ok=True, result=out[:200])
            return result(out)
        except Exception as e:
            self.bus.publish(E.TOOL_FINISHED, name=call.name, ok=False, result=str(e))
            return result(f"{type(e).__name__}: {e}", True)

    async def _ask(self, call) -> bool:
        pid = uuid.uuid4().hex[:8]
        fut = asyncio.get_running_loop().create_future()
        self._pending[pid] = fut
        self.bus.publish(E.PERMISSION_REQUEST, id=pid, tool=call.name, args=call.args)
        try:
            return await asyncio.wait_for(fut, PERMISSION_TIMEOUT_S)
        except asyncio.TimeoutError:
            return False 
        finally:
            self._pending.pop(pid, None)

    def resolve_permission(self, pid: str, allowed: bool) -> None:
        """Thread-safe: call from the UI thread."""
        def _set() -> None:
            fut = self._pending.get(pid)
            if fut and not fut.done():
                fut.set_result(allowed)
        assert self.loop is not None
        self.loop.call_soon_threadsafe(_set)


class AgentRunner:
    """Runs the agent's asyncio loop on a background thread."""

    def __init__(self, agent: Agent) -> None:
        self.agent = agent
        self.loop = asyncio.new_event_loop()
        agent.loop = self.loop
        threading.Thread(target=self._run, daemon=True).start()

    def _run(self) -> None:
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()

    def submit(self, text: str):
        return asyncio.run_coroutine_threadsafe(self.agent.handle(text), self.loop)

    def stop(self) -> None:
        self.loop.call_soon_threadsafe(self.loop.stop)
