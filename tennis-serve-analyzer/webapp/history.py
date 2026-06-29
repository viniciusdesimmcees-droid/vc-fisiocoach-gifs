"""Histórico do atleta: persistência das análises + gráficos de evolução e
comparação.

Armazena cada análise (atleta, data, velocidade de pico/média, fps, detector)
em um SQLite. Os gráficos são gerados sob demanda como PNG em memória.

Persistência: o caminho do banco vem de DB_PATH (padrão: webapp/data/history.db).
Em hospedagem com disco efêmero (ex.: Hugging Face grátis), os dados resetam
quando o servidor reinicia. Para histórico permanente, aponte DB_PATH para um
disco persistente (ex.: /data em planos com armazenamento) — o código não muda.
"""

from __future__ import annotations

import io
import os
import sqlite3
from datetime import datetime, timezone

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

CREDIT = "Sistema criado e desenvolvido por Vinícius Camargos da Fonseca."

def _default_db_path() -> str:
    """Escolhe onde guardar o histórico.

    Prioridade: DB_PATH explícito > disco persistente /data (ex.: armazenamento
    persistente do Hugging Face) > pasta local efêmera. Assim, basta ativar o
    armazenamento persistente no Space que o histórico passa a ser PERMANENTE,
    sem mudar código.
    """
    env = os.environ.get("DB_PATH")
    if env:
        return env
    if os.path.isdir("/data") and os.access("/data", os.W_OK):
        return "/data/history.db"
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "history.db")


DB_PATH = _default_db_path()


def _conn() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c


def init_db() -> None:
    with _conn() as c:
        c.execute(
            """CREATE TABLE IF NOT EXISTS analyses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                athlete TEXT NOT NULL,
                created_at TEXT NOT NULL,
                peak_kmh REAL,
                mean_kmh REAL,
                fps REAL,
                detector TEXT
            )"""
        )


def record_analysis(athlete, peak_kmh, mean_kmh, fps, detector) -> None:
    with _conn() as c:
        c.execute(
            "INSERT INTO analyses "
            "(athlete, created_at, peak_kmh, mean_kmh, fps, detector) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                athlete.strip() or "Atleta",
                datetime.now(timezone.utc).isoformat(),
                round(float(peak_kmh), 1),
                round(float(mean_kmh), 1),
                float(fps),
                detector,
            ),
        )


def list_athletes() -> list[dict]:
    with _conn() as c:
        rows = c.execute(
            """SELECT athlete, COUNT(*) AS n, MAX(peak_kmh) AS best,
                      AVG(peak_kmh) AS avg, MAX(created_at) AS last
               FROM analyses GROUP BY athlete ORDER BY best DESC"""
        ).fetchall()
    return [dict(r) for r in rows]


def get_history(athlete: str) -> list[dict]:
    with _conn() as c:
        rows = c.execute(
            "SELECT * FROM analyses WHERE athlete = ? ORDER BY created_at",
            (athlete,),
        ).fetchall()
    return [dict(r) for r in rows]


def athlete_stats(athlete: str) -> dict:
    h = get_history(athlete)
    if not h:
        return {}
    peaks = [r["peak_kmh"] for r in h]
    first, last = peaks[0], peaks[-1]
    return {
        "n": len(h),
        "best": max(peaks),
        "avg": round(sum(peaks) / len(peaks), 1),
        "first": first,
        "last": last,
        "delta": round(last - first, 1),
        "delta_pct": round((last - first) / first * 100, 1) if first else 0.0,
    }


def _short_date(iso: str) -> str:
    try:
        return datetime.fromisoformat(iso).strftime("%d/%m")
    except ValueError:
        return iso[:10]


def _fig_to_png(fig) -> bytes:
    buf = io.BytesIO()
    fig.text(0.5, 0.005, CREDIT, ha="center", fontsize=7, color="#9aa39c")
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    fig.savefig(buf, format="png", dpi=110)
    plt.close(fig)
    buf.seek(0)
    return buf.read()


def evolution_png(athlete: str) -> bytes:
    """Linha da velocidade de pico ao longo das análises do atleta."""
    h = get_history(athlete)
    fig, ax = plt.subplots(figsize=(8.5, 4.2))
    if h:
        xs = list(range(1, len(h) + 1))
        ys = [r["peak_kmh"] for r in h]
        labels = [_short_date(r["created_at"]) for r in h]
        ax.plot(xs, ys, "-o", color="#15803d", lw=2, ms=6, label="Velocidade de pico")
        best = max(ys)
        ax.axhline(best, ls="--", lw=1, color="#d62728", label=f"Recorde: {best:.0f} km/h")
        ax.set_xticks(xs)
        ax.set_xticklabels(labels, rotation=0, fontsize=8)
        for x, y in zip(xs, ys):
            ax.annotate(f"{y:.0f}", (x, y), textcoords="offset points",
                        xytext=(0, 7), ha="center", fontsize=8, color="#15803d")
        ax.legend(loc="lower right")
    else:
        ax.text(0.5, 0.5, "Sem análises ainda", ha="center", va="center")
    ax.set_xlabel("Análises (por data)")
    ax.set_ylabel("Velocidade (km/h)")
    ax.set_title(f"Evolução do saque — {athlete}")
    ax.grid(True, alpha=0.3)
    return _fig_to_png(fig)


def comparison_png(top: int = 12) -> bytes:
    """Barras comparando a melhor velocidade (recorde) de cada atleta."""
    athletes = list_athletes()[:top]
    fig, ax = plt.subplots(figsize=(8.5, 4.5))
    if athletes:
        names = [a["athlete"] for a in athletes]
        best = [a["best"] for a in athletes]
        avg = [round(a["avg"], 1) for a in athletes]
        y = range(len(names))
        ax.barh(y, best, color="#22c55e", label="Recorde")
        ax.barh(y, avg, color="#15803d", height=0.45, label="Média")
        ax.set_yticks(list(y))
        ax.set_yticklabels(names, fontsize=9)
        ax.invert_yaxis()
        for i, b in enumerate(best):
            ax.text(b + 1, i, f"{b:.0f}", va="center", fontsize=8, color="#15803d")
        ax.legend(loc="lower right")
    else:
        ax.text(0.5, 0.5, "Sem atletas ainda", ha="center", va="center")
    ax.set_xlabel("Velocidade (km/h)")
    ax.set_title("Comparação entre atletas")
    ax.grid(True, axis="x", alpha=0.3)
    return _fig_to_png(fig)
