"""Reconhecimento automático do golpe (saque / forehand / backhand) a partir
da sequência de pose (keypoints COCO).

É um classificador por REGRAS transparentes — devolve os sinais que usou e um
nível de confiança. Funciona melhor com captura lateral/frontal estável. O
profissional pode sempre escolher o golpe manualmente (a escolha manual vence).

Sinais (invariantes à orientação da câmera):
- Alcance vertical do punho acima dos ombros/cabeça  -> SAQUE
- No contato, o punho da raquete cruza ou não a linha média do corpo:
  mesmo lado do próprio ombro -> FOREHAND; lado oposto (cruzou) -> BACKHAND
"""

from __future__ import annotations

import numpy as np

# índices COCO
NOSE = 0
L_SH, R_SH = 5, 6
L_WR, R_WR = 9, 10
L_HIP, R_HIP = 11, 12

_CONF = 0.3

GOLPES = {
    "saque": {"nome": "Saque", "icone": "🎾"},
    "forehand": {"nome": "Forehand (direita)", "icone": "👉"},
    "backhand": {"nome": "Backhand (esquerda)", "icone": "👈"},
    "indeterminado": {"nome": "Indeterminado", "icone": "❔"},
}


def _pt(frame, idx):
    """Retorna (x, y) do keypoint se confiável, senão None."""
    if frame is None:
        return None
    x, y, c = frame[idx]
    if c < _CONF:
        return None
    return np.array([x, y], dtype=np.float32)


def _series(frames, idx):
    """Série temporal (N,2) de um keypoint, com NaN onde não há detecção."""
    out = np.full((len(frames), 2), np.nan, dtype=np.float32)
    for i, f in enumerate(frames):
        p = _pt(f, idx)
        if p is not None:
            out[i] = p
    return out


def _mid(a, b):
    return (a + b) / 2.0


def _nanmedian(x):
    return float(np.nanmedian(x)) if np.isfinite(x).any() else float("nan")


def classify(frames: list, fps: float = 30.0) -> dict | None:
    """Classifica o golpe. Retorna dict com golpe, confiança e sinais, ou None
    se não houver pose suficiente."""
    if not frames:
        return None
    total = len(frames)
    detected = sum(1 for f in frames if f is not None)
    if detected < 5:
        return None
    valid_ratio = detected / total

    sh_l, sh_r = _series(frames, L_SH), _series(frames, R_SH)
    hip_l, hip_r = _series(frames, L_HIP), _series(frames, R_HIP)
    wr_l, wr_r = _series(frames, L_WR), _series(frames, R_WR)
    nose = _series(frames, NOSE)

    sh_mid = _mid(sh_l, sh_r)
    hip_mid = _mid(hip_l, hip_r)

    # escala do corpo: comprimento médio do tronco (ombro -> quadril)
    torso = _nanmedian(np.linalg.norm(sh_mid - hip_mid, axis=1))
    sh_width = _nanmedian(np.linalg.norm(sh_l - sh_r, axis=1))
    if not (np.isfinite(torso) and torso > 1):
        return None

    # punho da raquete: o que mais se mexe (maior diagonal do movimento)
    def _motion(w):
        finite = w[np.isfinite(w).all(axis=1)]
        if len(finite) < 3:
            return -1.0
        return float(np.hypot(np.ptp(finite[:, 0]), np.ptp(finite[:, 1])))

    if _motion(wr_r) >= _motion(wr_l):
        wr, rsh, lado = wr_r, sh_r, "direito"
    else:
        wr, lsh_unused, lado = wr_l, sh_l, "esquerdo"
        rsh = sh_l

    # --- alcance vertical (em image-coords, y menor = mais alto) ---
    wr_y = wr[:, 1]
    valid_y = np.isfinite(wr_y)
    top_frame = int(np.nanargmin(np.where(valid_y, wr_y, np.inf)))
    sh_y_top = sh_mid[top_frame, 1]
    reach = (sh_y_top - wr_y[top_frame]) / torso  # >0: punho acima dos ombros
    nose_y_top = nose[top_frame, 1]
    acima_da_cabeca = np.isfinite(nose_y_top) and wr_y[top_frame] < nose_y_top

    sinais = []

    # --- regra do saque ---
    if reach >= 1.1 and acima_da_cabeca:
        margem = min(1.0, (reach - 1.1) / 0.9)
        conf = 0.55 + 0.4 * margem
        sinais.append(f"Punho atinge {reach:.1f}× o tronco acima dos ombros "
                      "(extensão acima da cabeça).")
        return _result("saque", conf * valid_ratio, sinais, lado, reach=reach)

    # --- groundstroke: forehand x backhand pela travessia da linha média ---
    # contato ≈ quadro de maior velocidade horizontal do punho
    wr_x = wr[:, 0]
    vx = np.full(total, np.nan, dtype=np.float32)
    last_i, last_x = None, None
    for i in range(total):
        if np.isfinite(wr_x[i]):
            if last_i is not None:
                vx[i] = abs(wr_x[i] - last_x) / max(1, i - last_i)
            last_i, last_x = i, wr_x[i]
    if not np.isfinite(vx).any():
        return _result("indeterminado", 0.2, ["Movimento horizontal insuficiente."],
                       lado)
    contato = int(np.nanargmax(np.where(np.isfinite(vx), vx, -np.inf)))

    # média numa pequena janela em torno do contato (mais estável que 1 quadro)
    lo, hi = max(0, contato - 2), min(total, contato + 3)
    mid_x = _nanmedian(sh_mid[lo:hi, 0])
    wr_x_c = _nanmedian(wr_x[lo:hi])
    rsh_x_c = _nanmedian(rsh[lo:hi, 0])
    if not (np.isfinite(mid_x) and np.isfinite(wr_x_c) and np.isfinite(rsh_x_c)):
        mid_x = _nanmedian(sh_mid[:, 0])
        wr_x_c = _nanmedian(wr_x)
        rsh_x_c = _nanmedian(rsh[:, 0])

    dom_side = np.sign(rsh_x_c - mid_x) or 1.0   # lado do ombro da raquete
    cross = (wr_x_c - mid_x) * dom_side          # >0 mesmo lado (forehand)
    cross_norm = cross / (sh_width if sh_width and sh_width > 1 else torso)

    margem = min(1.0, abs(cross_norm) / 0.6)
    conf = (0.5 + 0.4 * margem) * valid_ratio
    if cross_norm >= 0:
        sinais.append("No contato, o braço da raquete fica do mesmo lado do corpo "
                      "(golpe aberto).")
        return _result("forehand", conf, sinais, lado, reach=reach, cross=cross_norm)
    else:
        sinais.append("No contato, o braço da raquete cruza para o outro lado do "
                      "corpo (atravessa o tronco).")
        return _result("backhand", conf, sinais, lado, reach=reach, cross=cross_norm)


def _result(golpe, conf, sinais, lado, reach=None, cross=None):
    conf = float(max(0.05, min(0.98, conf)))
    if conf >= 0.75:
        nivel = "Alta"
    elif conf >= 0.5:
        nivel = "Média"
    else:
        nivel = "Baixa"
    meta = GOLPES.get(golpe, GOLPES["indeterminado"])
    return {
        "golpe": golpe,
        "nome": meta["nome"],
        "icone": meta["icone"],
        "confianca": conf,
        "confianca_pct": round(conf * 100),
        "confianca_nivel": nivel,
        "braco_dominante": lado,
        "sinais": sinais,
        "automatico": True,
    }


def manual(golpe: str) -> dict | None:
    """Resultado a partir da escolha manual do profissional."""
    if golpe not in GOLPES or golpe == "indeterminado":
        return None
    meta = GOLPES[golpe]
    return {
        "golpe": golpe,
        "nome": meta["nome"],
        "icone": meta["icone"],
        "confianca": 1.0,
        "confianca_pct": 100,
        "confianca_nivel": "Manual",
        "braco_dominante": None,
        "sinais": ["Selecionado manualmente pelo profissional."],
        "automatico": False,
    }
