"""Interactions:  click = open/close the input box · drag = move · right-click = menu."""
from __future__ import annotations

from PySide6.QtCore import QObject, QPoint, QTimer, Qt, Signal
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import (QApplication, QHBoxLayout, QLabel, QLineEdit, QMenu,
                               QPushButton, QVBoxLayout, QWidget)

from .. import events as E
from ..mood import state_for
from .sprites import SpriteSheet

SLEEP_AFTER_MS = 45_000


class Bridge(QObject):
    """Hops events from the agent thread onto the GUI thread."""
    event = Signal(object)


class SpriteWidget(QWidget):
    clicked = Signal()

    def __init__(self, sheet: SpriteSheet, scale: int) -> None:
        super().__init__()
        self.sheet, self.state, self.i = sheet, "idle", 0
        self.setFixedSize(sheet.fw * scale, sheet.fh * scale)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self._press: QPoint | None = None
        self._win_origin = QPoint()
        self._moved = False
        self.set_state("idle", force=True)

    def set_state(self, state: str, force: bool = False) -> None:
        resolved = self.sheet.resolve(state)
        if resolved == self.state and not force and self.timer.isActive():
            return
        self.state, self.i = resolved, 0
        self.timer.start(max(1, int(1000 / self.sheet.spec(resolved)["fps"])))
        self.update()

    def _tick(self) -> None:
        spec = self.sheet.spec(self.state)
        self.i += 1
        if self.i >= spec["frames"]:
            if spec.get("loop", True):
                self.i = 0
            else:
                self.set_state(spec.get("next", "idle"), force=True)
                return
        self.update()

    def paintEvent(self, _) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, False)
        p.drawPixmap(self.rect(), self.sheet.frame(self.state, self.i))

    def mousePressEvent(self, e) -> None:
        if e.button() == Qt.MouseButton.LeftButton:
            self._press = e.globalPosition().toPoint()
            self._win_origin = self.window().pos()
            self._moved = False

    def mouseMoveEvent(self, e) -> None:
        if self._press is not None:
            delta = e.globalPosition().toPoint() - self._press
            if delta.manhattanLength() > 4:
                self._moved = True
            if self._moved:
                self.window().move(self._win_origin + delta)

    def mouseReleaseEvent(self, e) -> None:
        if e.button() == Qt.MouseButton.LeftButton and self._press is not None and not self._moved:
            self.clicked.emit()
        self._press = None

    def contextMenuEvent(self, e) -> None:
        menu = QMenu(self)
        menu.addAction("Sleep", lambda: self.set_state("sleeping"))
        menu.addAction("Quit", QApplication.quit)
        menu.exec(e.globalPos())


class PetWindow(QWidget):
    def __init__(self, sheet: SpriteSheet, agent, runner, scale: int = 4) -> None:
        super().__init__()
        self.agent, self.runner = agent, runner
        self._pending_perm: str | None = None
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint
                            | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self.bubble = QLabel(wordWrap=True)
        self.bubble.setMaximumWidth(280)
        self.bubble.setStyleSheet(
            "background: rgba(255,255,255,240); color: #222; border: 2px solid #282d3c;"
            "border-radius: 8px; padding: 8px; font-size: 13px;")
        self.bubble.hide()

        self.allow, self.deny = QPushButton("Allow"), QPushButton("Deny")
        self.buttons = QWidget()
        row = QHBoxLayout(self.buttons)
        row.setContentsMargins(0, 0, 0, 0)
        row.addWidget(self.allow); row.addWidget(self.deny)
        self.buttons.hide()
        self.allow.clicked.connect(lambda: self._answer(True))
        self.deny.clicked.connect(lambda: self._answer(False))

        self.input = QLineEdit(placeholderText="say something…")
        self.input.setStyleSheet("background: white; color: #222; border: 2px solid #282d3c;"
                                 "border-radius: 8px; padding: 6px;")
        self.input.hide()
        self.input.returnPressed.connect(self._submit)

        self.sprite = SpriteWidget(sheet, scale)
        self.sprite.clicked.connect(self._toggle_input)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(6, 6, 6, 6); lay.setSpacing(4)
        lay.addWidget(self.bubble); lay.addWidget(self.buttons); lay.addWidget(self.input)
        lay.addWidget(self.sprite, alignment=Qt.AlignmentFlag.AlignHCenter)

        self.bubble_timer = QTimer(self, singleShot=True)
        self.bubble_timer.timeout.connect(lambda: (self.bubble.hide(), self._relayout()))
        self.sleep_timer = QTimer(self, singleShot=True, interval=SLEEP_AFTER_MS)
        self.sleep_timer.timeout.connect(self._maybe_sleep)
        self.sleep_timer.start()

    # --- events from the agent ------------------------------------------------
    def on_event(self, ev: E.Event) -> None:
        self.sleep_timer.start()
        if (st := state_for(ev)):
            self.sprite.set_state(st)
        if ev.kind == E.ASSISTANT_TEXT:
            self._say(ev.payload["text"])
        elif ev.kind == E.PERMISSION_REQUEST:
            self._ask(ev.payload)
        elif ev.kind == E.ERROR:
            self._say("Oops: " + ev.payload["message"], 8000)

    def _say(self, text: str, ms: int | None = None) -> None:
        self.bubble.setText(text)
        self.bubble.show()
        self.bubble_timer.start(ms or max(4000, 70 * len(text)))
        self._relayout()

    def _ask(self, p: dict) -> None:
        self._pending_perm = p["id"]
        self.bubble_timer.stop()  # keep the question up until answered
        args = ", ".join(f"{k}={v!r}" for k, v in p["args"].items())
        self.bubble.setText(f"Can I run {p['tool']}({args})?")
        self.bubble.show(); self.buttons.show()
        self._relayout()

    def _answer(self, allowed: bool) -> None:
        if self._pending_perm:
            self.agent.resolve_permission(self._pending_perm, allowed)
            self._pending_perm = None
        self.buttons.hide(); self.bubble.hide()
        self._relayout()

    # --- input ------------------------------------------------------------------
    def _toggle_input(self) -> None:
        self.sprite.set_state("alert", force=True)
        self.input.setVisible(not self.input.isVisible())
        self._relayout()
        if self.input.isVisible():
            self.activateWindow(); self.input.setFocus()

    def _submit(self) -> None:
        text = self.input.text().strip()
        self.input.clear(); self.input.hide()
        self._relayout()
        if text:
            self.runner.submit(text)

    # --- misc -------------------------------------------------------------------
    def _maybe_sleep(self) -> None:
        if self.sprite.state == "idle":
            self.sprite.set_state("sleeping")

    def _relayout(self) -> None:
        """Resize but keep the creature anchored: the window grows upward."""
        bottom = self.geometry().bottom()
        self.layout().activate()
        self.adjustSize()
        g = self.geometry()
        g.moveBottom(bottom)
        self.setGeometry(g)
