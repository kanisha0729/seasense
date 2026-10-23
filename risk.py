"""Safe / Caution / Don't go rules.

Starter thresholds for the hackathon demo. NOT official IMD guidance.
"""

WAVE_CAUTION_M = 1.5
WAVE_DANGER_M = 2.5
GUST_CAUTION_KMH = 30
GUST_DANGER_KMH = 45


def assess(max_wave_m: float, max_gust_kmh: float) -> tuple[str, str, float]:
    """Return (level, cause, value) for the worst conditions in the trip window.

    level: "safe" | "caution" | "danger"
    cause: "wave" | "gust" | "calm"
    value: the number that decided it (metres or km/h)
    """
    if max_wave_m > WAVE_DANGER_M:
        return "danger", "wave", max_wave_m
    if max_gust_kmh > GUST_DANGER_KMH:
        return "danger", "gust", max_gust_kmh
    if max_wave_m >= WAVE_CAUTION_M:
        return "caution", "wave", max_wave_m
    if max_gust_kmh >= GUST_CAUTION_KMH:
        return "caution", "gust", max_gust_kmh
    return "safe", "calm", 0.0
