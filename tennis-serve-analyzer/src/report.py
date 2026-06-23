"""Geração de saídas: CSV da trajetória, gráfico de velocidade, vídeo anotado e
resumo JSON pronto para protocolar."""

from __future__ import annotations

import csv
import json
from datetime import datetime, timezone

import cv2
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from tracking import Detection
from speed_estimator import SpeedResult


def write_trajectory_csv(path: str, trajectory: list[Detection]) -> None:
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["frame", "x_px", "y_px", "radius_px"])
        for d in trajectory:
            w.writerow([d.frame, f"{d.x:.2f}", f"{d.y:.2f}", f"{d.radius:.2f}"])


def write_speed_plot(path: str, result: SpeedResult, athlete: str) -> None:
    if not result.samples:
        return
    t = [s.t_s for s in result.samples]
    v = [s.speed_kmh for s in result.samples]

    fig, ax = plt.subplots(figsize=(9, 4.5))
    ax.plot(t, v, "-o", color="#1f77b4", ms=3, lw=1.5, label="Velocidade da bola")
    ax.axhline(
        result.peak_kmh,
        color="#d62728",
        ls="--",
        lw=1,
        label=f"Pico: {result.peak_kmh:.1f} km/h",
    )
    ax.set_xlabel("Tempo (s)")
    ax.set_ylabel("Velocidade (km/h)")
    ax.set_title(f"Perfil de velocidade do saque — {athlete}")
    ax.grid(True, alpha=0.3)
    ax.legend()
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    plt.close(fig)


def write_summary_json(
    path: str,
    athlete: str,
    result: SpeedResult,
    meta: dict,
    calib_meters_per_pixel: float,
) -> dict:
    summary = {
        "atleta": athlete,
        "gerado_em": datetime.now(timezone.utc).isoformat(),
        "captura": {
            "fps": meta.get("fps"),
            "resolucao": f"{meta.get('width')}x{meta.get('height')}",
            "quadros": meta.get("frames"),
            "deteccoes_bola": meta.get("detections"),
            "metros_por_pixel": round(calib_meters_per_pixel, 6),
        },
        "resultado": {
            "velocidade_pico_kmh": round(result.peak_kmh, 1),
            "velocidade_pico_ms": round(result.peak_ms, 2),
            "velocidade_media_kmh": round(result.mean_kmh, 1),
            "quadro_impacto": result.impact_frame,
        },
        "observacoes": result.notes,
    }
    with open(path, "w") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    return summary


def write_annotated_video(
    in_path: str,
    out_path: str,
    trajectory: list[Detection],
    result: SpeedResult,
) -> None:
    """Reescreve o vídeo com o esqueleto da trajetória e a velocidade sobreposta."""
    by_frame = {d.frame: d for d in trajectory}
    speed_by_frame = {s.frame: s.speed_kmh for s in result.samples}

    cap = cv2.VideoCapture(in_path)
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    out = cv2.VideoWriter(out_path, fourcc, fps, (width, height))

    trail: list[tuple[int, int]] = []
    frame_idx = -1
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        frame_idx += 1

        d = by_frame.get(frame_idx)
        if d is not None:
            trail.append((int(d.x), int(d.y)))
            cv2.circle(frame, (int(d.x), int(d.y)), int(d.radius) + 2, (0, 255, 0), 2)
        for i in range(1, len(trail)):
            cv2.line(frame, trail[i - 1], trail[i], (0, 200, 255), 2)

        cur_speed = speed_by_frame.get(frame_idx)
        label = f"v = {cur_speed:.0f} km/h" if cur_speed else "v = --"
        cv2.rectangle(frame, (8, 8), (320, 78), (0, 0, 0), -1)
        cv2.putText(
            frame, label, (16, 38), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 0), 2
        )
        cv2.putText(
            frame,
            f"pico {result.peak_kmh:.0f} km/h",
            (16, 68),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (0, 200, 255),
            2,
        )
        if result.impact_frame == frame_idx:
            cv2.putText(
                frame,
                "IMPACTO",
                (width // 2 - 80, 50),
                cv2.FONT_HERSHEY_SIMPLEX,
                1.0,
                (0, 0, 255),
                3,
            )
        out.write(frame)

    cap.release()
    out.release()
