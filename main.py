"""Run:  python main.py            (uses Claude if ANTHROPIC_API_KEY is set, else the mock)
       python main.py --mock      (force the offline mock backend)
       python main.py --scale 6   (bigger creature)"""
import argparse
import logging
import os
import sys
from pathlib import Path

from critter import builtin_tools, events as E
from critter.agent import Agent, AgentRunner
from critter.backends import AnthropicBackend, MockBackend
from critter.tools import ToolRegistry

ROOT = Path(__file__).parent


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mock", action="store_true", help="use the offline mock backend")
    ap.add_argument("--scale", type=int, default=4, help="pixel scale factor")
    ap.add_argument("--sprites", default=str(ROOT / "assets/sprites/blob.json"))
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO)

    from PySide6.QtWidgets import QApplication
    from critter.ui.sprites import SpriteSheet
    from critter.ui.window import Bridge, PetWindow

    use_claude = bool(os.getenv("ANTHROPIC_API_KEY")) and not args.mock
    backend = AnthropicBackend() if use_claude else MockBackend()
    logging.info("backend: %s", type(backend).__name__)

    bus = E.EventBus()
    registry = ToolRegistry().discover(builtin_tools)
    agent = Agent(backend, registry, bus)
    runner = AgentRunner(agent)

    app = QApplication(sys.argv)
    window = PetWindow(SpriteSheet(args.sprites), agent, runner, scale=args.scale)
    bridge = Bridge()
    bridge.event.connect(window.on_event)
    bus.subscribe(bridge.event.emit)

    window.show()
    screen = app.primaryScreen().availableGeometry()
    window.move(screen.right() - window.width() - 40, screen.bottom() - window.height() - 40)
    code = app.exec()
    runner.stop()
    return code


if __name__ == "__main__":
    sys.exit(main())
