"""Cálculo de velocidade da bola a partir da trajetória rastreada.

A velocidade do saque é a velocidade de PICO logo após o impacto. Calculamos a
velocidade instantânea entre detecções consecutivas e reportamos:
  - peak_kmh: maior velocidade (robusta, mediana das N maiores janelas)
  - impact_frame: quadro de provável impacto (onde a velocidade dispara)
  - série temporal completa para gráfico
"""

from __future__ import annotations

from dataclasses import dataclass, field

from calibration import Calibration
from tracking import Detection


@dataclass
class SpeedSample:
    frame: int
    t_s: float
    speed_ms: float
    speed_kmh: float
    x_m: float
    y_m: float


@dataclass
class SpeedResult:
    peak_kmh: float
    peak_ms: float
    mean_kmh: float
    impact_frame: int | None
    samples: list[SpeedSample] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


def estimate(
    trajectory: list[Detection],
    calib: Calibration,
    top_n: int = 3,
) -> SpeedResult:
    notes: list[str] = []
    if len(trajectory) < 2:
        return SpeedResult(0.0, 0.0, 0.0, None, [], ["Trajetória insuficiente."])

    mpp = calib.meters_per_pixel
    fps = calib.fps

    samples: list[SpeedSample] = []
    for prev, cur in zip(trajectory, trajectory[1:]):
        dframes = cur.frame - prev.frame
        if dframes <= 0:
            continue
        dt = dframes / fps
        dx_m = (cur.x - prev.x) * mpp
        dy_m = (cur.y - prev.y) * mpp
        dist_m = (dx_m * dx_m + dy_m * dy_m) ** 0.5
        speed_ms = dist_m / dt
        samples.append(
            SpeedSample(
                frame=cur.frame,
                t_s=cur.frame / fps,
                speed_ms=speed_ms,
                speed_kmh=speed_ms * 3.6,
                x_m=cur.x * mpp,
                y_m=cur.y * mpp,
            )
        )

    if not samples:
        return SpeedResult(0.0, 0.0, 0.0, None, [], ["Sem amostras válidas."])

    # Rejeita saltos fisicamente impossíveis (> 300 km/h): tipicamente
    # reaquisição da bola após oclusão, não movimento real.
    MAX_PLAUSIBLE_MS = 300 / 3.6
    clean = [s for s in samples if s.speed_ms <= MAX_PLAUSIBLE_MS]
    if len(clean) < len(samples):
        notes.append(
            f"{len(samples) - len(clean)} amostra(s) acima de 300 km/h "
            "descartada(s) como artefato de rastreamento."
        )
    if not clean:
        clean = samples

    mean_ms = sum(s.speed_ms for s in clean) / len(clean)

    # Velocidade do saque = maior MEDIANA de uma janela deslizante sustentada,
    # não um pico de quadro único. O saque mantém muitos quadros consecutivos
    # de alta velocidade; já um spike isolado (reaquecimento do detector, ruído)
    # fica cercado de valores baixos e sua mediana despenca. Assim isolamos a
    # velocidade real da bola e ignoramos artefatos pontuais.
    win_len = max(3, min(7, len(clean) // 3))
    best_median = -1.0
    best_start = 0
    for i in range(0, len(clean) - win_len + 1):
        w = sorted(s.speed_ms for s in clean[i : i + win_len])
        m = w[len(w) // 2]
        if m > best_median:
            best_median = m
            best_start = i
    if best_median < 0:  # poucas amostras p/ janela: cai na mediana geral
        all_speeds = sorted(s.speed_ms for s in clean)
        best_median = all_speeds[len(all_speeds) // 2]
        best_start = 0
        win_len = len(clean)

    peak_ms = best_median
    window = clean[best_start : best_start + win_len]
    impact_frame = window[0].frame

    if fps < 100:
        notes.append(
            f"fps={fps:.0f}: para saque (150-220 km/h) use slow-motion "
            "(120-240 fps). Abaixo disso a velocidade de bola é apenas estimativa."
        )

    return SpeedResult(
        peak_kmh=peak_ms * 3.6,
        peak_ms=peak_ms,
        mean_kmh=mean_ms * 3.6,
        impact_frame=impact_frame,
        samples=samples,
        notes=notes,
    )
