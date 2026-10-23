"""Safe / Caution / Don't go rules.

Starter thresholds for the hackathon demo. NOT official IMD guidance.
"""

WAVE_CAUTION_M = 1.5
WAVE_DANGER_M = 2.5
GUST_CAUTION_KMH = 30
GUST_DANGER_KMH = 45


def assess(max_wave_m: float, max_gust_kmh: float) -> tuple[str, str]:
    """Return (level, reason) for the worst conditions in the trip window."""
    if max_wave_m > WAVE_DANGER_M:
        return "Don't go", f"waves up to {max_wave_m:.1f} metres"
    if max_gust_kmh > GUST_DANGER_KMH:
        return "Don't go", f"wind gusts up to {max_gust_kmh:.0f} km/h"
    if max_wave_m >= WAVE_CAUTION_M:
        return "Caution", f"waves up to {max_wave_m:.1f} metres"
    if max_gust_kmh >= GUST_CAUTION_KMH:
        return "Caution", f"wind gusts up to {max_gust_kmh:.0f} km/h"
    return "Safe", f"waves under {WAVE_CAUTION_M} metres and gusts under {GUST_CAUTION_KMH} km/h"
