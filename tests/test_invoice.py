"""Fatura okuma: metinden alan çıkarımı, birim çevirme, hata durumları, PDF metin katmanı."""
from edifice.invoice import (GAS_KWH_PER_SM3, InvoiceParse, detect_period, detect_utility, extract_text, parse_invoice_text,
                             read_invoice, read_invoices)
from edifice.models import UtilityType

ELEC = """BAŞKENT ELEKTRİK DAĞITIM A.Ş.  Elektrik Faturası
Fatura Dönemi: 01.03.2025 - 31.03.2025
Aktif Enerji Bedeli 120.450,00 TL
Toplam Tüketim: 85.320,500 kWh
Dağıtım Bedeli 20.100,25 TL
Ödenecek Tutar: 212.345,67 TL"""
GAS_KWH = """İGDAŞ Doğalgaz Faturası  Dönem: 2025/01
Toplam Tüketim 12.500 Sm3  Enerji 118.750,0 kWh
Ödenecek Tutar 45.210,10 TL"""
GAS_SM3 = """BOTAŞ Doğalgaz  Fatura dönemi 01.02.2025-28.02.2025
Tüketim 1.000 Sm3
Genel Toplam 9.500,00 TL"""
WATER = """İSKİ Su Faturası  Mart 2025
Su Tüketim 412 m3
Ödenecek Tutar: 18.900,50 TL"""


def test_electricity():
    r = parse_invoice_text(ELEC)
    assert r.utility == UtilityType.ELECTRICITY and (r.year, r.month) == (2025, 3)
    assert r.consumption == 85320.5 and r.cost == 212345.67 and r.complete and r.confidence == 1.0


def test_gas_prefers_kwh_over_sm3():
    r = parse_invoice_text(GAS_KWH)
    assert r.utility == UtilityType.GAS and (r.year, r.month) == (2025, 1)
    assert r.consumption == 118750.0 and not r.warnings


def test_gas_sm3_converted_with_warning():
    r = parse_invoice_text(GAS_SM3)
    assert r.utility == UtilityType.GAS and (r.year, r.month) == (2025, 2)
    assert r.consumption == 1000 * GAS_KWH_PER_SM3 and r.cost == 9500.0
    assert any("varsayım" in w for w in r.warnings)


def test_water():
    r = parse_invoice_text(WATER)
    assert r.utility == UtilityType.WATER and (r.year, r.month) == (2025, 3) and r.consumption == 412 and r.cost == 18900.5


def test_missing_cost_uses_tariff_and_warns():
    r = parse_invoice_text("Elektrik Faturası Dönem: 2025/05 Toplam Tüketim 1.000 kWh")
    assert r.cost is None and any("tutar" in w.lower() for w in r.warnings)
    rd = r.reading({UtilityType.ELECTRICITY: 3.0})
    assert rd.cost == 3000.0 and rd.consumption == 1000.0


def test_garbage_gives_incomplete_with_reasons():
    r = parse_invoice_text("Merhaba dünya, bu bir fatura değil.")
    assert not r.complete and r.reading() is None and len(r.warnings) >= 2 and r.confidence == 0


def test_period_variants():
    assert detect_period("Dönem 03/2025") == (2025, 3)
    assert detect_period("Mart 2025 faturası") == (2025, 3)
    assert detect_period("12.12.2024 - 11.01.2025") == (2025, 1)
    assert detect_period("hiçbir tarih yok") is None
    assert detect_utility("sadece 100 kWh") == UtilityType.ELECTRICITY


def test_nonpositive_consumption_rejected():
    r = parse_invoice_text("Elektrik Dönem 2025/02 Toplam Tüketim 0 kWh Ödenecek Tutar 10 TL")
    assert r.consumption is None and not r.complete


def test_unsupported_and_missing_files(tmp_path):
    f = tmp_path / "a.txt"
    f.write_text("x")
    r = read_invoice(str(f))
    assert not r.complete and "Desteklenmeyen" in r.warnings[0]
    r = read_invoice(str(tmp_path / "yok.pdf"))
    assert not r.complete and r.warnings


def _make_pdf(path, lines):
    from reportlab.pdfgen import canvas  # noqa
    c = canvas.Canvas(str(path))
    y = 800
    for ln in lines:
        c.drawString(40, y, ln)
        y -= 18
    c.save()


def test_pdf_text_layer(tmp_path):
    import pytest
    pytest.importorskip("reportlab")
    pytest.importorskip("pypdf")
    p = tmp_path / "f.pdf"
    _make_pdf(p, ["Elektrik Faturasi (EDAS)", "Fatura Donemi: 01.04.2025 - 30.04.2025", "Toplam Tuketim: 70.000,0 kWh",
                  "Odenecek Tutar: 150.000,00 TL"])
    text, how = extract_text(str(p))
    assert how == "pdf-metin"
    r = read_invoice(str(p))
    assert r.complete and (r.year, r.month) == (2025, 4) and r.consumption == 70000.0 and r.cost == 150000.0


def test_read_invoices_dedup(tmp_path):
    import pytest
    pytest.importorskip("reportlab")
    pytest.importorskip("pypdf")
    a, b = tmp_path / "a.pdf", tmp_path / "b.pdf"
    _make_pdf(a, ["Elektrik EDAS", "Donem: 2025/06", "Toplam Tuketim 1.000 kWh", "Odenecek Tutar 3.000 TL"])
    _make_pdf(b, ["Elektrik EDAS", "Donem: 2025/06", "Toplam Tuketim 2.000 kWh", "Odenecek Tutar 6.000 TL"])
    readings, items = read_invoices([str(a), str(b)])
    assert len(readings) == 1 and readings[0].consumption == 2000.0 and any("başka fatura" in w for w in items[1].warnings)


def test_image_ocr(tmp_path):
    import pytest
    from edifice.invoice import ocr_available
    if not ocr_available():
        pytest.skip("Tesseract kurulu değil")
    from PIL import Image, ImageDraw, ImageFont
    img = Image.new("RGB", (1400, 420), "white")
    d = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 40)
    except OSError:
        pytest.skip("yazı tipi yok")
    for i, ln in enumerate(["Elektrik Faturasi EDAS", "Fatura Donemi: 01.05.2025 - 31.05.2025", "Toplam Tuketim: 64.200 kWh",
                            "Odenecek Tutar: 180.500,00 TL"]):
        d.text((30, 20 + i * 90), ln, fill="black", font=font)
    p = tmp_path / "f.png"
    img.save(p)
    r = read_invoice(str(p))
    assert r.utility == UtilityType.ELECTRICITY and (r.year, r.month) == (2025, 5) and r.consumption == 64200.0
    assert any("OCR" in w for w in r.warnings) and r.confidence <= 0.8
