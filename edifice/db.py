"""SQLite kayıt katmanı: bina, tüketim ve ekipman. Ham veri burada, hesaplananlar motorda."""
from __future__ import annotations

import os
import sqlite3
from pathlib import Path

from .models import Assumptions, Building, Equipment, UtilityReading, UtilityType
from .service import Project
from . import mock_data

SCHEMA = """
CREATE TABLE IF NOT EXISTS buildings (
  id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, address TEXT, use_type TEXT,
  floor_area_m2 REAL, year_built INTEGER, floors INTEGER, occupants INTEGER,
  created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS readings (
  building_id INTEGER NOT NULL REFERENCES buildings(id) ON DELETE CASCADE,
  utility TEXT NOT NULL, year INTEGER NOT NULL, month INTEGER NOT NULL,
  consumption REAL NOT NULL, cost REAL NOT NULL,
  PRIMARY KEY (building_id, utility, year, month));
CREATE TABLE IF NOT EXISTS equipment (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  building_id INTEGER NOT NULL REFERENCES buildings(id) ON DELETE CASCADE,
  category TEXT, name TEXT, year_installed INTEGER, condition INTEGER, notes TEXT);
"""


def default_path() -> str:
    env = os.environ.get("EDIFICE_DB")
    if env:
        return env
    d = Path.home() / ".edifice"
    d.mkdir(exist_ok=True)
    return str(d / "edifice.db")


class Store:
    def __init__(self, path: str | None = None):
        self.conn = sqlite3.connect(path or default_path())
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.conn.executescript(SCHEMA)

    def count(self) -> int:
        return self.conn.execute("SELECT COUNT(*) FROM buildings").fetchone()[0]

    def list_buildings(self) -> list[tuple[int, str]]:
        return self.conn.execute("SELECT id, name FROM buildings ORDER BY id").fetchall()

    def latest_id(self) -> int | None:
        row = self.conn.execute("SELECT MAX(id) FROM buildings").fetchone()
        return row[0]

    def save_building(self, b: Building, readings: list[UtilityReading], equipment: list[Equipment]) -> int:
        with self.conn:
            cur = self.conn.execute(
                "INSERT INTO buildings (name,address,use_type,floor_area_m2,year_built,floors,occupants) "
                "VALUES (?,?,?,?,?,?,?)",
                (b.name, b.address, b.use_type, b.floor_area_m2, b.year_built, b.floors, b.occupants))
            bid = cur.lastrowid
            self.conn.executemany(
                "INSERT INTO readings VALUES (?,?,?,?,?,?)",
                [(bid, r.utility.value, r.year, r.month, r.consumption, r.cost) for r in readings])
            self.conn.executemany(
                "INSERT INTO equipment (building_id,category,name,year_installed,condition,notes) VALUES (?,?,?,?,?,?)",
                [(bid, e.category, e.name, e.year_installed, e.condition, e.notes) for e in equipment])
        return bid

    def delete_building(self, bid: int):
        with self.conn:
            self.conn.execute("DELETE FROM buildings WHERE id = ?", (bid,))

    def load_project(self, bid: int) -> Project:
        row = self.conn.execute(
            "SELECT name,address,use_type,floor_area_m2,year_built,floors,occupants FROM buildings WHERE id=?",
            (bid,)).fetchone()
        if row is None:
            raise KeyError(bid)
        building = Building(*row)
        readings = [UtilityReading(UtilityType(u), y, m, c, k) for u, y, m, c, k in self.conn.execute(
            "SELECT utility,year,month,consumption,cost FROM readings WHERE building_id=? ORDER BY year,month", (bid,))]
        equipment = [Equipment(*r) for r in self.conn.execute(
            "SELECT category,name,year_installed,condition,notes FROM equipment WHERE building_id=?", (bid,))]
        return Project(building, readings, equipment, mock_data.opportunities(), Assumptions(), building_id=bid)

    def seed_demo(self) -> int:
        p = Project.mock()
        p.building.name = "Demo Ofis Binası"
        return self.save_building(p.building, p.readings, p.equipment)
