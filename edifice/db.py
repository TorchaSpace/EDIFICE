"""SQLite kayıt katmanı: bina, tüketim ve ekipman. Ham veri burada, hesaplananlar motorda."""
from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path

from .models import Assumptions, Building, Equipment, Opportunity, UtilityReading, UtilityType
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
CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS opportunities (
  code TEXT PRIMARY KEY, name TEXT, category TEXT, affects TEXT, saving_pct REAL, capex_per_m2 REAL,
  description TEXT, position INTEGER);
CREATE TABLE IF NOT EXISTS projects (
  building_id INTEGER NOT NULL REFERENCES buildings(id) ON DELETE CASCADE,
  code TEXT NOT NULL, status TEXT NOT NULL, year INTEGER NOT NULL, PRIMARY KEY (building_id, code));
CREATE TABLE IF NOT EXISTS scenarios (
  building_id INTEGER PRIMARY KEY REFERENCES buildings(id) ON DELETE CASCADE, codes TEXT NOT NULL);
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


def assumptions_to_json(a: Assumptions) -> str:
    return json.dumps({
        "emission": {k.value: v for k, v in a.emission_factor_kg_per_kwh.items()},
        "benchmark_eui": a.benchmark_eui_kwh_m2, "benchmark_carbon": a.benchmark_carbon_kg_m2,
        "eui_by_use": a.benchmark_eui_by_use,
        "benchmark_water": a.benchmark_water_m3_m2, "target_eui": a.target_eui_kwh_m2,
        "equipment_life": a.equipment_life_years, "weights": a.health_weights,
        "tariffs": {k.value: v for k, v in a.default_tariffs.items()},
        "finance": {"discount": a.discount_rate, "escalation": a.energy_escalation, "horizon": a.horizon_years,
                    "degradation": a.savings_degradation}}, ensure_ascii=False)


def assumptions_from_json(text: str) -> Assumptions:
    d, a = json.loads(text), Assumptions()
    a.emission_factor_kg_per_kwh = {UtilityType(k): v for k, v in d["emission"].items()}
    a.benchmark_eui_kwh_m2, a.benchmark_carbon_kg_m2 = d["benchmark_eui"], d.get("benchmark_carbon")
    if d.get("eui_by_use"):
        a.benchmark_eui_by_use = d["eui_by_use"]
    a.benchmark_water_m3_m2, a.target_eui_kwh_m2 = d["benchmark_water"], d["target_eui"]
    a.equipment_life_years, a.health_weights = d["equipment_life"], d["weights"]
    a.default_tariffs = {UtilityType(k): v for k, v in d["tariffs"].items()}
    f = d.get("finance")
    if f:
        a.discount_rate, a.energy_escalation = f["discount"], f["escalation"]
        a.horizon_years, a.savings_degradation = int(f["horizon"]), f["degradation"]
    return a


class Store:
    def __init__(self, path: str | None = None):
        self.conn = sqlite3.connect(path or default_path())
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.conn.executescript(SCHEMA)
        cols = {r[1] for r in self.conn.execute("PRAGMA table_info(buildings)")}
        for c in ("lat", "lon"):
            if c not in cols:
                self.conn.execute(f"ALTER TABLE buildings ADD COLUMN {c} REAL")
        self.conn.execute("UPDATE buildings SET lat=41.0082, lon=28.9784 WHERE name='Demo Ofis Binası' AND lat IS NULL")
        self.conn.commit()
        self._migrate_evidence_defaults()

    EVIDENCE_VERSION = "3"

    def _migrate_evidence_defaults(self):
        """Kanıta dayalı varsayılanlara geçiş: eski (kaynaksız) kayıtlı varsayımlar ve katalog bir kez sıfırlanır."""
        row = self.conn.execute("SELECT value FROM settings WHERE key='evidence_version'").fetchone()
        if row and row[0] == self.EVIDENCE_VERSION:
            return
        with self.conn:
            self.conn.execute("DELETE FROM settings WHERE key='assumptions'")
            self.conn.execute("DELETE FROM opportunities")
            self.conn.execute("INSERT OR REPLACE INTO settings VALUES ('evidence_version', ?)", (self.EVIDENCE_VERSION,))

    def get_setting(self, key: str, default: str | None = None) -> str | None:
        row = self.conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        return row[0] if row else default

    def set_setting(self, key: str, value: str):
        with self.conn:
            if value:
                self.conn.execute("INSERT OR REPLACE INTO settings VALUES (?, ?)", (key, value))
            else:
                self.conn.execute("DELETE FROM settings WHERE key=?", (key,))

    # ---- varsayımlar ve öneri kataloğu
    def load_assumptions(self) -> Assumptions:
        row = self.conn.execute("SELECT value FROM settings WHERE key='assumptions'").fetchone()
        return assumptions_from_json(row[0]) if row else Assumptions()

    def save_assumptions(self, a: Assumptions):
        with self.conn:
            self.conn.execute("INSERT OR REPLACE INTO settings VALUES ('assumptions', ?)", (assumptions_to_json(a),))

    def reset_settings(self):
        with self.conn:
            self.conn.execute("DELETE FROM settings WHERE key='assumptions'")
            self.conn.execute("DELETE FROM opportunities")

    def load_opportunities(self) -> list[Opportunity]:
        rows = self.conn.execute(
            "SELECT code,name,category,affects,saving_pct,capex_per_m2,description FROM opportunities ORDER BY position").fetchall()
        defaults = {o.code: o for o in mock_data.opportunities()}
        if not rows:
            return list(defaults.values())
        out = []
        for c, n, cat, aff, sp, cx, desc in rows:
            d = defaults.get(c)
            changed = d is not None and abs(sp - d.saving_pct) > 1e-9
            out.append(Opportunity(c, n, cat, UtilityType(aff), sp, cx, desc,
                                   d.saving_low if d else None, d.saving_high if d else None,
                                   d.evidence if d else (), d.evidence_level if d else "varsayım",
                                   (d.basis if not changed else "Kullanıcı değeri (Ayarlar); literatür aralığı için varsayılana bakın.") if d else ""))
        return out

    def save_opportunities(self, opps: list[Opportunity]):
        with self.conn:
            self.conn.execute("DELETE FROM opportunities")
            self.conn.executemany("INSERT INTO opportunities VALUES (?,?,?,?,?,?,?,?)", [
                (o.code, o.name, o.category, o.affects.value, o.saving_pct, o.capex_per_m2, o.description, i)
                for i, o in enumerate(opps)])

    def update_building(self, bid: int, b: Building, readings: list[UtilityReading], equipment: list[Equipment]):
        with self.conn:
            self.conn.execute(
                "UPDATE buildings SET name=?,address=?,use_type=?,floor_area_m2=?,year_built=?,floors=?,occupants=?,lat=?,lon=? WHERE id=?",
                (b.name, b.address, b.use_type, b.floor_area_m2, b.year_built, b.floors, b.occupants, b.lat, b.lon, bid))
            self.conn.execute("DELETE FROM readings WHERE building_id=?", (bid,))
            self.conn.execute("DELETE FROM equipment WHERE building_id=?", (bid,))
            self.conn.executemany("INSERT INTO readings VALUES (?,?,?,?,?,?)",
                                  [(bid, r.utility.value, r.year, r.month, r.consumption, r.cost) for r in readings])
            self.conn.executemany(
                "INSERT INTO equipment (building_id,category,name,year_installed,condition,notes) VALUES (?,?,?,?,?,?)",
                [(bid, e.category, e.name, e.year_installed, e.condition, e.notes) for e in equipment])

    def save_project(self, bid: int, code: str, status: str, year: int):
        with self.conn:
            self.conn.execute("INSERT OR REPLACE INTO projects VALUES (?,?,?,?)", (bid, code, status, year))

    def load_projects(self, bid: int) -> dict[str, tuple[str, int]]:
        return {c: (s, y) for c, s, y in self.conn.execute(
            "SELECT code,status,year FROM projects WHERE building_id=?", (bid,))}

    def save_scenario(self, bid: int, codes: list[str]):
        with self.conn:
            self.conn.execute("INSERT OR REPLACE INTO scenarios VALUES (?, ?)", (bid, json.dumps(codes)))

    def load_scenario(self, bid: int) -> list[str]:
        row = self.conn.execute("SELECT codes FROM scenarios WHERE building_id=?", (bid,)).fetchone()
        return json.loads(row[0]) if row else []

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
                "INSERT INTO buildings (name,address,use_type,floor_area_m2,year_built,floors,occupants,lat,lon) "
                "VALUES (?,?,?,?,?,?,?,?,?)",
                (b.name, b.address, b.use_type, b.floor_area_m2, b.year_built, b.floors, b.occupants, b.lat, b.lon))
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
            "SELECT name,address,use_type,floor_area_m2,year_built,floors,occupants,lat,lon FROM buildings WHERE id=?",
            (bid,)).fetchone()
        if row is None:
            raise KeyError(bid)
        building = Building(*row)
        readings = [UtilityReading(UtilityType(u), y, m, c, k) for u, y, m, c, k in self.conn.execute(
            "SELECT utility,year,month,consumption,cost FROM readings WHERE building_id=? ORDER BY year,month", (bid,))]
        equipment = [Equipment(*r) for r in self.conn.execute(
            "SELECT category,name,year_installed,condition,notes FROM equipment WHERE building_id=?", (bid,))]
        return Project(building, readings, equipment, self.load_opportunities(), self.load_assumptions(), building_id=bid)

    def seed_demo(self) -> int:
        p = Project.mock()
        p.building.name = "Demo Ofis Binası"
        p.building.lat, p.building.lon = 41.0082, 28.9784
        return self.save_building(p.building, p.readings, p.equipment)
