"""Tahmini enerji sınıfı (A-G) ve benzer binalara göre yüzdelik sıralama.

Dikkat: Bunlar resmi Enerji Kimlik Belgesi değil, kıyas değerine (Ayarlar) göre gösterge niteliğinde tahminlerdir."""
from __future__ import annotations

import math

CLASSES = ["A", "B", "C", "D", "E", "F", "G"]
# EUI / kıyas değeri oranı için üst sınırlar; üstü G
LIMITS = [0.50, 0.75, 1.00, 1.30, 1.65, 2.00]
CLASS_COLORS = {"A": "#0DDD96", "B": "#67D46E", "C": "#B9D940", "D": "#F5C033", "E": "#F59E0B", "F": "#F2703C", "G": "#F43F5E"}
LOG_SIGMA = 0.35   # benzer binaların EUI dağılımının (log-normal) yayılımı; medyan = kıyas değeri


def energy_class(eui: float, benchmark: float) -> str:
    r = eui / benchmark if benchmark > 0 else float("inf")
    for letter, limit in zip(CLASSES, LIMITS):
        if r <= limit:
            return letter
    return "G"


def percentile_worse_than(eui: float, benchmark: float) -> float:
    """Benzer binaların yüzde kaçından DAHA FAZLA enerji tüketiyor (0-100). Log-normal model, medyan = kıyas değeri."""
    if eui <= 0 or benchmark <= 0:
        return 0.0
    z = math.log(eui / benchmark) / LOG_SIGMA
    return 50 * (1 + math.erf(z / math.sqrt(2)))


def pdf_curve(n: int = 80) -> list[tuple[float, float]]:
    """Dağılım eğrisi (z, yoğunluk) çizimi için; z ∈ [-3, 3]."""
    return [(-3 + 6 * i / (n - 1), math.exp(-0.5 * (-3 + 6 * i / (n - 1)) ** 2)) for i in range(n)]


def z_of(eui: float, benchmark: float) -> float:
    return max(-3.0, min(3.0, math.log(max(eui, 1e-9) / benchmark) / LOG_SIGMA))
