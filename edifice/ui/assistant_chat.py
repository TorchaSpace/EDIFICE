from __future__ import annotations

import os

from PySide6.QtCore import QThread, Qt, QTimer, Signal
from PySide6.QtGui import QFontMetrics
from PySide6.QtWidgets import (QHBoxLayout, QLabel, QLineEdit, QPushButton, QScrollArea, QSizePolicy, QVBoxLayout, QWidget)

from ..ai.agent import DEFAULT_MODEL, MODELS, ChatError, Toolbox, run_chat
from ..db import Store
from ..service import Project
from .dropdown import PremiumCombo
from .widgets import AMBER, G, MUTED, RED, SUB, Panel, header, qfont

TOOL_NAMES = {"list_buildings": "portföy özeti", "get_building": "bina verisi", "get_opportunities": "öneriler",
              "simulate_scenario": "senaryo hesabı", "best_package": "bütçe optimizasyonu", "get_monthly": "aylık tüketim",
              "get_equipment": "ekipman envanteri", "search_evidence": "kaynak kaydı"}
SUGGESTIONS = ["Bu binanın en büyük sorunu ne?", "Hangi öneriyle başlamalıyım?", "2 milyon ₺ bütçeyle ne yapmalıyım?",
               "Enerji sınıfım neden bu?", "Tasarruf oranları hangi kaynaklara dayanıyor?", "Portföyde en kötü bina hangisi?"]


class ChatState:
    """Sohbet geçmişi: bina değişse bile korunur (sayfa yeniden kurulsa da)."""

    def __init__(self):
        self.messages: list[dict] = []      # API biçimi
        self.display: list[tuple[str, str]] = []   # (rol, metin)


class ChatWorker(QThread):
    text = Signal(str)
    tool = Signal(str)
    failed = Signal(str)

    def __init__(self, key, model, state: ChatState, toolbox: Toolbox, building_name: str):
        super().__init__()
        self.key, self.model, self.state, self.toolbox, self.name = key, model, state, toolbox, building_name
        self.cancelled = False

    def run(self):
        try:
            run_chat(self.key, self.model, self.state.messages, self.toolbox, self.name,
                     self.text.emit, self.tool.emit, lambda: self.cancelled)
        except ChatError as e:
            self.failed.emit(str(e))
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
                             "Binanın gerçek verisini, hesap sonuçlarını ve kaynak kaydını okuyarak cevap verir."), 1)
        self.live = QLabel("●  LIVE")
        self.live.setStyleSheet(f"color: {G}; background: rgba(13,221,150,0.10); border: 1px solid rgba(13,221,150,0.25);"
                                "border-radius: 12px; padding: 4px 12px; font-size: 11px; font-weight: 800;")
        top.addWidget(self.live, 0, Qt.AlignTop)
        lay.addLayout(top)

        self.setup = self._build_setup()
        lay.addWidget(self.setup)

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
        self.input.setPlaceholderText("Binan, öneriler, finans ya da kaynaklar hakkında sor…")
        self.input.setMinimumHeight(44)
        self.input.returnPressed.connect(lambda: self.send(self.input.text()))
        self.btn = QPushButton("Gönder")
        self.btn.setObjectName("primary")
        self.btn.setMinimumHeight(44)
        self.btn.setCursor(Qt.PointingHandCursor)
        self.btn.clicked.connect(lambda: self.send(self.input.text()))
        key_btn = QPushButton("API anahtarı")
        key_btn.setObjectName("export")
        key_btn.setMinimumHeight(44)
        key_btn.setCursor(Qt.PointingHandCursor)
        key_btn.clicked.connect(lambda: self.setup.setVisible(not self.setup.isVisible()))
        row.addWidget(self.input, 1)
        row.addWidget(self.btn)
        row.addWidget(key_btn)
        lay.addLayout(row)

        for role, text in state.display:
            self._add(text, role == "user")
        if not state.display:
            self._add("Merhaba! Ben EDIFI'CE Asistanı. Binanın verisine, önerilere, finansa ve kaynaklara bakarak sorularını cevaplarım. "
                      "Aşağıdan bir soru seçebilir ya da kendi sorunu yazabilirsin.", False, remember=False)
        self._refresh_key_state()

    # ---- anahtar kurulumu
    def key(self) -> str:
        return (self.store.get_setting("ai_api_key") or os.environ.get("ANTHROPIC_API_KEY") or "").strip()

    def _build_setup(self) -> QWidget:
        p = Panel(eyebrow="Kurulum", title="Yapay zeka bağlantısı",
                  subtitle="Asistan, Anthropic Claude API'sini kullanır. Kendi API anahtarını gir (console.anthropic.com). "
                           "Anahtar yalnız bu bilgisayarda saklanır. Sorduğun sorular ve ilgili bina verisi cevap üretmek için "
                           "Anthropic'e gönderilir; göndermek istemiyorsan anahtar girme.")
        row = QHBoxLayout()
        row.setSpacing(10)
        self.key_edit = QLineEdit()
        self.key_edit.setEchoMode(QLineEdit.Password)
        self.key_edit.setPlaceholderText("sk-ant-…")
        self.key_edit.setMinimumHeight(40)
        self.model_box = PremiumCombo()
        self.model_box.addItems(list(MODELS))
        cur = self.store.get_setting("ai_model", DEFAULT_MODEL)
        for i, (label, mid) in enumerate(MODELS.items()):
            if mid == cur:
                self.model_box.setCurrentIndex(i)
        self.model_box.setMinimumHeight(40)
        self.model_box.setFixedWidth(210)
        save = QPushButton("Kaydet")
        save.setObjectName("primary")
        save.setMinimumHeight(40)
        save.setCursor(Qt.PointingHandCursor)
        save.clicked.connect(self._save_key)
        row.addWidget(self.key_edit, 1)
        row.addWidget(self.model_box)
        row.addWidget(save)
        p.lay.addSpacing(6)
        p.lay.addLayout(row)
        self.setup_msg = QLabel("")
        self.setup_msg.setStyleSheet(f"color: {SUB}; font-size: 12px; background: transparent;")
        p.lay.addWidget(self.setup_msg)
        return p

    def _save_key(self):
        text = self.key_edit.text().strip()
        if text:
            self.store.set_setting("ai_api_key", text)
        self.store.set_setting("ai_model", list(MODELS.values())[self.model_box.currentIndex()])
        self.key_edit.clear()
        self.setup_msg.setText("Kaydedildi.")
        self._refresh_key_state()
        QTimer.singleShot(900, lambda: self.setup.setVisible(not bool(self.key())))

    def _refresh_key_state(self):
        has = bool(self.key())
        self.setup.setVisible(not has)
        color = G if has else AMBER
        rgb = "13,221,150" if has else "245,158,11"
        self.live.setText("●  LIVE" if has else "○  KURULUM GEREKLİ")
        self.live.setStyleSheet(f"color: {color}; background: rgba({rgb},0.10); border: 1px solid rgba({rgb},0.25);"
                                "border-radius: 12px; padding: 4px 12px; font-size: 11px; font-weight: 800;")

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
        if not self.key():
            self.setup.setVisible(True)
            self.setup_msg.setText("Önce API anahtarını gir.")
            return
        self.input.clear()
        self._add(text, True)
        self.state.display.append(("user", text))
        self.state.messages.append({"role": "user", "content": text})
        self.current, self._buf = self._add("…", False), ""
        self._busy(True)
        projects = self.load_projects()
        model = self.store.get_setting("ai_model", DEFAULT_MODEL)
        self.worker = ChatWorker(self.key(), model, self.state, Toolbox(projects, self.project.building_id), self.project.building.name)
        self.worker.text.connect(self._on_text)
        self.worker.tool.connect(lambda n: self.status.setText(f"Veri okunuyor: {TOOL_NAMES.get(n, n)}…"))
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
        # başarısız turda kalan yarım kullanıcı mesajını geçmişten çıkar ki sonraki soru tutarlı olsun
        while self.state.messages and self.state.messages[-1]["role"] == "user":
            self.state.messages.pop()

    def _on_done(self):
        if self._buf.strip():
            self.state.display.append(("assistant", self._buf))
        self.status.setText("")
        self._busy(False)

    def _busy(self, on: bool):
        for w in (self.input, self.btn, *self.chips):
            w.setEnabled(not on)
        self.btn.setText("Yanıtlıyor…" if on else "Gönder")
        if not on:
            self.input.setFocus()
