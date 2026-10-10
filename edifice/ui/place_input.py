"""Ülke / il / ilçe alanları: her biri yazdıkça öneri çıkarır, üstteki seçimlere göre süzer."""
from __future__ import annotations

from PySide6.QtCore import QObject, QStringListModel, Qt, Signal
from PySide6.QtWidgets import QCompleter, QLineEdit

from ..geocode import Geocoder


class PlaceInput(QObject):
    picked = Signal(float, float)     # seçilen yerin koordinatı

    def __init__(self, edit: QLineEdit, layers, kind: str, parent_fields=(), placeholder: str = "", context=None):
        """kind: 'country' | 'state' | 'city'. parent_fields: önce seçilmesi beklenen üst alanlar [(kind, QLineEdit)]."""
        super().__init__(edit)
        self.edit, self.kind, self.parents = edit, kind, list(parent_fields)
        self.context = context         # açık adres: yazılana eklenen ilçe, il, ülke metni
        self.coord: tuple[float, float] | None = None
        edit.setPlaceholderText(placeholder)
        self._hits: dict[str, dict] = {}
        self._model = QStringListModel(self)
        self._comp = QCompleter(self._model, self)
        self._comp.setCompletionMode(QCompleter.UnfilteredPopupCompletion)
        self._comp.setCaseSensitivity(Qt.CaseInsensitive)
        edit.setCompleter(self._comp)
        self._geo = Geocoder(layers, self)
        edit.textEdited.connect(self._typed)
        self._geo.results.connect(self._results)
        self._comp.activated.connect(self._chosen)

    def _typed(self, text: str):
        self.coord = None
        near = next((p.coord for _, p in self.parents if p.coord), None)
        ctx = self.context() if self.context else ""
        self._geo.search(f"{text}, {ctx}" if ctx and text.strip() else text, near)

    def _matches(self, hit: dict) -> bool:
        for kind, field in self.parents:
            want = field.edit.text().strip().casefold()
            if not want:
                continue
            have = hit["country"] if kind == "country" else hit["state"]
            if have and want not in have.casefold() and have.casefold() not in want:
                return False
        return True

    def _label(self, h: dict) -> str:
        """Açık adres önerisi: yalnız ilçe altındaki kısım (mahalle, cadde, kapı no); ülke/il/ilçe tekrarlanmaz."""
        if self.kind != "street":
            return h["name"]
        if h["street"]:
            street = f"{h['street']} {h['housenumber']}".strip()
            return ", ".join(x for x in (h["district"], street) if x and x != h["name"]) + (
                f" ({h['name']})" if h["name"] and h["name"] != h["street"] and h["name"] != h["district"] else "")
        return ", ".join(x for x in (h["district"], h["name"]) if x)

    def _results(self, hits: list):
        names, self._hits = [], {}
        for h in hits:
            if not self._matches(h):
                continue
            if self.kind == "country" and h["type"] != "country":
                continue
            label = self._label(h)
            if label and label not in self._hits:
                self._hits[label] = h
                names.append(label)
        self._model.setStringList(names[:7])
        if names and self.edit.hasFocus():
            self._comp.complete()

    def _chosen(self, name: str):
        h = self._hits.get(name)
        if h:
            self.coord = (h["lat"], h["lon"])
            self.picked.emit(h["lat"], h["lon"])
