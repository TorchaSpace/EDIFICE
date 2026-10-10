import json
import sqlite3
from pathlib import Path

import pytest

from edifice import safety
from edifice.db import Store
from edifice.models import UtilityType
from edifice.quality import assess
from edifice.service import Project


def test_clean_mock_is_high_quality():
    q = assess(Project.mock())
    assert q.level == "Yüksek" and q.completeness == 1.0
    assert all(i.severity == "bilgi" for i in q.issues)      # yalnız "tarifeyle aynı" gibi bilgi notları


def test_missing_months_lower_score_and_are_listed():
    p = Project.mock()
    p.readings = [r for r in p.readings if not (r.utility == UtilityType.ELECTRICITY and r.year == p.year and r.month in (3, 4, 5, 6, 7))]
    q = assess(p)
    assert q.score < assess(Project.mock()).score
    assert any("ay boş" in i.message and "Elektrik" in i.message for i in q.issues)


def test_outlier_and_unit_error_detected():
    p = Project.mock()
    for r in p.readings:
        if r.utility == UtilityType.ELECTRICITY and r.year == p.year and r.month == 6:
            r.consumption *= 40           # MWh/kWh karışıklığı gibi
    q = assess(p)
    assert any("medyanın" in i.message for i in q.issues)
    assert any(i.severity == "kritik" and "birim hatası" in i.message for i in q.issues)


def test_bad_building_and_equipment_inputs_flagged():
    p = Project.mock()
    p.building.floor_area_m2 = 0
    p.equipment[0].year_installed = 2999
    q = assess(p)
    msgs = " ".join(i.message for i in q.issues)
    assert "Brüt alan" in msgs and "gelecekte" in msgs and q.level == "Düşük"


def test_no_equipment_is_warned():
    p = Project.mock()
    p.equipment = []
    assert any(i.area == "Ekipman" and i.severity == "uyarı" for i in assess(p).issues)


def test_single_year_is_informational():
    p = Project.mock()
    p.readings = [r for r in p.readings if r.year == p.year]
    assert any("Tek yıllık" in i.message for i in assess(p).issues)


def test_backup_is_daily_and_pruned(tmp_path):
    db = tmp_path / "e.db"
    st = Store(str(db))
    st.seed_demo()
    folder = tmp_path / "bk"
    b = safety.backup_db(str(db), keep=2, folder=folder)
    assert b and b.exists()
    assert safety.backup_db(str(db), folder=folder) == b          # aynı gün ikinci yedek yok
    for n in ("20200101", "20200102", "20200103"):
        (folder / f"edifice-{n}.db").write_bytes(b.read_bytes())
    safety.backup_db(str(db), keep=2, folder=folder)
    assert len(list(folder.glob("edifice-*.db"))) == 2


def test_corrupt_db_is_recovered_from_backup(tmp_path):
    db = tmp_path / "e.db"
    st = Store(str(db))
    st.seed_demo()
    st.conn.close()
    folder = tmp_path / "bk"
    safety.backup_db(str(db), folder=folder)
    db.write_bytes(b"this is not a database" * 100)
    note = safety.recover_if_corrupt(str(db), folder=folder)
    assert note and "geri yüklendi" in note
    assert Store(str(db)).count() == 1
    assert any(p.name.startswith("e.bozuk-") for p in tmp_path.iterdir())


def test_corrupt_without_backup_starts_fresh(tmp_path):
    db = tmp_path / "e.db"
    db.write_bytes(b"garbage" * 50)
    note = safety.recover_if_corrupt(str(db), folder=tmp_path / "none")
    assert note and "sağlam yedek bulunamadı" in note
    assert Store(str(db)).count() == 0


def test_json_export_roundtrips_key_fields(tmp_path):
    st = Store(":memory:")
    bid = st.seed_demo()
    st.save_project(bid, "LED", "Tamamlandı", 2027)
    out = safety.export_json(st, str(tmp_path / "x.json"))
    data = json.loads(Path(out).read_text(encoding="utf-8"))
    b = data["binalar"][0]
    assert b["ad"] == "Demo Ofis Binası" and len(b["tuketim"]) > 30 and b["projeler"]["LED"] == {"durum": "Tamamlandı", "yil": 2027}
