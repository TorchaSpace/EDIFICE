"""Yük profili: CSV ayrıştırma (kWh/kW, ayırıcı, tarih biçimleri), boşta yük, pik, tarife karşılaştırması."""
import pytest
from datetime import datetime, timedelta

from edifice.engine.loadprofile import analyze, compare_tariffs, parse_interval_text


def synth_csv(days=14, step_min=60, night_kw=20.0, day_kw=100.0, weekend_kw=None, spike=None, header="Tarih;Tüketim (kWh)", fmt="%d.%m.%Y %H:%M"):
    lines = [header]
    t = datetime(2025, 3, 3)               # Pazartesi
    step_h = step_min / 60
    for i in range(int(days * 24 * 60 / step_min)):
        ts = t + timedelta(minutes=i * step_min)
        kw = day_kw if 8 <= ts.hour < 18 else night_kw
        if ts.weekday() >= 5 and weekend_kw is not None:
            kw = weekend_kw
        if spike and i == spike[0]:
            kw = spike[1]
        lines.append(f"{ts.strftime(fmt)};{str(round(kw * step_h, 3)).replace('.', ',')}")
    return "\n".join(lines)


def test_parse_hourly_kwh_to_kw():
    s = parse_interval_text(synth_csv())
    assert s.step_hours == 1.0 and len(s.points) == 14 * 24 and not s.warnings
    assert max(v for _, v in s.points) == 100.0


def test_parse_15min_and_iso_and_comma_delim():
    txt = synth_csv(days=3, step_min=15, header="timestamp,kWh", fmt="%Y-%m-%d %H:%M").replace(";", ",").replace(",", ";", 0)
    # virgül ayırıcı + ondalık virgül çakışır: ondalığı noktaya çevir
    lines = [txt.split("\n")[0]] + [ln.rsplit(",", 1)[0] + "," + ln.rsplit(",", 1)[1].replace(",", ".") if ln.count(",") > 1 else ln for ln in txt.split("\n")[1:]]
    s = parse_interval_text("\n".join(lines))
    assert s.step_hours == 0.25 and len(s.points) == 3 * 96
    assert max(v for _, v in s.points) == pytest.approx(100.0)


def test_kw_header_not_divided():
    s = parse_interval_text(synth_csv(header="Tarih;Güç (kW)", step_min=15))
    assert max(v for _, v in s.points) == pytest.approx(25.0)        # değerler kW kabul edildi: 100*0,25 = 25 kW olarak okunur


def test_bad_rows_and_garbage():
    s = parse_interval_text("Tarih;kWh\nabc;1\n01.03.2025 00:00;-5\n01.03.2025 01:00;2")
    assert not s.points and s.warnings
    assert not parse_interval_text("x").points


def test_analysis_profile_and_findings():
    s = parse_interval_text(synth_csv(days=14, night_kw=60, day_kw=100, weekend_kw=60))
    r = analyze(s)
    assert r.ok and r.peak_kw == 100 and r.base_kw == 60 and r.days == 14
    assert r.base_to_peak == pytest.approx(0.6) and r.weekday_profile[12] == 100 and r.weekend_profile[12] == 60
    assert any("Boşta" in f for f in r.findings)
    assert 0 < r.off_hours_share < 1 and sum(r.band_kwh.values()) == pytest.approx(r.kwh)


def test_spike_and_clean_case():
    s = parse_interval_text(synth_csv(days=14, night_kw=20, day_kw=100, weekend_kw=20, spike=(24 * 5 + 12, 300)))
    r = analyze(s)
    assert r.peak_kw == 300 and any("kısa süreli pik" in f for f in r.findings) and not any("Boşta" in f for f in r.findings)
    clean = analyze(parse_interval_text(synth_csv(days=14, night_kw=20, day_kw=100, weekend_kw=20)))
    assert not any("Boşta" in f or "kısa süreli" in f for f in clean.findings)


def test_too_short():
    assert not analyze(parse_interval_text(synth_csv(days=1))).ok


def test_tariff_comparison_consistency():
    r = analyze(parse_interval_text(synth_csv(days=14, night_kw=60, day_kw=100, weekend_kw=60)))
    c = compare_tariffs(r, 4.0)
    assert c.single_cost == pytest.approx(r.kwh * 4.0) and c.tou_cost == pytest.approx(sum(c.band_cost.values()))
    assert c.saving == pytest.approx(c.single_cost - c.tou_cost)
    flat = compare_tariffs(r, 4.0, {"T1": 1.0, "T2": 1.0, "T3": 1.0})
    assert flat.saving == pytest.approx(0) and flat.shift_gain == pytest.approx(0)


def test_store_roundtrip_and_page(tmp_path):
    import os
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication
    from edifice.db import Store
    from edifice.ui.load_page import LoadPage
    app = QApplication.instance() or QApplication([])  # noqa: F841
    st = Store(str(tmp_path / "l.db"))
    bid = st.seed_demo()
    s = parse_interval_text(synth_csv(days=7, night_kw=60, day_kw=100, weekend_kw=60))
    assert st.save_interval(bid, s) == len(s.points)
    back = st.load_interval(bid)
    assert back.step_hours == 1.0 and len(back.points) == len(s.points) and back.points[0] == s.points[0]
    st.save_interval(bid, s)                                  # tekrar yazmak çoğaltmaz
    assert len(st.load_interval(bid).points) == len(s.points)
    pg = LoadPage(st.load_project(bid), st)
    assert pg.rsp and pg._report.peak_kw == 100
    pg.rsp["T3"].setValue(0.5)                                # tarife yeniden hesaplanır, çökmez
    st.clear_interval(bid)
    pg.render()
    assert not st.load_interval(bid).points
