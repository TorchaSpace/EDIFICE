from __future__ import annotations

import time

from PySide6.QtCore import QThread, Qt, QTimer, Signal
from PySide6.QtGui import QFontMetrics
from PySide6.QtWidgets import (QHBoxLayout, QLabel, QLineEdit, QPushButton, QScrollArea, QSizePolicy, QVBoxLayout, QWidget)

from ..ai.local import LocalAssistant, Memory, stream_chunks
from ..ai.tools import Toolbox
from ..db import Store
from ..service import Project
from .widgets import G, MUTED, SUB, header, qfont

SUGGESTIONS = ["Bu binanın en büyük sorunu ne?", "Hangi öneriyle başlamalıyım?", "2 milyon ₺ bütçeyle ne yapmalıyım?",
               "Enerji sınıfım neden bu?", "Tasarruf oranları hangi kaynaklara dayanıyor?", "Portföyde en kötü bina hangisi?"]


class ChatState:
    """Sohbet geçmişi: bina değişse bile korunur (sayfa yeniden kurulsa da)."""

    def __init__(self):
        self.display: list[tuple[str, str]] = []   # (rol, metin)
        self.memory = Memory()


_ASSISTANT: LocalAssistant | None = None


def assistant() -> LocalAssistant:
    global _ASSISTANT
    if _ASSISTANT is None:
        _ASSISTANT = LocalAssistant()     # niyet modeli ilk kullanımda eğitilir (milisaniyeler)
    return _ASSISTANT


class ChatWorker(QThread):
    text = Signal(str)
    failed = Signal(str)

    def __init__(self, question: str, state: ChatState, toolbox: Toolbox):
        super().__init__()
        self.question, self.state, self.toolbox = question, state, toolbox
        self.cancelled = False

    def run(self):
        try:
            answer = assistant().answer(self.question, self.toolbox, self.state.memory)
            for chunk in stream_chunks(answer):       # canlı yazım etkisi
                if self.cancelled:
                    return
                self.text.emit(chunk)
                time.sleep(0.012)
        except Exception as e:     # beklenmeyen hata sohbeti kilitlemesin
            self.failed.emit(f"Beklenmeyen hata: {e}")


def _bubble(text: str, user: bool) -> QLabel:
    lbl = QLabel(text)
    lbl.setTextFormat(Qt.MarkdownText)
    lbl.setWordWrap(True)
    lbl.setTextInteractionFlags(Qt.TextSelectableByMouse)
    lbl.setMaximumWidth(760)
    if user:      # kullanıcı balonu metne göre daralır, asistan balonu 760 pikseline kadar genişler
        lbl.setFixedWidth(min(760, max(90, QFontMetrics(lbl.font()).horizontalAdvance(text) + 52)))
    else:
        lbl.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
    if user:
        lbl.setStyleSheet("background: rgba(13,221,150,0.10); border: 1px solid rgba(13,221,150,0.25); border-radius: 14px;"
                          "padding: 10px 14px; font-size: 13px;")
    else:
        lbl.setStyleSheet("background: #0B1624; border: 1px solid rgba(255,255,255,0.07); border-radius: 14px;"
                          "padding: 12px 16px; font-size: 13px;")
    return lbl


class ChatPage:
    def __init__(self, project: Project, store: Store, state: ChatState, load_projects):
        self.project, self.store, self.state, self.load_projects = project, store, state, load_projects
        self.worker: ChatWorker | None = None
        self.current: QLabel | None = None
        self._buf = ""
        self.widget = QWidget()
        self.widget.setObjectName("page")
        lay = QVBoxLayout(self.widget)
        lay.setContentsMargins(32, 26, 32, 22)
        lay.setSpacing(12)
        top = QHBoxLayout()
        top.addWidget(header("Yapay zeka", "EDIFI'CE Asistanı",
                             "Uygulamanın kendi yapay zekası: internet ya da dış servis kullanmaz; binanın gerçek verisini ve hesaplarını okuyarak cevap verir."), 1)
        self.live = QLabel("●  LIVE")
        self.live.setStyleSheet(f"color: {G}; background: rgba(13,221,150,0.10); border: 1px solid rgba(13,221,150,0.25);"
                                "border-radius: 12px; padding: 4px 12px; font-size: 11px; font-weight: 800;")
        top.addWidget(self.live, 0, Qt.AlignTop)
        lay.addLayout(top)

        self.area = QScrollArea()
        self.area.setWidgetResizable(True)
        self.area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.area.setFrameShape(QScrollArea.NoFrame)
        inner = QWidget()
        inner.setObjectName("page")
        self.msgs = QVBoxLayout(inner)
        self.msgs.setContentsMargins(0, 0, 8, 0)
        self.msgs.setSpacing(10)
        self.msgs.addStretch()
        self.area.setWidget(inner)
        lay.addWidget(self.area, 1)

        self.status = QLabel("")
        self.status.setStyleSheet(f"color: {MUTED}; font-size: 12px; background: transparent;")
        lay.addWidget(self.status)
        chips = QHBoxLayout()
        chips.setSpacing(8)
        self.chips = []
        for q in SUGGESTIONS[:4]:
            b = QPushButton(q)
            b.setObjectName("seg")
            b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(lambda _=False, t=q: self.send(t))
            chips.addWidget(b)
            self.chips.append(b)
        chips.addStretch()
        lay.addLayout(chips)
        row = QHBoxLayout()
        row.setSpacing(10)
        self.input = QLineEdit()
        self.input.setPlaceholderText("Binan, öneriler, bütçe, finans ya da kaynaklar hakkında sor…")
        self.input.setMinimumHeight(44)
        self.input.returnPressed.connect(lambda: self.send(self.input.text()))
        self.btn = QPushButton("Gönder")
        self.btn.setObjectName("primary")
        self.btn.setMinimumHeight(44)
        self.btn.setCursor(Qt.PointingHandCursor)
        self.btn.clicked.connect(lambda: self.send(self.input.text()))
        row.addWidget(self.input, 1)
        row.addWidget(self.btn)
        lay.addLayout(row)

        for role, text in state.display:
            self._add(text, role == "user")
        if not state.display:
            self._add("Merhaba! Ben EDIFI'CE Asistanı. Binanın verisine, önerilere, finansa ve kaynaklara bakarak sorularını cevaplarım. "
                      "Aşağıdan bir soru seçebilir ya da kendi sorunu yazabilirsin.", False, remember=False)

    # ---- sohbet
    def _add(self, text: str, user: bool, remember: bool = True) -> QLabel:
        lbl = _bubble(text, user)
        wrap = QHBoxLayout()
        wrap.setContentsMargins(0, 0, 0, 0)
        if user:
            wrap.addStretch()
            wrap.addWidget(lbl)
        else:
            wrap.addWidget(lbl, 1)
            wrap.addStretch(0)
        self.msgs.insertLayout(self.msgs.count() - 1, wrap)
        QTimer.singleShot(30, lambda: self.area.verticalScrollBar().setValue(self.area.verticalScrollBar().maximum()))
        return lbl

    def send(self, text: str):
        text = text.strip()
        if not text or (self.worker and self.worker.isRunning()):
            return
        self.input.clear()
        self._add(text, True)
        self.state.display.append(("user", text))
        self.current, self._buf = self._add("…", False), ""
        self._busy(True)
        self.worker = ChatWorker(text, self.state, Toolbox(self.load_projects(), self.project.building_id))
        self.worker.text.connect(self._on_text)
        self.worker.failed.connect(self._on_failed)
        self.worker.finished.connect(self._on_done)
        self.worker.start()

    def _on_text(self, delta: str):
        self._buf += delta
        if self.current is not None:
            self.current.setText(self._buf)
            sb = self.area.verticalScrollBar()
            sb.setValue(sb.maximum())

    def _on_failed(self, msg: str):
        if self.current is not None:
            self.current.setText(f"{self._buf}\n\n⚠ {msg}".strip())
            self.current.setStyleSheet(self.current.styleSheet().replace("rgba(255,255,255,0.07)", "rgba(244,63,94,0.4)"))
        self._buf += f"\n\n⚠ {msg}"

    def _on_done(self):
        if self._buf.strip():
            self.state.display.append(("assistant", self._buf))
        self._busy(False)

    def _busy(self, on: bool):
        for w in (self.input, self.btn, *self.chips):
            w.setEnabled(not on)
        self.btn.setText("Yanıtlıyor…" if on else "Gönder")
        if not on:
            self.input.setFocus()
