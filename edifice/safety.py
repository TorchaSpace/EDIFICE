"""Veri güvenliği: günlük yedek, bütünlük kontrolü ve kurtarma, JSON dışa aktarma, hata günlüğü (UI'dan bağımsız)."""
from __future__ import annotations

import json
import logging
import shutil
import sqlite3
import sys
from datetime import date, datetime
from pathlib import Path

LOG = logging.getLogger("edifice")


def app_dir() -> Path:
    d = Path.home() / ".edifice"
    d.mkdir(parents=True, exist_ok=True)
    return d


def backup_dir() -> Path:
    d = app_dir() / "backups"
    d.mkdir(parents=True, exist_ok=True)
    return d


def check_integrity(path: str) -> tuple[bool, str]:
    """SQLite bütünlük kontrolü. Dosya yoksa (yeni kurulum) sorun sayılmaz."""
    p = Path(path)
    if path == ":memory:" or not p.exists():
        return True, "yeni"
    try:
        con = sqlite3.connect(path)
        try:
            row = con.execute("PRAGMA integrity_check").fetchone()
        finally:
            con.close()
        return (row is not None and row[0] == "ok"), (row[0] if row else "boş")
    except sqlite3.DatabaseError as e:
        return False, str(e)


def backup_db(path: str, keep: int = 7, folder: Path | None = None) -> Path | None:
    """Günde en fazla bir kez, SQLite'ın tutarlı yedekleme API'siyle yedek alır; en son `keep` yedeği tutar."""
    if path == ":memory:" or not Path(path).exists():
        return None
    folder = folder or backup_dir()
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / f"edifice-{date.today():%Y%m%d}.db"
    if not target.exists():
        src = sqlite3.connect(path)
        try:
            dst = sqlite3.connect(str(target))
            try:
                src.backup(dst)
            finally:
                dst.close()
        finally:
            src.close()
    for old in sorted(folder.glob("edifice-*.db"))[:-keep]:
        old.unlink(missing_ok=True)
    return target


def recover_if_corrupt(path: str, folder: Path | None = None) -> str | None:
    """Veritabanı bozuksa dosyayı kenara alır ve en yeni sağlam yedeği yerine koyar. Ne yapıldığını döndürür (sorun yoksa None)."""
    ok, msg = check_integrity(path)
    if ok:
        return None
    p = Path(path)
    aside = p.with_name(f"{p.stem}.bozuk-{datetime.now():%Y%m%d-%H%M%S}{p.suffix}")
    shutil.move(str(p), str(aside))
    for b in sorted((folder or backup_dir()).glob("edifice-*.db"), reverse=True):
        if check_integrity(str(b))[0]:
            shutil.copy2(b, p)
            return f"Veritabanı bozuktu ({msg}); {b.name} yedeği geri yüklendi. Bozuk dosya: {aside.name}"
    return f"Veritabanı bozuktu ({msg}) ve sağlam yedek bulunamadı; yeni veritabanı açıldı. Bozuk dosya: {aside.name}"


def export_json(store, path: str) -> str:
    """Tüm binaları, tüketimleri, ekipmanı, proje durumlarını ve senaryoları insan okuyabilir JSON olarak yazar."""
    out = {"surum": 1, "tarih": datetime.now().isoformat(timespec="seconds"), "binalar": []}
    for bid, _ in store.list_buildings():
        p = store.load_project(bid)
        b = p.building
        out["binalar"].append({
            "id": bid, "ad": b.name, "adres": b.address, "kullanim": b.use_type, "alan_m2": b.floor_area_m2, "yapim_yili": b.year_built,
            "kat": b.floors, "kisi": b.occupants, "enlem": b.lat, "boylam": b.lon,
            "tuketim": [{"tur": r.utility.value, "yil": r.year, "ay": r.month, "miktar": r.consumption, "tutar_TL": r.cost} for r in p.readings],
            "ekipman": [{"kategori": e.category, "ad": e.name, "kurulum_yili": e.year_installed, "durum": e.condition, "not": e.notes}
                        for e in p.equipment],
            "projeler": {c: {"durum": s, "yil": y} for c, (s, y) in store.load_projects(bid).items()},
            "senaryo": store.load_scenario(bid)})
    Path(path).write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def install_crash_log(show_dialog=None) -> Path:
    """Yakalanmamış hataları ~/.edifice/edifice.log dosyasına yazar; uygulama sessizce kapanmak yerine kullanıcıya bildirir."""
    log_file = app_dir() / "edifice.log"
    handler = logging.FileHandler(log_file, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    LOG.addHandler(handler)
    LOG.setLevel(logging.INFO)
    if log_file.exists() and log_file.stat().st_size > 1_000_000:      # günlük şişmesin
        log_file.write_text(log_file.read_text(encoding="utf-8")[-200_000:], encoding="utf-8")
    shown = {"n": 0}

    def hook(tp, val, tb):
        LOG.error("Yakalanmamış hata", exc_info=(tp, val, tb))
        sys.__excepthook__(tp, val, tb)
        if show_dialog and shown["n"] < 3:
            shown["n"] += 1
            try:
                show_dialog(f"Beklenmeyen bir hata oluştu: {val}\n\nAyrıntı günlük dosyasına yazıldı:\n{log_file}")
            except Exception:
                pass
    sys.excepthook = hook
    return log_file
