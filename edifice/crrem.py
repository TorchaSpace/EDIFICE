"""CRREM yol dosyasını (kullanıcının crrem.org'dan kendi indirdiği resmî Excel) okur. UI'dan bağımsız.

ÖNEMLİ — LİSANS: CRREM verisi (CRREM Foundation) dahili karar araçlarında, kaynak gösterilerek serbest kullanılabilir; ancak ticari yazılıma gömmek
ve yeniden dağıtmak ayrı bir License Partner anlaşması ister (https://crrem.org/library/use-of-data/). Bu yüzden uygulama CRREM verisini İÇERMEZ;
kullanıcı dosyayı kendisi indirir (kayıt formu ve kullanım koşulları onunla) ve buraya içe aktarır. Veri yalnızca kullanıcının yerel veritabanında durur.
Türkiye (TR) CRREM kapsamında YOKTUR (V2.01'de 65 ülke/şehir kodu var, TR yok); vekil ülke seçmek kullanıcının kararıdır."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from openpyxl import load_workbook


class CrremError(Exception):
    pass


@dataclass
class CrremData:
    version: str = ""
    source_file: str = ""
    pathways: dict[str, dict[tuple[str, str], dict[int, float]]] = field(default_factory=lambda: {"ghg": {}, "kwh": {}})
    grid: dict[str, dict[int, float]] = field(default_factory=dict)

    @property
    def countries(self) -> list[str]:
        return sorted({c for d in self.pathways.values() for c, _ in d})

    @property
    def types(self) -> list[str]:
        return sorted({t for d in self.pathways.values() for _, t in d})


def _header_row(rows):
    for i, r in enumerate(rows[:30]):
        if r and isinstance(r[0], str) and r[0].strip().lower() == "year":
            return i
    return None


_CODE = re.compile(r"^[A-Za-z]{2,3}(?:-[A-Za-z0-9]+)?\.[A-Za-z0-9_-]+(?:\..+)?$")        # ÜLKE.TÜR[.ölçüt]


def _metric_of(sheet_name: str) -> str | None:
    n = sheet_name.lower()
    if "ghg" in n or "co2" in n or "carbon" in n:
        return "ghg"
    if "kwh" in n or "energy" in n or "eui" in n:
        return "kwh"
    return None


def parse(path: str) -> CrremData:
    try:
        wb = load_workbook(path, read_only=True, data_only=True)
    except Exception as e:
        raise CrremError(f"Dosya açılamadı: {e}") from e
    data = CrremData(source_file=Path(path).name)
    for ws in wb.worksheets:
        for r in ws.iter_rows(min_row=1, max_row=8, values_only=True):
            for c in r:
                if isinstance(c, str) and re.search(r"(?i)version\s*:", c):
                    data.version = c.strip()
        name = ws.title.lower()
        rows = [list(r) for r in ws.iter_rows(values_only=True)]
        if "grid" in name:
            _parse_grid(rows, data)
            continue
        metric = _metric_of(name)
        if metric is None:
            continue
        hi = _header_row(rows)
        if hi is None:
            continue
        header = rows[hi]
        for r in rows[hi + 1:]:
            if not r or not isinstance(r[0], (int, float)) or not 1990 < r[0] < 2100:
                continue
            year = int(r[0])
            for j, code in enumerate(header):
                if j == 0 or not isinstance(code, str) or not _CODE.match(code.strip()):
                    continue
                code = code.strip()
                v = r[j] if j < len(r) else None
                if isinstance(v, (int, float)):
                    country, ptype = code.split(".")[0], code.split(".")[1]
                    data.pathways[metric].setdefault((country, ptype), {})[year] = float(v)
    if not data.pathways["ghg"] and not data.pathways["kwh"]:
        raise CrremError("Bu dosyada tanınan CRREM yol tablosu bulunamadı (beklenen: «GHGe» ve «kWh» sayfaları, ilk sütun «Year», "
                         "sütun adları ÜLKE.TÜR.ölçüt). Dosya crrem.org'un yeni bir biçimindeyse içe aktarma güncellenmelidir.")
    return data


def _parse_grid(rows, data: CrremData):
    header = None
    for r in rows:
        if not r or r[0] is None:
            continue
        if isinstance(r[0], str) and r[0].lower().startswith("grid"):
            header = [str(c).strip() if c is not None else None for c in r]
            continue
        if header and isinstance(r[0], (int, float)) and 1990 < r[0] < 2100:
            for j, code in enumerate(header):
                if j and code and j < len(r) and isinstance(r[j], (int, float)):
                    data.grid.setdefault(code, {})[int(r[0])] = float(r[j])


# ---- kolaylık: özet, otomatik bulma, vekil ülke önerisi ----------------------------------------

PROXY_PREFERENCE = ("GR", "BG", "RO", "IT", "ES", "CY", "PT", "HU", "HR")      # Türkiye'ye coğrafi/iklim olarak yakın olabilecekler; yalnız ipucu


def summary(data: CrremData) -> dict:
    """İçe aktarılan dosyanın kısa özeti: sürüm, yıl aralığı, ülke/tür sayısı, Türkiye var mı."""
    years = sorted({y for d in data.pathways.values() for ys in d.values() for y in ys})
    return {"version": data.version, "years": (years[0], years[-1]) if years else None, "countries": len(data.countries),
            "types": data.types, "has_turkey": any(c in data.countries for c in ("TR", "TUR")), "grid_countries": len(data.grid)}


def suggest_proxies(countries: list[str]) -> list[str]:
    """Dosyada bulunan, Türkiye'ye yakın olabilecek ülke kodları (yalnız öneri: vekil seçimi kullanıcının kararıdır, Türkiye yolu DEĞİLDİR)."""
    have = set(countries)
    return [c for c in PROXY_PREFERENCE if c in have]


def find_candidates(dirs: list[str] | None = None, limit: int = 5) -> list[str]:
    """İndirilenler (ve verilen klasörler) içinde CRREM'e benzeyen Excel dosyaları, yenisi önce. Dosyalar açılıp doğrulanmaz."""
    import os
    dirs = dirs or [str(Path.home() / "Downloads"), str(Path.home() / "Desktop"), str(Path.home() / "Masaüstü"), str(Path.home() / "İndirilenler")]
    found = []
    for d in dirs:
        try:
            for f in Path(d).iterdir():
                if f.suffix.lower() in (".xlsx", ".xlsm") and "crrem" in f.name.lower() and not f.name.startswith("~$"):
                    found.append((os.path.getmtime(f), str(f)))
        except OSError:
            continue
    return [p for _, p in sorted(found, reverse=True)[:limit]]
