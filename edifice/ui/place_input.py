"""Ülke / il / ilçe alanları: her biri yazdıkça öneri çıkarır, üstteki seçimlere göre süzer."""
from __future__ import annotations

from PySide6.QtCore import QObject, QStringListModel, Qt, Signal
from PySide6.QtWidgets import QCompleter, QLineEdit

from ..geocode import Geocoder


class PlaceInput(QObject):
    picked = Signal(float, float)     # seçilen yerin koordinatı

    def __init__(self, edit: QLineEdit, layers, kind: str, parent_fields=(), placeholder: str = ""):
        """kind: 'country' | 'state' | 'city'. parent_fields: önce seçilmesi beklenen üst alanlar [(kind, QLineEdit)]."""
        super().__init__(edit)
        self.edit, self.kind, self.parents = edit, kind, list(parent_fields)
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
        self._geo.search(text, near)

    def _matches(self, hit: dict) -> bool:
        for kind, field in self.parents:
            want = field.edit.text().strip().casefold()
            if not want:
                continue
            have = hit["country"] if kind == "country" else hit["state"]
            if have and want not in have.casefold() and have.casefold() not in want:
                return False
        return True

    def _results(self, hits: list):
        names, self._hits = [], {}
        for h in hits:
            if not self._matches(h):
                continue
            if self.kind == "country" and h["type"] != "country":
                continue
            if h["name"] not in self._hits:
                self._hits[h["name"]] = h
                names.append(h["name"])
        self._model.setStringList(names[:7])
        if names and self.edit.hasFocus():
            self._comp.complete()

    def _chosen(self, name: str):
        h = self._hits.get(name)
        if h:
            self.coord = (h["lat"], h["lon"])
            self.picked.emit(h["lat"], h["lon"])
