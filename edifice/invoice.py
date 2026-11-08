"""Fatura PDF/foto okuma: faturadan tüketim ve tutarı çıkarır. UI'dan bağımsız.

Akış: dosya -> metin (PDF metin katmanı ya da, kuruluysa, OCR) -> alan çıkarımı (tür, dönem, tüketim, tutar) -> `UtilityReading`.
Sonuç her zaman kullanıcı onayına sunulur; okuma hatası sessizce veriye girmez. Her alan için güven ve uyarı döner.

Bağımlılıklar isteğe bağlıdır: PDF için `pypdf`, görüntü için `pytesseract` + Tesseract programı (Türkçe dil paketi önerilir).
Taranmış (metin katmanı olmayan) PDF'ler de OCR gerektirir (`pypdfium2` ile sayfa görüntüye çevrilir)."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from .bulk_import import MONTHS, norm, parse_number
from .models import UtilityReading, UtilityType

IMAGE_EXT = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".webp"}
# Doğalgaz faturası yalnız Sm³ veriyorsa kWh'ye çevirme katsayısı: yaklaşık üst ısıl değer, VARSAYIM (fatura kWh veriyorsa kullanılmaz).
GAS_KWH_PER_SM3 = 9.4
MIN_TEXT_CHARS = 40          # bundan az metin = metin katmanı yok


@dataclass
class InvoiceParse:
    utility: UtilityType | None = None
    year: int | None = None
    month: int | None = None
    consumption: float | None = None     # elektrik/doğalgaz kWh, su m³
    cost: float | None = None            # ₺
    confidence: float = 0.0              # 0-1: bulunan alanların oranı
    warnings: list[str] = field(default_factory=list)
    source: str = ""

    @property
    def complete(self) -> bool:
        return None not in (self.utility, self.year, self.month, self.consumption)

    def reading(self, tariffs: dict | None = None) -> UtilityReading | None:
        if not self.complete:
            return None
        cost = self.cost if self.cost is not None else self.consumption * (tariffs or {}).get(self.utility, 0.0)
        return UtilityReading(self.utility, self.year, self.month, float(self.consumption), float(cost))


# ---- Metin çıkarma ----------------------------------------------------------

class OcrUnavailable(RuntimeError):
    pass


def ocr_available() -> bool:
    try:
        import pytesseract
        pytesseract.get_tesseract_version()
        return True
    except Exception:
        return False


def _ocr_image(img) -> str:
    try:
        import pytesseract
        pytesseract.get_tesseract_version()
    except Exception as e:
        raise OcrUnavailable("Görüntü okumak için Tesseract OCR kurulu olmalı (pip install pytesseract ve Tesseract programı + Türkçe dil paketi).") from e
    try:
        return pytesseract.image_to_string(img, lang="tur+eng")
    except Exception:
        return pytesseract.image_to_string(img)       # Türkçe paket yoksa varsayılan dil


def extract_text(path: str) -> tuple[str, str]:
    """-> (metin, yöntem: 'pdf-metin' | 'ocr'). Okunamazsa ValueError / OcrUnavailable."""
    p = Path(path)
    ext = p.suffix.lower()
    if ext == ".pdf":
        text = ""
        try:
            from pypdf import PdfReader
            text = "\n".join((pg.extract_text() or "") for pg in PdfReader(str(p)).pages)
        except ImportError as e:
            raise ValueError("PDF okumak için pypdf kurulu olmalı (pip install pypdf).") from e
        except Exception as e:
            raise ValueError(f"PDF açılamadı: {e}") from e
        if len(text.strip()) >= MIN_TEXT_CHARS:
            return text, "pdf-metin"
        try:                                           # taranmış PDF: sayfaları görüntüye çevirip OCR
            import pypdfium2
        except ImportError as e:
            raise OcrUnavailable("PDF'de metin katmanı yok (taranmış). OCR için pypdfium2 ve Tesseract gerekir.") from e
        pdf = pypdfium2.PdfDocument(str(p))
        parts = [_ocr_image(pdf[i].render(scale=2.5).to_pil()) for i in range(min(len(pdf), 4))]
        return "\n".join(parts), "ocr"
    if ext in IMAGE_EXT:
        from PIL import Image
        return _ocr_image(Image.open(p)), "ocr"
    raise ValueError(f"Desteklenmeyen dosya türü: {ext or '(uzantısız)'}. PDF ya da görüntü (png, jpg, tif) seçin.")


# ---- Alan çıkarımı ------------------------------------------------------------

_NUM = r"(\d{1,3}(?:[.,]\d{3})+(?:[.,]\d+)?|\d+(?:[.,]\d+)?)"
_DATE = r"(\d{1,2})[./-](\d{1,2})[./-](20\d\d)"


def detect_utility(text: str) -> UtilityType | None:
    """Anahtar kelime sayımı. «kWh» hem elektrikte hem doğalgazda geçtiği için yalnız elektrik kelimesi yoksa elektrik sayılır."""
    t = norm(text)
    count = lambda pat: len(re.findall(pat, t))
    gas = count(r"dogalgaz|dogal gaz|igdas|botas|sm3|sm³|egegaz|izmirgaz|bursagaz|aksa gaz|gaz dagitim")
    elec = count(r"elektrik|edas|tedas|enerjisa|aktif enerji|reaktif|dagitim bedeli|gdz")
    water = count(r"\bsu fatura|iski|aski|izsu|su idare|su tuketim|atik su|kanalizasyon|su bedeli|\bsu sayac")
    if not elec and not gas:
        elec = count(r"kwh") if not water else 0
    best = max((elec, UtilityType.ELECTRICITY), (gas, UtilityType.GAS), (water, UtilityType.WATER), key=lambda x: x[0])
    return best[1] if best[0] > 0 else None


def detect_period(text: str) -> tuple[int, int] | None:
    """Fatura dönemi: 'Dönem 2025/03', '01.03.2025 - 31.03.2025' (bitiş tarihinin ayı), 'Mart 2025'."""
    t = norm(text)
    m = re.search(r"(?:fatura )?donem[^\n\d]{0,20}(20\d\d)\s*[/.-]\s*(\d{1,2})", t)
    if m and 1 <= int(m.group(2)) <= 12:
        return int(m.group(1)), int(m.group(2))
    m = re.search(r"(?:fatura )?donem[^\n\d]{0,20}(\d{1,2})\s*[/.-]\s*(20\d\d)", t)
    if m and 1 <= int(m.group(1)) <= 12:
        return int(m.group(2)), int(m.group(1))
    rng = re.search(_DATE + r"\s*(?:-|–|ile|/|ila)\s*" + _DATE, t)
    if rng:
        d1, m1, y1, d2, m2, y2 = (int(g) for g in rng.groups())
        if 1 <= m2 <= 12:
            # 28-31 günlük dönemin çoğu bitiş ayına düşer; dönem 15'inde başlıyorsa bitiş ayı yine doğru kabul edilir
            return y2, m2
    names = "|".join(sorted((k for k in MONTHS if len(k) > 3), key=len, reverse=True))
    m = re.search(rf"\b({names})\w*\s+(20\d\d)", t)
    if m:
        return int(m.group(2)), MONTHS[m.group(1)]
    m = re.search(r"(?:fatura tarihi|duzenlenme tarihi|son odeme tarihi)[^\d]{0,15}" + _DATE, t)
    if m and 1 <= int(m.group(2)) <= 12:                 # son çare: fatura tarihi (genelde dönemden bir sonraki ay olabilir)
        return int(m.group(3)), int(m.group(2))
    return None


def _find_number(t: str, labels: str, unit: str | None = None, window: int = 60) -> float | None:
    """Etiketten sonraki ilk sayı (birim verilmişse birimle birlikte); biçim 1.234,56 ya da 1,234.56."""
    pat = rf"(?:{labels})[^\d\n]{{0,{window}}}?{_NUM}" + (rf"\s*{unit}" if unit else "")
    vals = [parse_number(m.group(1)) for m in re.finditer(pat, t)]
    vals = [v for v in vals if v is not None]
    return max(vals) if vals else None


def parse_invoice_text(text: str, source: str = "") -> InvoiceParse:
    r = InvoiceParse(source=source)
    t = norm(text)
    r.utility = detect_utility(text)
    per = detect_period(text)
    if per:
        r.year, r.month = per
    if r.utility is None:
        r.warnings.append("Fatura türü (elektrik / doğalgaz / su) anlaşılamadı.")
    if per is None:
        r.warnings.append("Fatura dönemi bulunamadı.")

    if r.utility == UtilityType.ELECTRICITY:
        r.consumption = (_find_number(t, r"toplam tuketim|toplam enerji|toplam aktif|tuketim miktari|aktif enerji|tuketim", "kwh")
                         or _find_number(t, r"", "kwh", window=0))
    elif r.utility == UtilityType.GAS:
        kwh = _find_number(t, r"toplam tuketim|tuketim|enerji", "kwh")
        if kwh:
            r.consumption = kwh
        else:
            sm3 = _find_number(t, r"toplam tuketim|tuketim|hacim|miktar", r"(?:sm3|sm³|m3|m³)")
            if sm3:
                r.consumption = sm3 * GAS_KWH_PER_SM3
                r.warnings.append(f"Faturada kWh bulunamadı; {sm3:g} Sm³ × {GAS_KWH_PER_SM3} kWh/Sm³ ile çevrildi (varsayım, gerçek ısıl değer faturada yazar).")
    elif r.utility == UtilityType.WATER:
        r.consumption = _find_number(t, r"toplam tuketim|tuketim|su tuketim|miktar", r"(?:m3|m³|ton)")
    if r.utility and r.consumption is None:
        r.warnings.append("Tüketim miktarı bulunamadı.")

    r.cost = _find_number(t, r"odenecek tutar|genel toplam|fatura tutari|toplam tutar|odenecek", r"(?:tl|₺|try)?", window=40)
    if r.cost is None:
        r.cost = _find_number(t, r"odenecek tutar|genel toplam|fatura tutari|toplam tutar", None, window=40)
    if r.cost is None:
        r.warnings.append("Ödenecek tutar bulunamadı; varsayılan tarifeyle tahmin edilecek.")
    if r.consumption is not None and r.consumption <= 0:
        r.warnings.append("Tüketim sıfır ya da negatif okundu.")
        r.consumption = None
    found = sum(x is not None for x in (r.utility, per, r.consumption, r.cost))
    r.confidence = found / 4
    return r


def read_invoice(path: str) -> InvoiceParse:
    """Dosyadan faturayı okur. Hata durumunda `warnings` içinde nedeni olan boş sonuç döner (istisna atmaz)."""
    try:
        text, how = extract_text(path)
    except (ValueError, OcrUnavailable) as e:
        return InvoiceParse(source=Path(path).name, warnings=[str(e)])
    res = parse_invoice_text(text, Path(path).name)
    if how == "ocr":
        res.warnings.append("Metin OCR ile okundu; rakamları faturayla karşılaştırın.")
        res.confidence *= 0.8
    if not text.strip():
        res.warnings.append("Dosyadan metin çıkarılamadı.")
    return res


def read_invoices(paths: list[str], tariffs: dict | None = None) -> tuple[list[UtilityReading], list[InvoiceParse]]:
    """Birden çok fatura: okunabilenlerden kayıt listesi + her dosyanın ayrıntısı. Aynı (tür, yıl, ay) için sonuncusu kalır."""
    items = [read_invoice(p) for p in paths]
    keyed: dict[tuple, UtilityReading] = {}
    for it in items:
        rd = it.reading(tariffs)
        if rd is None:
            continue
        k = (rd.utility, rd.year, rd.month)
        if k in keyed:
            it.warnings.append(f"{rd.month}/{rd.year} {rd.utility.value} için başka fatura da var; bu değer kullanıldı.")
        keyed[k] = rd
    return sorted(keyed.values(), key=lambda r: (r.year, r.month, r.utility.value)), items
