"""Çatı GES verimi: PVGIS (AB Ortak Araştırma Merkezi, JRC) aylık üretim verisi (1 kWp başına kWh) ve önbellek anahtarı.
PVGIS ücretsizdir; kaynak gösterilmelidir. Sonuç, konum + eğim + yön + sistem kaybına göre MODELLENMİŞ üretimdir (ölçüm değil)."""
from __future__ import annotations

import json
from urllib.parse import urlencode

BASE_URL = "https://re.jrc.ec.europa.eu/api/v5_2/PVcalc"
DEFAULT_ANGLE, DEFAULT_ASPECT, DEFAULT_LOSS = 30.0, 0.0, 14.0     # eğim °, yön (0 = güney), sistem kaybı % (PVGIS varsayılanı)


def request_url(lat: float, lon: float, angle: float = DEFAULT_ANGLE, aspect: float = DEFAULT_ASPECT, loss: float = DEFAULT_LOSS) -> str:
    q = {"lat": f"{lat:.3f}", "lon": f"{lon:.3f}", "peakpower": 1, "loss": loss, "angle": angle, "aspect": aspect, "outputformat": "json"}
    return f"{BASE_URL}?{urlencode(q)}"


def parse_pvgis(data: bytes) -> list[float] | None:
    """12 aylık kWh/kWp. Biçim beklenmedikse None."""
    try:
        months = json.loads(data.decode("utf-8"))["outputs"]["monthly"]["fixed"]
        vals = [float(m["E_m"]) for m in sorted(months, key=lambda m: m["month"])]
    except (KeyError, ValueError, TypeError):
        return None
    return vals if len(vals) == 12 and all(v >= 0 for v in vals) else None
