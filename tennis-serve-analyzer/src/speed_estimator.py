"""Cálculo de velocidade da bola a partir da trajetória rastreada.

A velocidade do saque é a velocidade logo APÓS O IMPACTO (a bola desacelera
pelo arrasto do ar durante o voo). O cálculo é forense, em 3 passos:

  1. SEGMENTAÇÃO — separa a trajetória em trechos coerentes: o voo da bola
     segue numa direção só; braço/raquete vão-e-voltam (inversões) e
     reaquisições criam buracos. Cada inversão/buraco fecha um segmento.
  2. SELEÇÃO — o saque é o segmento mais rápido e sustentado (mediana de
     velocidade, mínimo de 3 amostras). Movimentos que não são o voo da
     bola são descartados e anotados nas observações.
  3. PICO NO IMPACTO — dentro do voo, o impacto é onde a velocidade dispara;
     o pico é a mediana das 3 maiores amostras do início do voo (robusto a
     ruído de quadro único, sem ser puxado para baixo pela desaceleração).

Reporta: peak_kmh, impact_frame, série temporal completa e observações.
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
    dxs: list[float] = []  # deslocamento horizontal (m) de cada amostra
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
        dxs.append(dx_m)

    if not samples:
        return SpeedResult(0.0, 0.0, 0.0, None, [], ["Sem amostras válidas."])

    # Rejeita saltos fisicamente impossíveis (> 300 km/h): tipicamente
    # reaquisição da bola após oclusão, não movimento real.
    MAX_PLAUSIBLE_MS = 300 / 3.6
    entries = [(s, dx) for s, dx in zip(samples, dxs)
               if s.speed_ms <= MAX_PLAUSIBLE_MS]
    if len(entries) < len(samples):
        notes.append(
            f"{len(samples) - len(entries)} amostra(s) acima de 300 km/h "
            "descartada(s) como artefato de rastreamento."
        )
    if not entries:
        entries = list(zip(samples, dxs))

    mean_ms = sum(s.speed_ms for s, _ in entries) / len(entries)

    # ---- 1) SEGMENTAÇÃO: separa o voo da bola de outros movimentos ----
    # O voo do saque é coerente: segue numa direção horizontal só. Braço e
    # raquete vão-e-voltam (invertem direção); reaquisições criam buracos.
    # Cada inversão de direção ou buraco grande inicia um novo segmento.
    MIN_DX_M = 0.03   # inversão só conta com deslocamento real (não ruído)
    MAX_GAP_FRAMES = 8
    segments: list[list[SpeedSample]] = []
    seg: list[SpeedSample] = [entries[0][0]]
    for (ps, pdx), (cs, cdx) in zip(entries, entries[1:]):
        reversal = (pdx * cdx < 0 and abs(pdx) > MIN_DX_M and abs(cdx) > MIN_DX_M)
        gap = (cs.frame - ps.frame) > MAX_GAP_FRAMES
        if reversal or gap:
            segments.append(seg)
            seg = []
        seg.append(cs)
    segments.append(seg)

    # ---- 2) SELEÇÃO: o saque é o segmento mais rápido e sustentado ----
    def _median(xs):
        xs = sorted(xs)
        return xs[len(xs) // 2]

    candidates = [s for s in segments if len(s) >= 3]
    if candidates:
        serve = max(candidates, key=lambda s: _median([x.speed_ms for x in s]))
    else:
        serve = max(segments, key=len)
    descartados = len(segments) - 1
    if descartados > 0 and len(segments) > 1:
        notes.append(
            f"{descartados} trecho(s) de movimento descartado(s) por não serem o "
            "voo da bola (ex.: braço/raquete indo e voltando, ou reaquisição). "
            "Medido apenas o voo mais rápido e coerente — confira no percurso."
        )

    # ---- 3) PICO ANCORADO NO IMPACTO ----
    # A bola é mais rápida logo após o impacto e desacelera pelo arrasto.
    # Dentro do voo, o impacto é onde a velocidade dispara; o pico é a mediana
    # das 3 maiores amostras do INÍCIO do voo (robusto a ruído de 1 quadro,
    # sem ser puxado para baixo pela desaceleração ao longo do voo).
    speeds = [s.speed_ms for s in serve]
    seg_max = max(speeds)
    start_idx = 0
    for i, v in enumerate(speeds):
        if v >= 0.6 * seg_max:
            start_idx = i
            break
    head = speeds[start_idx : start_idx + 6]
    top = sorted(head, reverse=True)[:3]
    peak_ms = top[len(top) // 2]
    impact_frame = serve[start_idx].frame

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
