from __future__ import annotations

import time

from PySide6.QtCore import QThread, Qt, QTimer, Signal
from PySide6.QtGui import QFontMetrics
from PySide6.QtWidgets import (QFrame, QHBoxLayout, QLabel, QLineEdit, QPushButton, QScrollArea, QSizePolicy, QVBoxLayout, QWidget)

from ..ai.local import INTENT_LABELS, LocalAssistant, Memory, accepts, stream_chunks
from ..ai.tools import Toolbox
from ..db import Store
from ..service import Project
from .dropdown import PremiumCombo
from .widgets import AMBER, G, MUTED, SUB, Panel, header

SUGGESTIONS = ["Bu binanın en büyük sorunu ne?", "Hangi öneriyle başlamalıyım?", "2 milyon ₺ bütçeyle ne yapmalıyım?",
               "Skorum neden düştü?", "Elektrik mi doğalgaz mı daha çok?", "Portföyde en kötü bina hangisi?"]


class ChatState:
    """Sohbet geçmişi: bina değişse bile korunur (sayfa yeniden kurulsa da)."""

    def __init__(self):
        self.display: list[tuple[str, str, dict | None, dict | None]] = []   # (rol, metin, grafik, meta)
        self.memory = Memory()


def build_assistant(store: Store | None) -> LocalAssistant:
    """Yerleşik örneklere kullanıcının öğrettiği örnekleri ekleyip modeli (milisaniyelerde) yeniden eğitir."""
    extra = [(i, t) for _, i, t in store.list_examples()] if store is not None else []
    return LocalAssistant(extra)


_LIVE_WORKERS: set = set()     # çalışan iş parçacıkları sayfa yok edilse bile bitene kadar canlı tutulur (QThread çökmesini önler)


class ChatWorker(QThread):
    text = Signal(str)
    extras = Signal(object)     # eylemler, grafik, anlaşılmayan soru, niyet, öneriler, öğrenilenler
    failed = Signal(str)

    def __init__(self, ai: LocalAssistant, question: str, state: ChatState, toolbox: Toolbox, forced: str | None = None):
        super().__init__()
        self.ai, self.question, self.state, self.toolbox, self.forced = ai, question, state, toolbox, forced
        self.cancelled = False

    def run(self):
        try:
            mem = self.state.memory
            answer = (self.ai.answer_as(self.forced, self.question, self.toolbox, mem) if self.forced
                      else self.ai.answer(self.question, self.toolbox, mem))
            for chunk in stream_chunks(answer):       # canlı yazım etkisi
                if self.cancelled:
                    return
                self.text.emit(chunk)
                time.sleep(0.012)
            self.extras.emit({"actions": list(mem.actions), "chart": mem.chart, "unknown": mem.unknown, "intent": mem.answered,
                              "suggest": list(mem.suggest), "learn": list(mem.learn), "question": self.question})
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

        for role, text, chart, meta in state.display:
            self._add(text, role == "user")
            if chart:
                self._add_chart(chart)
            if meta and (meta.get("intent") or meta.get("suggest")):
                self._add_feedback(meta, interactive=False)
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

    def send(self, text: str, forced: str | None = None, echo: bool = True):
        text = text.strip()
        if not text or (self.worker and self.worker.isRunning()):
            return
        self.input.clear()
        if echo:
            self._add(text, True)
            self.state.display.append(("user", text, None, None))
        self.current, self._buf = self._add("…", False), ""
        self._busy(True)
        projects = self.load_projects()
        weather = {bid: self.store.load_weather(p.building.lat, p.building.lon) for bid, p in projects.items() if p.building.lat is not None}
        tb = Toolbox(projects, self.project.building_id, weather)
        from .. import solar as _solar
        for bid, p in projects.items():
            if p.building.lat is not None:
                got = self.store.load_climate(p.building.lat, p.building.lon)
                if got:
                    tb.climate[bid] = got
        for bid, p in projects.items():
            if p.building.lat is not None:
                y = self.store.load_solar(p.building.lat, p.building.lon, _solar.DEFAULT_ANGLE, _solar.DEFAULT_ASPECT)
                if y:
                    tb.solar[bid] = y
        for bid in projects:
            months = self.store.load_project_months(bid)
            tb.completed[bid] = {c: (y, months.get(c, 1)) for c, (s, y) in self.store.load_projects(bid).items() if s == "Tamamlandı"}
        self.worker = ChatWorker(self.ai, text, self.state, tb, forced)
        self.worker.text.connect(self._on_text)
        self.worker.extras.connect(self._on_extras)
        self.worker.failed.connect(self._on_failed)
        self.worker.finished.connect(self._on_done)
        _LIVE_WORKERS.add(self.worker)
        self.worker.finished.connect(lambda w=self.worker: _LIVE_WORKERS.discard(w))
        self.worker.start()

    def _on_text(self, delta: str):
        self._buf += delta
        if self.current is not None:
            self.current.setText(self._buf)
            sb = self.area.verticalScrollBar()
            sb.setValue(sb.maximum())

    def _on_extras(self, info: dict):
        self._chart = info["chart"]
        self._meta = {"question": info["question"], "intent": info["intent"], "suggest": info["suggest"], "feedback": None}
        if info["chart"]:
            self._add_chart(info["chart"])
        if info["unknown"]:
            self.store.log_unknown(info["unknown"])       # Eğitim sekmesinde öğretilebilsin
        for a in info["actions"]:
            self.on_action(a)
        for intent, text in info["learn"]:               # yeniden sorma sinyali: ilk soruyu da öğren
            if self.learn(intent, text):
                self.status.setText(f"Öğrendim: “{text}” sorusunu da artık anlıyorum.")
        self._add_feedback(self._meta, interactive=True)

    def learn(self, intent: str, text: str) -> bool:
        """Bozulma korumasından geçerse örneği kaydeder ve modeli yeniden eğitir."""
        existing = [(i, t) for _, i, t in self.store.list_examples()]
        if (intent, text) in existing:
            return True
        if not accepts(existing, intent, text):
            return False
        self.store.add_example(intent, text)
        for uid, q in self.store.list_unknown():
            if q == text:
                self.store.delete_unknown(uid)
        self.reload_ai()
        return True

    def _add_feedback(self, meta: dict, interactive: bool):
        """Cevabın altında 👍/👎 ya da (anlaşılmadıysa) “şunu mu demek istedin?” düğmeleri."""
        row = QHBoxLayout()
        row.setContentsMargins(4, 0, 0, 0)
        row.setSpacing(6)
        if meta.get("suggest") and not meta.get("intent"):
            hint = QLabel("Şunu mu demek istedin?")
            hint.setStyleSheet(f"color: {SUB}; font-size: 12px; background: transparent;")
            row.addWidget(hint)
            for intent in meta["suggest"]:
                b = QPushButton(INTENT_LABELS.get(intent, intent))
                b.setObjectName("seg")
                b.setCursor(Qt.PointingHandCursor)
                b.setEnabled(interactive)
                b.clicked.connect(lambda _=False, i=intent, m=meta: self._choose(m, i))
                row.addWidget(b)
        elif meta.get("intent"):
            for icon, good in (("👍", True), ("👎", False)):
                b = QPushButton(icon)
                b.setCursor(Qt.PointingHandCursor)
                b.setFixedSize(34, 28)
                b.setStyleSheet("QPushButton { background: rgba(255,255,255,0.04); border: 1px solid rgba(255,255,255,0.08); border-radius: 14px; }"
                                "QPushButton:hover { background: rgba(255,255,255,0.09); }")
                b.setEnabled(interactive and meta.get("feedback") is None)
                b.clicked.connect(lambda _=False, g=good, m=meta: self._feedback(m, g))
                row.addWidget(b)
        else:
            return
        row.addStretch()
        self.msgs.insertLayout(self.msgs.count() - 1, row)
        self._fb_rows = getattr(self, "_fb_rows", [])
        self._fb_rows.append(row)

    def _feedback(self, meta: dict, good: bool):
        meta["feedback"] = good
        row = self._fb_rows[-1]
        for i in range(row.count()):
            w = row.itemAt(i).widget()
            if w is not None:
                w.setEnabled(False)
        if good:
            ok = self.learn(meta["intent"], meta["question"])
            self.status.setText("Teşekkürler, bu soruyu öğrendim." if ok else
                                "Teşekkürler. Bu kalıp mevcut kalıpları bozacağı için kaydetmedim.")
        else:
            self.store.log_unknown(meta["question"])      # Eğitim sekmesinde doğru niyeti seçebilirsin
            self.status.setText("Anlaşıldı; soruyu Eğitim sekmesine ekledim, orada doğru konuyu seçebilirsin.")

    def _choose(self, meta: dict, intent: str):
        """Öneri düğmesi: seçilen niyeti öğren ve soruyu o niyetle cevapla."""
        if self.worker and self.worker.isRunning():
            return
        ok = self.learn(intent, meta["question"])
        self.status.setText(f"Öğrendim: bu tür sorular “{INTENT_LABELS.get(intent, intent)}” konusu." if ok else
                            "Cevaplıyorum ama bu kalıp mevcut kalıpları bozacağı için kaydetmedim.")
        self.send(meta["question"], forced=intent, echo=False)

    def _on_failed(self, msg: str):
        if self.current is not None:
            self.current.setText(f"{self._buf}\n\n⚠ {msg}".strip())
        self._buf += f"\n\n⚠ {msg}"

    def _on_done(self):
        if self._buf.strip():
            self.state.display.append(("assistant", self._buf, getattr(self, "_chart", None), getattr(self, "_meta", None)))
        self._chart, self._meta = None, None
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
        if getattr(self, "note", ""):
            warn = QLabel(self.note)
            warn.setWordWrap(True)
            warn.setStyleSheet(f"color: {AMBER}; font-size: 12px; background: transparent;")
            p.lay.addWidget(warn)
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
        if ex:
            clear = QPushButton("Öğrendiklerimi sıfırla")
            clear.setObjectName("export")
            clear.setCursor(Qt.PointingHandCursor)
            clear.clicked.connect(self.reset)
            q.lay.addWidget(clear, 0, Qt.AlignLeft)
        self.body.addWidget(q)

    def teach(self, uid: int, text: str, intent: str):
        existing = [(i, t) for _, i, t in self.store.list_examples()]
        if not accepts(existing, intent, text):
            self.note = "Bu örnek mevcut kalıpları bozacağı için eklenmedi (başka bir konuya düşüyor). Soruyu biraz daha belirgin yazıp tekrar dene."
            self.refresh()
            return
        self.note = ""
        self.store.add_example(intent, text)
        self.store.delete_unknown(uid)
        self.on_taught()
        self.refresh()

    def reset(self):
        for eid, _, _ in self.store.list_examples():
            self.store.delete_example(eid)
        self.on_taught()
        self.refresh()
