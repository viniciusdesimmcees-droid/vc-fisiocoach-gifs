"""Biomecânica do saque a partir dos keypoints da pose.

Tudo aqui é GEOMETRIA PURA sobre os keypoints (não depende de deep learning),
portanto é determinístico e testável (ver tools/test_biomechanics.py):

  - ângulos articulares (cotovelo, ombro, joelho, quadril, tronco);
  - escolha do lado dominante do saque;
  - segmentação das fases do saque pela trajetória do punho;
  - sequência da cadeia cinética (timing proximal -> distal).

Convenção de eixo: em imagem, y cresce para BAIXO. "Punho alto" = y menor.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from pose_estimator import KP

CONF_MIN = 0.30  # confiança mínima do keypoint para usá-lo


def angle_at(a, b, c) -> float:
    """Ângulo (graus) no vértice b formado por a-b-c. Geometria pura."""
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    c = np.asarray(c, dtype=float)
    v1, v2 = a - b, c - b
    n1, n2 = np.linalg.norm(v1), np.linalg.norm(v2)
    if n1 == 0 or n2 == 0:
        return float("nan")
    cos = np.clip(np.dot(v1, v2) / (n1 * n2), -1.0, 1.0)
    return float(np.degrees(np.arccos(cos)))


def _pt(kp: np.ndarray, name: str):
    """Retorna (x,y) do keypoint se confiável, senão None."""
    i = KP[name]
    if kp is None or kp[i, 2] < CONF_MIN:
        return None
    return kp[i, :2]


def choose_serve_side(frames: list) -> str:
    """Lado dominante = punho que atinge o ponto mais alto (menor y) no vídeo."""
    best = {"left": np.inf, "right": np.inf}
    for kp in frames:
        if kp is None:
            continue
        for side in ("left", "right"):
            w = _pt(kp, f"{side}_wrist")
            if w is not None:
                best[side] = min(best[side], w[1])
    return "left" if best["left"] < best["right"] else "right"


@dataclass
class FrameAngles:
    frame: int
    elbow: float = float("nan")     # ombro-cotovelo-punho
    shoulder: float = float("nan")  # quadril-ombro-cotovelo (abdução)
    knee: float = float("nan")      # quadril-joelho-tornozelo
    hip: float = float("nan")       # ombro-quadril-joelho
    trunk_lean: float = float("nan")  # inclinação do tronco vs. vertical
    wrist_y: float = float("nan")   # altura do punho (px, y-imagem)


def compute_angles(frames: list, side: str) -> list[FrameAngles]:
    out: list[FrameAngles] = []
    for idx, kp in enumerate(frames):
        fa = FrameAngles(frame=idx)
        if kp is not None:
            sh = _pt(kp, f"{side}_shoulder")
            el = _pt(kp, f"{side}_elbow")
            wr = _pt(kp, f"{side}_wrist")
            hp = _pt(kp, f"{side}_hip")
            kn = _pt(kp, f"{side}_knee")
            an = _pt(kp, f"{side}_ankle")

            if sh is not None and el is not None and wr is not None:
                fa.elbow = angle_at(sh, el, wr)
            if hp is not None and sh is not None and el is not None:
                fa.shoulder = angle_at(hp, sh, el)
            if hp is not None and kn is not None and an is not None:
                fa.knee = angle_at(hp, kn, an)
            if sh is not None and hp is not None and kn is not None:
                fa.hip = angle_at(sh, hp, kn)
            if sh is not None and hp is not None:
                # inclinação do tronco em relação à vertical (0 = ereto)
                dx, dy = sh[0] - hp[0], sh[1] - hp[1]
                fa.trunk_lean = float(np.degrees(np.arctan2(abs(dx), abs(dy))))
            if wr is not None:
                fa.wrist_y = float(wr[1])
        out.append(fa)
    return out


@dataclass
class Phases:
    loading: int | None = None       # joelhos mais flexionados / punho baixo
    cocking: int | None = None       # punho começa a subir
    contact: int | None = None       # punho no ponto mais alto (impacto)
    follow_through: int | None = None


def segment_phases(angles: list[FrameAngles]) -> Phases:
    """Segmentação heurística pela trajetória vertical do punho.

    contact  = quadro de punho mais alto (menor wrist_y);
    loading  = punho mais baixo antes do contato;
    cocking  = ponto médio entre loading e contact;
    follow   = punho mais baixo depois do contato.
    """
    ys = [(a.frame, a.wrist_y) for a in angles if not np.isnan(a.wrist_y)]
    if len(ys) < 3:
        return Phases()
    contact_frame = min(ys, key=lambda t: t[1])[0]

    before = [t for t in ys if t[0] <= contact_frame]
    after = [t for t in ys if t[0] >= contact_frame]
    loading = max(before, key=lambda t: t[1])[0] if before else None
    follow = max(after, key=lambda t: t[1])[0] if after else None
    cocking = (loading + contact_frame) // 2 if loading is not None else None
    return Phases(
        loading=loading, cocking=cocking,
        contact=contact_frame, follow_through=follow,
    )


def _angular_velocity(series: list[tuple[int, float]], fps: float):
    """|dθ/dt| (graus/s) entre amostras consecutivas válidas."""
    out = []
    for (f0, a0), (f1, a1) in zip(series, series[1:]):
        if f1 == f0:
            continue
        out.append((f1, abs(a1 - a0) / ((f1 - f0) / fps)))
    return out


@dataclass
class KinematicChain:
    peak_frames: dict = field(default_factory=dict)  # junta -> quadro do pico de vel.
    proximal_to_distal: bool = False
    notes: list = field(default_factory=list)


def kinematic_sequence(angles: list[FrameAngles], fps: float) -> KinematicChain:
    """Timing do pico de velocidade angular por segmento. No saque eficiente a
    sequência é proximal -> distal: quadril/tronco antes do ombro, antes do
    cotovelo. Detectamos a ordem dos picos."""
    chain = KinematicChain()
    joints = {
        "quadril": [(a.frame, a.hip) for a in angles if not np.isnan(a.hip)],
        "tronco": [(a.frame, a.trunk_lean) for a in angles if not np.isnan(a.trunk_lean)],
        "ombro": [(a.frame, a.shoulder) for a in angles if not np.isnan(a.shoulder)],
        "cotovelo": [(a.frame, a.elbow) for a in angles if not np.isnan(a.elbow)],
    }
    for name, series in joints.items():
        av = _angular_velocity(series, fps)
        if av:
            chain.peak_frames[name] = max(av, key=lambda t: t[1])[0]

    order = [j for j in ("quadril", "tronco", "ombro", "cotovelo") if j in chain.peak_frames]
    if len(order) >= 2:
        seq = [chain.peak_frames[j] for j in order]
        chain.proximal_to_distal = all(x <= y for x, y in zip(seq, seq[1:]))
        if chain.proximal_to_distal:
            chain.notes.append("Sequência proximal->distal preservada (eficiente).")
        else:
            chain.notes.append(
                "Sequência proximal->distal quebrada: revisar timing da cadeia."
            )
    return chain


# ============================ Biomecânica profunda ============================

def _smooth(series: list[tuple[int, float]], k: int = 3) -> list[tuple[int, float]]:
    """Média móvel simples sobre (frame, valor) para reduzir ruído da pose
    antes de derivar — evita picos irreais de velocidade angular."""
    if len(series) < k:
        return series
    frames = [f for f, _ in series]
    vals = [v for _, v in series]
    out = []
    half = k // 2
    for i in range(len(vals)):
        lo, hi = max(0, i - half), min(len(vals), i + half + 1)
        out.append((frames[i], sum(vals[lo:hi]) / (hi - lo)))
    return out


def peak_angular_velocities(angles: list[FrameAngles], fps: float,
                            ceiling: float = 4000.0) -> dict:
    """Pico de velocidade angular (°/s) por junta — quão rápido cada segmento
    gira. Indicador de explosão/potência do gesto. A série é suavizada e o
    valor é limitado a um teto fisiológico para descartar ruído da pose."""
    series = {
        "quadril": [(a.frame, a.hip) for a in angles if not np.isnan(a.hip)],
        "tronco": [(a.frame, a.trunk_lean) for a in angles if not np.isnan(a.trunk_lean)],
        "ombro": [(a.frame, a.shoulder) for a in angles if not np.isnan(a.shoulder)],
        "cotovelo": [(a.frame, a.elbow) for a in angles if not np.isnan(a.elbow)],
        "joelho": [(a.frame, a.knee) for a in angles if not np.isnan(a.knee)],
    }
    out = {}
    for name, s in series.items():
        av = _angular_velocity(_smooth(s), fps)
        if av:
            out[name] = round(min(max(v for _, v in av), ceiling), 0)
    return out


def phase_durations_ms(phases: Phases, fps: float) -> dict:
    """Duração de cada fase do saque em milissegundos."""
    if not fps or fps <= 0:
        return {}

    def ms(a, b):
        if a is None or b is None:
            return None
        return round((b - a) / fps * 1000.0, 0)

    return {
        "carregamento": ms(phases.loading, phases.cocking),
        "armada": ms(phases.cocking, phases.contact),
        "aceleracao_total": ms(phases.loading, phases.contact),
        "finalizacao": ms(phases.contact, phases.follow_through),
    }


def x_factor(frames: list, side: str) -> dict:
    """X-Factor: separação ombro–quadril (rotação do tronco) — métrica de ouro
    da potência. ESTIMATIVA 2D no plano da imagem; requer ver os dois ombros e
    os dois quadris (melhor em câmera frontal/traseira)."""
    best = 0.0
    n = 0
    for kp in frames:
        if kp is None:
            continue
        ls, rs = _pt(kp, "left_shoulder"), _pt(kp, "right_shoulder")
        lh, rh = _pt(kp, "left_hip"), _pt(kp, "right_hip")
        if any(p is None for p in (ls, rs, lh, rh)):
            continue
        sh_vec = np.asarray(rs) - np.asarray(ls)
        hp_vec = np.asarray(rh) - np.asarray(lh)
        ns, nh = np.linalg.norm(sh_vec), np.linalg.norm(hp_vec)
        if ns < 1e-3 or nh < 1e-3:
            continue
        cos = np.clip(np.dot(sh_vec, hp_vec) / (ns * nh), -1.0, 1.0)
        sep = float(np.degrees(np.arccos(cos)))
        best = max(best, sep)
        n += 1
    if n < 3:
        return {"disponivel": False}
    return {"disponivel": True, "separacao_max_graus": round(best, 0)}


def injury_flags(angles: list[FrameAngles], phases: Phases) -> list[dict]:
    """Indicadores de risco (NÃO é diagnóstico médico) a partir de ângulos-chave.
    Heurísticas de coaching/fisio para sinalizar pontos a investigar."""
    flags: list[dict] = []

    def at(frame):
        for a in angles:
            if a.frame == frame:
                return a
        return None

    contato = at(phases.contact)
    loading = at(phases.loading)

    if contato is not None and not np.isnan(contato.trunk_lean) and contato.trunk_lean > 35:
        flags.append({"area": "Lombar", "nivel": "atenção",
                      "texto": f"Inclinação de tronco acentuada no impacto "
                               f"({contato.trunk_lean:.0f}°) — atenção à sobrecarga lombar."})
    if contato is not None and not np.isnan(contato.elbow) and contato.elbow < 100:
        flags.append({"area": "Cotovelo/Ombro", "nivel": "atenção",
                      "texto": f"Cotovelo muito flexionado no impacto "
                               f"({contato.elbow:.0f}°) — risco de sobrecarga no ombro/cotovelo."})
    if loading is not None and not np.isnan(loading.knee) and loading.knee > 168:
        flags.append({"area": "Pernas/Ombro", "nivel": "atenção",
                      "texto": "Pouca flexão de joelhos no carregamento — menos "
                               "absorção das pernas, mais carga em ombro/tronco."})
    if not flags:
        flags.append({"area": "Geral", "nivel": "ok",
                      "texto": "Nenhum indicador de risco evidente nos ângulos analisados."})
    return flags


def deep_metrics(frames: list, angles: list[FrameAngles], phases: Phases,
                 fps: float, side: str) -> dict:
    """Reúne as métricas biomecânicas avançadas em um dicionário."""
    return {
        "velocidades_angulares_max": peak_angular_velocities(angles, fps),
        "duracao_fases_ms": phase_durations_ms(phases, fps),
        "x_factor": x_factor(frames, side),
        "indicadores_risco": injury_flags(angles, phases),
    }
