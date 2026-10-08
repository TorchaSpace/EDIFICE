"""Basit HTML rapor çıktısı (tarayıcıdan PDF olarak yazdırılabilir)."""
from __future__ import annotations

from html import escape

from ..service import Project
from .widgets import fmt, fmt_years


def build_report(project: Project, codes: list[str]) -> str:
    b, k, h = project.building, project.kpis(), project.health()
    s = project.scenario(codes)
    rows = "".join(
        f"<tr><td>{escape(r.opportunity.name)}</td><td>{fmt(r.annual_saving)}</td>"
        f"<td>{fmt(r.capex)}</td><td>{fmt_years(r.payback_years)}</td></tr>"
        for r in project.opportunity_results())
    comps = "".join(f"<li>{escape(n)}: {p:.0f}/100</li>" for n, (p, _) in h.components.items())
    return f"""<!doctype html><html lang="tr"><meta charset="utf-8">
<title>EDIFI'CE Raporu</title>
<style>body{{font-family:sans-serif;max-width:800px;margin:2em auto}}
table{{border-collapse:collapse;width:100%}}td,th{{border:1px solid #ccc;padding:6px;text-align:right}}
td:first-child,th:first-child{{text-align:left}}</style>
<h1>EDIFI'CE Enerji ve Dönüşüm Raporu</h1>
<h2>{escape(b.name)}</h2>
<p>{escape(b.address)} · {escape(b.use_type)} · {fmt(b.floor_area_m2)} m² · Baz yıl {project.year}</p>
<h3>Mevcut durum</h3>
<ul><li>Toplam enerji: {fmt(k.total_energy_kwh / 1000)} MWh (EUI {fmt(k.eui_kwh_m2, 1)} kWh/m²)</li>
<li>Karbon: {fmt(k.carbon_kg / 1000, 1)} tCO₂</li><li>Su: {fmt(k.water_m3)} m³</li>
<li>Yıllık maliyet: {fmt(k.total_cost)} ₺</li></ul>
<h3>Building Health Score: {h.total:.0f}/100 (Not {h.grade})</h3><ul>{comps}</ul>
<h3>Dönüşüm önerileri</h3>
<table><tr><th>Öneri</th><th>Yıllık tasarruf (₺)</th><th>CAPEX (₺)</th><th>Geri ödeme</th></tr>{rows}</table>
<h3>Seçilen senaryo</h3>
<p>CAPEX {fmt(s.capex)} ₺ · Yıllık tasarruf {fmt(s.annual_saving)} ₺ ·
Geri ödeme {fmt_years(s.payback_years)} · Karbon azalımı %{fmt(s.carbon_reduction_pct * 100, 1)}</p>
</html>"""
