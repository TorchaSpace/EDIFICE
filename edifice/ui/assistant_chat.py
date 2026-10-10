from __future__ import annotations

import time

from PySide6.QtCore import QThread, Qt, QTimer, Signal
from PySide6.QtGui import QFontMetrics
from PySide6.QtWidgets import (QFrame, QHBoxLayout, QLabel, QLineEdit, QPushButton, QScrollArea, QSizePolicy, QVBoxLayout, QWidget)

from ..ai.local import INTENTS, LocalAssistant, Memory, stream_chunks
from ..ai.tools import Toolbox
from ..db import Store
from ..service import Project
from .dropdown import PremiumCombo
from .widgets import G, MUTED, SUB, Panel, header, qfont

SUGGESTIONS = ["Bu binanın en büyük sorunu ne?", "Hangi öneriyle başlamalıyım?", "2 milyon ₺ bütçeyle ne yapmalıyım?",
               "Skorum neden düştü?", "Elektrik mi doğalgaz mı daha çok?", "Portföyde en kötü bina hangisi?"]


INTENT_LABELS = {
    "overview": "Bina özeti", "problem": "Sorunlar / zayıf noktalar", "health": "Sağlık skoru", "rating": "Enerji sınıfı", "energy": "Enerji tüketimi",
    "carbon": "Karbon", "water": "Su", "cost": "Maliyet", "trend": "Yıllık değişim", "peak": "Pik ay", "anomaly": "Anomali",
    "opportunities": "Öneri listesi", "start": "Nereden başlamalı", "budget": "Bütçeye göre paket", "scenario": "Senaryo (ne olur?)",
    "finance": "Finans (NPV, geri ödeme)", "equipment": "Ekipman", "portfolio": "Portföy", "why": "Neden?", "compare": "Karşılaştırma",
    "evidence": "Kaynak / kanıt", "act_status": "İşlem: proje durumu", "act_report": "İşlem: rapor", "act_open": "İşlem: sayfa aç",
    "act_scenario": "İşlem: senaryo seç", "greet": "Selamlama / yardım"}


class ChatState:
    """Sohbet geçmişi: bina değişse bile korunur (sayfa yeniden kurulsa da)."""

    def __init__(self):
        self.display: list[tuple[str, str, dict | None]] = []   # (rol, metin, grafik)
        self.memory = Memory()


def build_assistant(store: Store | None) -> LocalAssistant:
    """Yerleşik örneklere kullanıcının öğrettiği örnekleri ekleyip modeli (milisaniyelerde) yeniden eğitir."""
    extra = [(i, t) for _, i, t in store.list_examples()] if store is not None else []
    return LocalAssistant(extra)


class ChatWorker(QThread):
    text = Signal(str)
    extras = Signal(object, object, object)     # eylemler, grafik, anlaşılmayan soru
    failed = Signal(str)

    def __init__(self, ai: LocalAssistant, question: str, state: ChatState, toolbox: Toolbox):
        super().__init__()
        self.ai, self.question, self.state, self.toolbox = ai, question, state, toolbox
        self.cancelled = False

    def run(self):
        try:
            mem = self.state.memory
            answer = self.ai.answer(self.question, self.toolbox, mem)
            for chunk in stream_chunks(answer):       # canlı yazım etkisi
                if self.cancelled:
                    return
                self.text.emit(chunk)
                time.sleep(0.012)
            self.extras.emit(list(mem.actions), mem.chart, mem.unknown)
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


def chart_widget(spec: dict) -> QWidget:
    """Cevaba eşlik eden mini grafik (aylık tüketim ya da kümülatif nakit akışı)."""
    from .charts import CashFlowChart
    from .pages import area_chart
    box = QFrame()
    box.setObjectName("card")
    box.setMaximumWidth(760)
    lay = QVBoxLayout(box)
    lay.setContentsMargins(16, 12, 16, 12)
    lay.setSpacing(4)
    t = QLabel(spec["title"])
    t.setStyleSheet(f"color: {SUB}; font-size: 12px; font-weight: 700; background: transparent;")
    lay.addWidget(t)
    if spec["kind"] == "area":
        lay.addWidget(area_chart(spec["cats"], spec["groups"], scale=spec.get("scale", 1.0), unit=spec.get("unit", ""), min_h=200))
    else:
        lay.addWidget(CashFlowChart(spec["years"], spec["cum"], spec.get("payback"), min_h=200))
    return box


class ChatPage:
    def __init__(self, project: Project, store: Store, state: ChatState, load_projects, on_action=None):
        self.project, self.store, self.state, self.load_projects = project, store, state, load_projects
        self.on_action = on_action or (lambda a: None)
        self.ai = build_assistant(store)
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
        for q in SUGGESTIONS[:5]:
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
        self.input.setPlaceholderText("Sor ya da komut ver: “VFD'yi planlandı yap”, “portföyü aç”, “2 milyon bütçeyle ne yapmalıyım?”…")
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

        for role, text, chart in state.display:
            self._add(text, role == "user")
            if chart:
                self._add_chart(chart)
        if not state.display:
            self._add("Merhaba! Ben EDIFI'CE Asistanı. Binanın verisine, önerilere, finansa ve kaynaklara bakarak sorularını cevaplarım; "
                      "ayrıca komut da verebilirsin (proje durumu değiştirme, sayfa açma, senaryo seçme, rapor). Aşağıdan bir soru seçebilir "
                      "ya da kendi sorunu yazabilirsin.", False)

    def reload_ai(self):
        """Eğitim sekmesinde yeni örnek öğretilince modeli yeniden eğitir."""
        self.ai = build_assistant(self.store)

    # ---- sohbet
    def _add(self, text: str, user: bool) -> QLabel:
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

    def _add_chart(self, spec: dict):
        w = chart_widget(spec)
        wrap = QHBoxLayout()
        wrap.setContentsMargins(0, 0, 0, 0)
        wrap.addWidget(w, 1)
        wrap.addStretch(0)
        self.msgs.insertLayout(self.msgs.count() - 1, wrap)
        QTimer.singleShot(60, lambda: self.area.verticalScrollBar().setValue(self.area.verticalScrollBar().maximum()))

    def send(self, text: str):
        text = text.strip()
        if not text or (self.worker and self.worker.isRunning()):
            return
        self.input.clear()
        self._add(text, True)
        self.state.display.append(("user", text, None))
        self.current, self._buf = self._add("…", False), ""
        self._busy(True)
        self.worker = ChatWorker(self.ai, text, self.state, Toolbox(self.load_projects(), self.project.building_id))
        self.worker.text.connect(self._on_text)
        self.worker.extras.connect(self._on_extras)
        self.worker.failed.connect(self._on_failed)
        self.worker.finished.connect(self._on_done)
        self.worker.start()

    def _on_text(self, delta: str):
        self._buf += delta
        if self.current is not None:
            self.current.setText(self._buf)
            sb = self.area.verticalScrollBar()
            sb.setValue(sb.maximum())

    def _on_extras(self, actions, chart, unknown):
        self._chart = chart
        if chart:
            self._add_chart(chart)
        if unknown:
            self.store.log_unknown(unknown)       # Eğitim sekmesinde öğretilebilsin
        for a in actions:
            self.on_action(a)

    def _on_failed(self, msg: str):
        if self.current is not None:
            self.current.setText(f"{self._buf}\n\n⚠ {msg}".strip())
        self._buf += f"\n\n⚠ {msg}"

    def _on_done(self):
        if self._buf.strip():
            self.state.display.append(("assistant", self._buf, getattr(self, "_chart", None)))
        self._chart = None
        self._busy(False)

    def _busy(self, on: bool):
        for w in (self.input, self.btn, *self.chips):
            w.setEnabled(not on)
        self.btn.setText("Yanıtlıyor…" if on else "Gönder")
        if not on:
            self.input.setFocus()


class _RefreshOnShow(QWidget):
    def __init__(self, cb):
        super().__init__()
        self._cb = cb

    def showEvent(self, e):
        super().showEvent(e)
        self._cb()


class TrainingPage:
    """Eğitim: asistanın anlamadığı sorular listelenir; doğru niyeti seçip “Öğret” dersen model o örnekle yeniden eğitilir."""

    def __init__(self, store: Store, on_taught):
        self.store, self.on_taught = store, on_taught
        self.widget = _RefreshOnShow(lambda: self.refresh())
        self.widget.setObjectName("page")
        self.outer = QVBoxLayout(self.widget)
        self.outer.setContentsMargins(32, 26, 32, 22)
        self.outer.setSpacing(14)
        self.outer.addWidget(header("Eğitim", "Asistanı eğit",
                                    "Asistanın anlayamadığı sorular burada birikir. Hangi konuya ait olduğunu seç ve “Öğret”e bas; "
                                    "benzer sorular artık doğru cevaplanır."))
        self.body = QVBoxLayout()
        self.body.setSpacing(14)
        self.outer.addLayout(self.body)
        self.outer.addStretch()
        self.refresh()

    def _clear(self, lay):
        while lay.count():
            it = lay.takeAt(0)
            if it.widget():
                it.widget().deleteLater()
            elif it.layout():
                self._clear(it.layout())

    def refresh(self):
        self._clear(self.body)
        unknown = self.store.list_unknown()
        p = Panel(eyebrow="Anlaşılmayanlar", title=f"{len(unknown)} soru bekliyor",
                  subtitle="Sohbette anlaşılmayan her soru otomatik buraya düşer." if unknown else "Şimdilik anlaşılmayan soru yok.")
        for uid, q in unknown:
            row = QHBoxLayout()
            row.setSpacing(10)
            lbl = QLabel(q)
            lbl.setWordWrap(True)
            lbl.setStyleSheet("font-size: 13px; font-weight: 600; background: transparent;")
            combo = PremiumCombo()
            combo.addItems(list(INTENT_LABELS.values()))
            combo.setFixedWidth(230)
            combo.setMinimumHeight(34)
            teach = QPushButton("Öğret")
            teach.setObjectName("primary")
            teach.setMinimumHeight(34)
            teach.setCursor(Qt.PointingHandCursor)
            drop = QPushButton("Sil")
            drop.setObjectName("export")
            drop.setMinimumHeight(34)
            drop.setCursor(Qt.PointingHandCursor)
            teach.clicked.connect(lambda _=False, i=uid, t=q, c=combo: self.teach(i, t, list(INTENT_LABELS)[c.currentIndex()]))
            drop.clicked.connect(lambda _=False, i=uid: (self.store.delete_unknown(i), self.refresh()))
            row.addWidget(lbl, 1)
            row.addWidget(combo)
            row.addWidget(teach)
            row.addWidget(drop)
            p.lay.addLayout(row)
        self.body.addWidget(p)
        ex = self.store.list_examples()
        q = Panel(eyebrow="Öğretilenler", title=f"{len(ex)} örnek", subtitle="Yerleşik örneklere ek olarak modele öğrettiklerin.")
        for eid, intent, text in ex:
            row = QHBoxLayout()
            lbl = QLabel(f"{text}  <span style='color:{MUTED}'>→ {INTENT_LABELS.get(intent, intent)}</span>")
            lbl.setStyleSheet("font-size: 13px; background: transparent;")
            rm = QPushButton("Kaldır")
            rm.setObjectName("export")
            rm.setCursor(Qt.PointingHandCursor)
            rm.clicked.connect(lambda _=False, i=eid: (self.store.delete_example(i), self.on_taught(), self.refresh()))
            row.addWidget(lbl, 1)
            row.addWidget(rm)
            q.lay.addLayout(row)
        self.body.addWidget(q)

    def teach(self, uid: int, text: str, intent: str):
        self.store.add_example(intent, text)
        self.store.delete_unknown(uid)
        self.on_taught()
        self.refresh()
