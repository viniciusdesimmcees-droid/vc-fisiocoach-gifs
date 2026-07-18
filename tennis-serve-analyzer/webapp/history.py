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
import json
import os
import sqlite3
from datetime import datetime, timezone

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

import storage  # persistência opcional (Dataset do HF)


def _sync() -> None:
    """Salva o banco no cofre permanente após cada gravação (se ativado)."""
    try:
        storage.push_db(DB_PATH)
    except Exception:
        pass

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


# Campos da ficha/anamnese do atleta (além de "name").
ATHLETE_FIELDS = [
    "birthdate", "height_cm", "weight_kg", "dominant_hand", "level",
    "since_year", "train_hours", "contact", "injuries", "pain",
    "conditions", "goals", "notes",
]


def init_db() -> None:
    # restaura o banco do cofre permanente (se ativado) antes de abrir
    try:
        storage.pull_db(DB_PATH)
    except Exception:
        pass
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
        # migração: colunas do golpe + plano inteligente + percurso da bola
        existing = {r["name"] for r in c.execute("PRAGMA table_info(analyses)")}
        if "stroke" not in existing:
            c.execute("ALTER TABLE analyses ADD COLUMN stroke TEXT")
        if "intel" not in existing:
            c.execute("ALTER TABLE analyses ADD COLUMN intel TEXT")
        if "traj_blob" not in existing:
            c.execute("ALTER TABLE analyses ADD COLUMN traj_blob BLOB")
        if "biomech" not in existing:
            c.execute("ALTER TABLE analyses ADD COLUMN biomech TEXT")
        # incluir=0 tira a análise dos laudos/estatísticas (ex.: captura ruim)
        if "incluir" not in existing:
            c.execute("ALTER TABLE analyses ADD COLUMN incluir INTEGER DEFAULT 1")
        c.execute(
            """CREATE TABLE IF NOT EXISTS athletes (
                name TEXT PRIMARY KEY,
                birthdate TEXT, height_cm REAL, weight_kg REAL,
                dominant_hand TEXT, level TEXT, since_year INTEGER,
                train_hours REAL, contact TEXT,
                injuries TEXT, pain TEXT, conditions TEXT, goals TEXT,
                notes TEXT, updated_at TEXT
            )"""
        )
        c.execute(
            """CREATE TABLE IF NOT EXISTS posture_assessments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                athlete TEXT NOT NULL,
                created_at TEXT NOT NULL,
                view TEXT,
                alertas INTEGER,
                graves INTEGER,
                image_url TEXT,
                medidas TEXT
            )"""
        )
        # migração: guarda a FOTO anotada no banco (permanente) para comparativo
        pcols = {r["name"] for r in c.execute("PRAGMA table_info(posture_assessments)")}
        if "image_blob" not in pcols:
            c.execute("ALTER TABLE posture_assessments ADD COLUMN image_blob BLOB")
        c.execute(
            """CREATE TABLE IF NOT EXISTS movement_tests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                athlete TEXT NOT NULL,
                created_at TEXT NOT NULL,
                teste TEXT, nome TEXT,
                alertas INTEGER, graves INTEGER,
                medidas TEXT, deficits TEXT, exercicios TEXT,
                image_blob BLOB
            )"""
        )
        # sessões NeuroFES (eletroterapia) — registro longitudinal por paciente
        c.execute(
            """CREATE TABLE IF NOT EXISTS neuro_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                patient TEXT NOT NULL,
                created_at TEXT NOT NULL,
                movimento TEXT, objetivo TEXT,
                modalidade TEXT, modalidade_nome TEXT,
                seguranca TEXT,
                avaliacao TEXT, escalas TEXT, obs TEXT
            )"""
        )
        # configurações do operador (ex.: métricas excluídas da leitura)
        c.execute(
            """CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY, value TEXT
            )"""
        )


# ----------------------------- ficha do atleta -----------------------------

def get_profile(name: str) -> dict | None:
    with _conn() as c:
        row = c.execute("SELECT * FROM athletes WHERE name = ?", (name,)).fetchone()
    return dict(row) if row else None


def save_profile(name: str, data: dict) -> None:
    """Cria ou atualiza a ficha/anamnese do atleta."""
    cols = ["name"] + ATHLETE_FIELDS + ["updated_at"]
    vals = [name] + [data.get(f) for f in ATHLETE_FIELDS] + [
        datetime.now(timezone.utc).isoformat()
    ]
    placeholders = ", ".join("?" for _ in cols)
    with _conn() as c:
        c.execute(
            f"INSERT OR REPLACE INTO athletes ({', '.join(cols)}) "
            f"VALUES ({placeholders})",
            vals,
        )
    _sync()


def age_from_birthdate(birthdate: str | None) -> int | None:
    if not birthdate:
        return None
    try:
        b = datetime.fromisoformat(birthdate)
    except ValueError:
        try:
            b = datetime.strptime(birthdate, "%Y-%m-%d")
        except ValueError:
            return None
    today = datetime.now()
    return today.year - b.year - ((today.month, today.day) < (b.month, b.day))


def bmi(height_cm, weight_kg):
    try:
        h = float(height_cm) / 100.0
        return round(float(weight_kg) / (h * h), 1) if h > 0 else None
    except (TypeError, ValueError, ZeroDivisionError):
        return None


# ----------------------- editar/corrigir o histórico -----------------------

def delete_analysis(analysis_id: int) -> None:
    with _conn() as c:
        c.execute("DELETE FROM analyses WHERE id = ?", (analysis_id,))
    _sync()


def update_analysis(analysis_id: int, peak_kmh=None, mean_kmh=None,
                    created_at=None) -> None:
    sets, vals = [], []
    if peak_kmh is not None:
        sets.append("peak_kmh = ?"); vals.append(round(float(peak_kmh), 1))
    if mean_kmh is not None:
        sets.append("mean_kmh = ?"); vals.append(round(float(mean_kmh), 1))
    if created_at:
        sets.append("created_at = ?"); vals.append(created_at)
    if not sets:
        return
    vals.append(analysis_id)
    with _conn() as c:
        c.execute(f"UPDATE analyses SET {', '.join(sets)} WHERE id = ?", vals)
    _sync()


def rename_athlete(old: str, new: str) -> None:
    new = new.strip()
    if not new or new == old:
        return
    with _conn() as c:
        c.execute("UPDATE analyses SET athlete = ? WHERE athlete = ?", (new, old))
        c.execute("UPDATE posture_assessments SET athlete = ? WHERE athlete = ?", (new, old))
        c.execute("UPDATE movement_tests SET athlete = ? WHERE athlete = ?", (new, old))
        c.execute("UPDATE OR REPLACE athletes SET name = ? WHERE name = ?", (new, old))
    _sync()


def delete_athlete(name: str) -> None:
    """Apaga o atleta e TUDO dele: análises, avaliações posturais e ficha."""
    with _conn() as c:
        c.execute("DELETE FROM analyses WHERE athlete = ?", (name,))
        c.execute("DELETE FROM posture_assessments WHERE athlete = ?", (name,))
        c.execute("DELETE FROM movement_tests WHERE athlete = ?", (name,))
        c.execute("DELETE FROM athletes WHERE name = ?", (name,))
    _sync()


# ----------------------------- configurações -------------------------------

def get_setting(key: str, default=None):
    with _conn() as c:
        row = c.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else default


def set_setting(key: str, value: str) -> None:
    with _conn() as c:
        c.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
                  (key, value))
    _sync()


def get_excluded_metrics() -> set[str]:
    """Métricas que o operador marcou para NÃO participar da leitura."""
    raw = get_setting("excluded_metrics")
    if not raw:
        return set()
    try:
        return set(json.loads(raw))
    except (ValueError, TypeError):
        return set()


def set_excluded_metrics(keys) -> None:
    set_setting("excluded_metrics", json.dumps(sorted(set(keys)), ensure_ascii=False))


# Como a análise é feita: o operador liga/desliga cada bloco e define o padrão.
DEFAULT_ANALYSIS_PREFS = {
    "ball_diameter_cm": 6.7,   # diâmetro padrão da bola (foam/junior variam)
    "usar_bola": True,         # verificação/calibração automática pela bola
    "previoo": True,           # checagem da qualidade da captura
    "confianca": False,        # selo de confiança (± margem) — DESLIGADO por
                               # padrão: é ferramenta interna do operador e
                               # pode confundir/desacreditar diante do atleta
    "didatico": True,          # resumo em palavras simples
    "glossario": True,         # glossário de termos
    "referencias": True,       # comparação com referências científicas
    "benchmark": True,         # benchmark vs. profissional
    "plano": True,             # plano inteligente (risco/músculos/treino)
}


def get_analysis_prefs() -> dict:
    prefs = dict(DEFAULT_ANALYSIS_PREFS)
    raw = get_setting("analysis_prefs")
    if raw:
        try:
            for k, v in json.loads(raw).items():
                if k in prefs:
                    prefs[k] = v
        except (ValueError, TypeError):
            pass
    return prefs


def set_analysis_prefs(prefs: dict) -> None:
    clean = {k: prefs[k] for k in DEFAULT_ANALYSIS_PREFS if k in prefs}
    set_setting("analysis_prefs", json.dumps(clean, ensure_ascii=False))


def record_analysis(athlete, peak_kmh, mean_kmh, fps, detector,
                    stroke=None, intel=None, traj_bytes=None,
                    biomech=None) -> int:
    with _conn() as c:
        cur = c.execute(
            "INSERT INTO analyses "
            "(athlete, created_at, peak_kmh, mean_kmh, fps, detector, stroke, "
            "intel, traj_blob, biomech) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                athlete.strip() or "Atleta",
                datetime.now(timezone.utc).isoformat(),
                round(float(peak_kmh), 1),
                round(float(mean_kmh), 1),
                float(fps),
                detector,
                json.dumps(stroke, ensure_ascii=False) if stroke else None,
                json.dumps(intel, ensure_ascii=False) if intel else None,
                sqlite3.Binary(traj_bytes) if traj_bytes else None,
                json.dumps(biomech, ensure_ascii=False) if biomech else None,
            ),
        )
        new_id = cur.lastrowid
    _sync()
    return new_id


def latest_biomech(athlete: str) -> tuple[dict | None, str | None]:
    """Biomecânica salva mais recente do atleta: (resumo, data_iso)."""
    for r in reversed(get_history(athlete)):
        if r.get("biomech"):
            try:
                return json.loads(r["biomech"]), r.get("created_at")
            except (ValueError, TypeError):
                continue
    return None, None


def get_analysis_traj(analysis_id: int) -> bytes | None:
    with _conn() as c:
        row = c.execute("SELECT traj_blob FROM analyses WHERE id = ?",
                        (analysis_id,)).fetchone()
    if row and row["traj_blob"] is not None:
        return bytes(row["traj_blob"])
    return None


def latest_extras(athlete: str) -> tuple[dict | None, dict | None]:
    """Golpe reconhecido + plano inteligente da análise mais recente que os têm."""
    golpe = intel = None
    for r in reversed(get_history(athlete)):
        if golpe is None and r.get("stroke"):
            try:
                golpe = json.loads(r["stroke"])
            except (ValueError, TypeError):
                pass
        if intel is None and r.get("intel"):
            try:
                intel = json.loads(r["intel"])
            except (ValueError, TypeError):
                pass
        if golpe and intel:
            break
    return golpe, intel


# ----------------------- avaliação postural (histórico) -----------------------

VIEW_LABEL = {"frente": "Frontal", "costas": "Posterior",
              "lado": "Lateral", "lateral": "Lateral",
              "lado_dir": "Perfil direito", "lado_esq": "Perfil esquerdo"}


def record_posture(athlete, view, resultado: dict, image_url=None,
                   image_bytes: bytes | None = None) -> int:
    """Salva uma avaliação postural no histórico do atleta. A foto anotada é
    guardada no banco (BLOB) para ficar permanente e permitir o comparativo."""
    medidas = [
        {"chave": m.get("chave"), "nome": m.get("nome"), "graus": m.get("graus"),
         "valor": m.get("valor"), "situacao": m.get("situacao"),
         "icone": m.get("icone")}
        for m in resultado.get("medidas", [])
    ]
    with _conn() as c:
        cur = c.execute(
            "INSERT INTO posture_assessments "
            "(athlete, created_at, view, alertas, graves, image_url, medidas, image_blob) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                (athlete or "Atleta").strip() or "Atleta",
                datetime.now(timezone.utc).isoformat(),
                view,
                int(resultado.get("alertas", 0)),
                int(resultado.get("graves", 0)),
                image_url,
                json.dumps(medidas, ensure_ascii=False),
                sqlite3.Binary(image_bytes) if image_bytes else None,
            ),
        )
        new_id = cur.lastrowid
    _sync()
    return new_id


def get_posture_image(assessment_id: int) -> bytes | None:
    with _conn() as c:
        row = c.execute(
            "SELECT image_blob FROM posture_assessments WHERE id = ?",
            (assessment_id,),
        ).fetchone()
    if row and row["image_blob"] is not None:
        return bytes(row["image_blob"])
    return None


def get_posture_history(athlete: str) -> list[dict]:
    with _conn() as c:
        rows = c.execute(
            "SELECT * FROM posture_assessments WHERE athlete = ? ORDER BY created_at",
            (athlete,),
        ).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["tem_imagem"] = d.pop("image_blob", None) is not None
        try:
            d["medidas"] = json.loads(d.get("medidas") or "[]")
        except (ValueError, TypeError):
            d["medidas"] = []
        d["view_label"] = VIEW_LABEL.get(d.get("view"), d.get("view") or "—")
        out.append(d)
    return out


def delete_posture(assessment_id: int) -> None:
    with _conn() as c:
        c.execute("DELETE FROM posture_assessments WHERE id = ?", (assessment_id,))
    _sync()


def posture_evolution_png(athlete: str) -> bytes:
    """Linhas de cada assimetria postural (graus) ao longo do tempo.
    Quanto MENOR o ângulo, mais simétrico."""
    h = get_posture_history(athlete)
    fig, ax = plt.subplots(figsize=(8.5, 4.4))
    # agrupa por métrica (chave): série de (data, |graus|)
    series: dict[str, dict] = {}
    for i, a in enumerate(h):
        for m in a["medidas"]:
            ch = m.get("chave")
            if ch is None or m.get("graus") is None:
                continue
            s = series.setdefault(ch, {"nome": m.get("nome", ch), "x": [], "y": []})
            s["x"].append(i + 1)
            s["y"].append(abs(float(m["graus"])))

    if series:
        labels = [_short_date(a["created_at"]) for a in h]
        for ch, s in series.items():
            ax.plot(s["x"], s["y"], "-o", lw=2, ms=5, label=s["nome"])
        ax.axhline(2.0, ls="--", lw=1, color="#15803d", alpha=0.7,
                   label="Faixa simétrica (≤2°)")
        ax.set_xticks(list(range(1, len(h) + 1)))
        ax.set_xticklabels(labels, fontsize=8)
        ax.legend(loc="upper right", fontsize=8, ncol=2)
        ax.set_ylim(bottom=0)
    else:
        ax.text(0.5, 0.5, "Sem avaliações posturais ainda", ha="center", va="center")
    ax.set_xlabel("Avaliações (por data)")
    ax.set_ylabel("Assimetria (graus) — menor é melhor")
    ax.set_title(f"Evolução postural — {athlete}")
    ax.grid(True, alpha=0.3)
    return _fig_to_png(fig)


# ------------------------ testes de movimento -------------------------

def record_movement_test(athlete, resultado: dict, exercicios: list,
                         image_bytes: bytes | None = None) -> int:
    with _conn() as c:
        cur = c.execute(
            "INSERT INTO movement_tests (athlete, created_at, teste, nome, "
            "alertas, graves, medidas, deficits, exercicios, image_blob) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                (athlete or "Atleta").strip() or "Atleta",
                datetime.now(timezone.utc).isoformat(),
                resultado.get("teste"), resultado.get("nome"),
                int(resultado.get("alertas", 0)), int(resultado.get("graves", 0)),
                json.dumps(resultado.get("medidas", []), ensure_ascii=False),
                json.dumps(resultado.get("deficits", []), ensure_ascii=False),
                json.dumps(exercicios or [], ensure_ascii=False),
                sqlite3.Binary(image_bytes) if image_bytes else None,
            ),
        )
        new_id = cur.lastrowid
    _sync()
    return new_id


def get_movement_tests(athlete: str) -> list[dict]:
    with _conn() as c:
        rows = c.execute(
            "SELECT * FROM movement_tests WHERE athlete = ? ORDER BY created_at",
            (athlete,),
        ).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["tem_imagem"] = d.pop("image_blob", None) is not None
        for campo in ("medidas", "deficits", "exercicios"):
            try:
                d[campo] = json.loads(d.get(campo) or "[]")
            except (ValueError, TypeError):
                d[campo] = []
        out.append(d)
    return out


def get_movement_image(test_id: int) -> bytes | None:
    with _conn() as c:
        row = c.execute("SELECT image_blob FROM movement_tests WHERE id = ?",
                        (test_id,)).fetchone()
    if row and row["image_blob"] is not None:
        return bytes(row["image_blob"])
    return None


def delete_movement_test(test_id: int) -> None:
    with _conn() as c:
        c.execute("DELETE FROM movement_tests WHERE id = ?", (test_id,))
    _sync()


# --------------------------- sessões NeuroFES ---------------------------

def record_neuro_session(patient: str, av: dict, prescricao: dict,
                         escalas: dict, obs: str = "") -> int:
    """Grava uma sessão de eletroterapia (avaliação + prescrição + escalas)."""
    principal = (prescricao or {}).get("principal") or {}
    seguranca = ((prescricao or {}).get("seguranca") or {}).get("nivel", "")
    with _conn() as c:
        cur = c.execute(
            "INSERT INTO neuro_sessions (patient, created_at, movimento, objetivo, "
            "modalidade, modalidade_nome, seguranca, avaliacao, escalas, obs) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                (patient or "Paciente").strip() or "Paciente",
                datetime.now(timezone.utc).isoformat(),
                av.get("movimento"), av.get("objetivo"),
                principal.get("chave"), principal.get("nome"),
                seguranca,
                json.dumps(av, ensure_ascii=False),
                json.dumps(escalas or {}, ensure_ascii=False),
                (obs or "").strip(),
            ),
        )
        new_id = cur.lastrowid
    _sync()
    return new_id


def get_neuro_sessions(patient: str) -> list[dict]:
    with _conn() as c:
        rows = c.execute(
            "SELECT * FROM neuro_sessions WHERE patient = ? ORDER BY created_at",
            (patient,),
        ).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        try:
            d["av"] = json.loads(d.get("avaliacao") or "{}")
        except (ValueError, TypeError):
            d["av"] = {}
        try:
            d["escalas"] = json.loads(d.get("escalas") or "{}")
        except (ValueError, TypeError):
            d["escalas"] = {}
        out.append(d)
    return out


def neuro_patients() -> list[dict]:
    """Lista de pacientes com sessões NeuroFES (nome, nº sessões, última data)."""
    with _conn() as c:
        rows = c.execute(
            "SELECT patient, COUNT(*) AS n, MAX(created_at) AS last "
            "FROM neuro_sessions GROUP BY patient ORDER BY last DESC"
        ).fetchall()
    return [dict(r) for r in rows]


def delete_neuro_session(session_id: int) -> None:
    with _conn() as c:
        c.execute("DELETE FROM neuro_sessions WHERE id = ?", (session_id,))
    _sync()


def neuro_evolution_png(patient: str) -> bytes:
    """Curva das escalas objetivas ao longo das sessões NeuroFES."""
    import neuro as _neuro
    sess = get_neuro_sessions(patient)
    fig, ax = plt.subplots(figsize=(8.5, 4.4))
    plotou = False
    if sess:
        labels = [_short_date(s["created_at"]) for s in sess]
        for chave, meta in _neuro.ESCALAS_NUM.items():
            rot, mn, mx, direcao, _desc = meta
            xs, ys = [], []
            for i, s in enumerate(sess):
                v = s.get("escalas", {}).get(chave)
                if v is None:
                    continue
                xs.append(i + 1)
                # normaliza 0–100% da faixa; escalas "down" (MAS/EVA) são
                # invertidas para que SUBIR no gráfico = melhora clínica.
                frac = (float(v) - mn) / (mx - mn) if mx > mn else 0.0
                if direcao == "down":
                    frac = 1.0 - frac
                ys.append(100.0 * frac)
            if len(xs) >= 1:
                sufixo = " (invertida)" if direcao == "down" else ""
                ax.plot(xs, ys, "-o", lw=2, ms=5, label=rot + sufixo)
                plotou = True
        ax.set_xticks(list(range(1, len(sess) + 1)))
        ax.set_xticklabels(labels, fontsize=8)
        ax.set_ylim(-2, 102)
    if plotou:
        ax.legend(loc="best", fontsize=8, ncol=3)
    else:
        ax.text(0.5, 0.5, "Registre escalas (FMA-UE, ARAT, MAS...) em ao menos "
                "uma sessão", ha="center", va="center", fontsize=9)
    ax.set_xlabel("Sessões (por data)")
    ax.set_ylabel("% da faixa — mais alto é melhor")
    ax.set_title(f"Evolução NeuroFES — {patient}")
    ax.grid(True, alpha=0.3)
    return _fig_to_png(fig)


def list_athletes() -> list[dict]:
    """Todos os atletas — inclui quem só tem ficha ou só avaliação postural."""
    with _conn() as c:
        serve = {r["athlete"]: dict(r) for r in c.execute(
            """SELECT athlete, COUNT(*) AS n, MAX(peak_kmh) AS best,
                      AVG(peak_kmh) AS avg, MAX(created_at) AS last
               FROM analyses WHERE COALESCE(incluir, 1) = 1
               GROUP BY athlete""")}
        post = {r["athlete"]: r["n"] for r in c.execute(
            "SELECT athlete, COUNT(*) AS n FROM posture_assessments GROUP BY athlete")}
        profs = {r["name"] for r in c.execute("SELECT name FROM athletes")}
    names = set(serve) | set(post) | profs
    out = []
    for name in names:
        s = serve.get(name)
        out.append({
            "athlete": name,
            "n": s["n"] if s else 0,
            "best": s["best"] if s else None,
            "avg": round(s["avg"], 1) if s and s["avg"] is not None else None,
            "last": s["last"] if s else None,
            "n_posturas": post.get(name, 0),
            "tem_ficha": name in profs,
        })
    out.sort(key=lambda a: (-(a["best"] or 0), a["athlete"].lower()))
    return out


def recent_activity(limit: int = 8) -> list[dict]:
    """Últimas atividades de todos os alunos (análises + posturais)."""
    with _conn() as c:
        rows = c.execute(
            """SELECT 'saque' AS tipo, athlete, created_at, peak_kmh AS valor,
                      NULL AS view
                 FROM analyses
               UNION ALL
               SELECT 'postura', athlete, created_at, NULL, view
                 FROM posture_assessments
               UNION ALL
               SELECT 'teste', athlete, created_at, NULL, nome
                 FROM movement_tests
               ORDER BY created_at DESC LIMIT ?""",
            (limit,),
        ).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        iso = d.get("created_at") or ""
        d["data"] = f"{iso[8:10]}/{iso[5:7]}/{iso[0:4]}" if len(iso) >= 10 else iso
        if d["tipo"] == "saque":
            d["icone"] = "🎾"
            d["texto"] = f"Saque analisado — pico {d.get('valor') or 0:.0f} km/h"
        elif d["tipo"] == "teste":
            d["icone"] = "🏋️"
            d["texto"] = f"Teste de movimento — {d.get('view') or ''}"
        else:
            vista = {"frente": "frontal", "costas": "posterior",
                     "lado": "lateral", "lateral": "lateral"}.get(d.get("view"), "")
            d["icone"] = "🧍"
            d["texto"] = f"Avaliação postural {vista}".strip()
        out.append(d)
    return out


def export_data(athlete: str) -> dict:
    """Todos os dados do atleta em dict (para o 'livro de dados' / JSON)."""
    return {
        "atleta": athlete,
        "gerado_em": datetime.now(timezone.utc).isoformat(),
        "ficha": get_profile(athlete),
        "estatisticas_saque": athlete_stats(athlete),
        "analises_saque": get_history(athlete),
        "avaliacoes_posturais": get_posture_history(athlete),
        "testes_movimento": get_movement_tests(athlete),
    }


def get_history(athlete: str, only_included: bool = True) -> list[dict]:
    """Análises do atleta. `only_included=True` (padrão) filtra as marcadas
    para não entrar nos laudos/estatísticas."""
    q = "SELECT * FROM analyses WHERE athlete = ?"
    if only_included:
        q += " AND COALESCE(incluir, 1) = 1"
    q += " ORDER BY created_at"
    with _conn() as c:
        rows = c.execute(q, (athlete,)).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["tem_percurso"] = d.pop("traj_blob", None) is not None
        d["incluida"] = (d.get("incluir") is None) or bool(d.get("incluir"))
        out.append(d)
    return out


def set_analysis_included(analysis_id: int, included: bool) -> None:
    with _conn() as c:
        c.execute("UPDATE analyses SET incluir = ? WHERE id = ?",
                  (1 if included else 0, analysis_id))
    _sync()


def get_analysis(analysis_id: int) -> dict | None:
    """Uma análise completa, com golpe/plano/biomecânica já decodificados."""
    with _conn() as c:
        row = c.execute("SELECT * FROM analyses WHERE id = ?",
                        (analysis_id,)).fetchone()
    if not row:
        return None
    d = dict(row)
    d["tem_percurso"] = d.pop("traj_blob", None) is not None
    for campo in ("stroke", "intel", "biomech"):
        try:
            d[campo] = json.loads(d[campo]) if d.get(campo) else None
        except (ValueError, TypeError):
            d[campo] = None
    return d


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
