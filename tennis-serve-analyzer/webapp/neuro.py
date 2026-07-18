"""NeuroFES — motor de decisão clínica para eletroterapia na recuperação motora.

Foco: recuperação da função motora do MEMBRO SUPERIOR (e princípios extensíveis
ao inferior) em pacientes com PARESIA/PLEGIA após AVC ou lesão do neurônio motor
superior. A partir da avaliação do paciente, o sistema:

  1. Faz a TRIAGEM DE SEGURANÇA (contraindicações absolutas e relativas);
  2. RANQUEIA as modalidades de eletroterapia pela melhor evidência atual;
  3. SELECIONA e monta o PROTOCOLO APLICÁVEL completo (parâmetros, eletrodos,
     passo a passo, dosagem, músculos-alvo);
  4. Define as ESCALAS DE REAVALIAÇÃO objetivas e o cronograma.

Base de evidência (resumo):
  - Network meta-analysis de estimulação elétrica no MS pós-AVC (Tang et al.,
    2021; 34 RCTs, ~2.383 pacientes): FES 1º para função motora (FMA-UE) e
    independência (Barthel/MBI); TEAS 1º para espasticidade (MAS).
  - Diretrizes internacionais recomendam FES dos extensores de punho/dedos como
    complemento à terapia, sincronizada com a tentativa ativa e a tarefa.
  - FES + treino robótico > robô isolado (ganho FMA-UE ~15,6 vs 9,3).
  - EMG-triggered FES e CCFES: opções avançadas promissoras, dependentes de
    contração voluntária mínima / mão contralateral funcional.
  - NMES cíclica: útil na fase grave/preparatória; deve evoluir para tarefa.
  - TENS: dor de ombro e modulação sensorial — NÃO recupera movimento.

IMPORTANTE — natureza do sistema: ferramenta de APOIO À DECISÃO clínica e de
padronização de protocolos. NÃO é dispositivo médico e NÃO substitui a avaliação
e a supervisão de fisioterapeuta/profissional habilitado. Toda aplicação em
paciente neurológico deve ser conduzida ou supervisionada presencialmente.

Este módulo é 100% determinístico e sem dependências pesadas (só Python padrão),
para rodar em qualquer plano/ambiente.
"""

from __future__ import annotations

VERSAO = "NeuroFES v1.0 · 2026"

# ---------------------------------------------------------------------------
# 1. EIXOS DA AVALIAÇÃO CLÍNICA (entrada do sistema)
# ---------------------------------------------------------------------------
# Cada campo tem opções com um "peso" clínico que o motor usa para ranquear.

AVALIACAO = {
    "movimento": {
        "rotulo": "Movimento voluntário do músculo-alvo",
        "ajuda": "Quanta contração/extensão ativa o paciente consegue produzir hoje.",
        "opcoes": [
            ("ausente", "Ausente — nenhuma contração perceptível"),
            ("minima", "Mínima — contração detectável, sem movimento funcional"),
            ("parcial", "Parcial — inicia o movimento, amplitude insuficiente"),
            ("moderada", "Moderada — move, mas com pouca destreza/controle"),
        ],
    },
    "objetivo": {
        "rotulo": "Objetivo funcional principal",
        "ajuda": "O que se quer recuperar prioritariamente nesta fase.",
        "opcoes": [
            ("abrir_mao", "Abrir a mão / estender punho e dedos"),
            ("alcance", "Alcançar, pegar e soltar objetos"),
            ("destreza", "Destreza fina (pinça, manipulação)"),
            ("ombro", "Ombro subluxado / doloroso / hipotônico"),
            ("manutencao", "Evitar desuso / manter amplitude (fase grave)"),
        ],
    },
    "contralateral": {
        "rotulo": "Mão contralateral (não afetada)",
        "ajuda": "Necessária para a modalidade CCFES (controle pelo lado saudável).",
        "opcoes": [
            ("funcional", "Funcional — abre/fecha normalmente"),
            ("limitada", "Limitada / também comprometida"),
        ],
    },
    "cognicao": {
        "rotulo": "Cognição e participação na tarefa",
        "ajuda": "Capacidade de compreender comandos e cooperar com o treino.",
        "opcoes": [
            ("boa", "Boa — compreende e coopera"),
            ("reduzida", "Reduzida — dificuldade de compreender/cooperar"),
        ],
    },
    "espasticidade": {
        "rotulo": "Espasticidade nos flexores (MAS)",
        "ajuda": "Tônus aumentado que dificulta abertura da mão/extensão.",
        "opcoes": [
            ("nenhuma", "Ausente ou leve"),
            ("relevante", "Relevante — atrapalha a função"),
        ],
    },
    "dor_ombro": {
        "rotulo": "Dor no ombro",
        "ajuda": "Dor que limita a participação no treino.",
        "opcoes": [
            ("nao", "Sem dor significativa"),
            ("sim", "Dor de ombro relevante"),
        ],
    },
    "responde_estim": {
        "rotulo": "O músculo responde à estimulação (teste)",
        "ajuda": "Ao testar, houve contração visível com a eletroestimulação?",
        "opcoes": [
            ("sim", "Sim — contração visível ao estímulo"),
            ("nao_testado", "Ainda não testado"),
            ("nao", "Não respondeu ao estímulo"),
        ],
    },
    "equipamento": {
        "rotulo": "Recursos do equipamento disponível",
        "ajuda": "Define quais modalidades avançadas são viáveis.",
        "multiplo": True,
        "opcoes": [
            ("fes_multicanal", "FES multicanal com rampas e gatilho manual"),
            ("emg", "Biofeedback/EMG-triggered"),
            ("ccfes", "CCFES (controle pelo lado contralateral)"),
            ("basico", "Apenas NMES/TENS básico"),
        ],
    },
}

# ---------------------------------------------------------------------------
# 2. TRIAGEM DE SEGURANÇA — contraindicações
# ---------------------------------------------------------------------------
# absolutas: bloqueiam a estimulação naquela região / exigem liberação médica.
# relativas: exigem cautela, ajuste ou supervisão reforçada.

CONTRAINDICACOES_ABSOLUTAS = [
    ("implante", "Dispositivo eletrônico implantado (marca-passo/DAI/estimulador), "
                 "sobretudo próximo à região a estimular"),
    ("torax", "Estimulação através do tórax ou sobre a região anterior do pescoço "
              "(seio carotídeo)"),
    ("trombose", "Trombose venosa suspeita ou confirmada na região"),
    ("neoplasia", "Neoplasia ativa na área de aplicação"),
    ("gestante_abdome", "Gestação — evitar tronco/abdome/pelve"),
    ("lesao_pele", "Infecção, ferida aberta ou lesão cutânea no local dos eletrodos"),
]

CONTRAINDICACOES_RELATIVAS = [
    ("arritmia", "Arritmia clinicamente importante — liberação médica"),
    ("epilepsia", "Epilepsia — cautela em aplicações próximas à cabeça/pescoço"),
    ("sensibilidade", "Sensibilidade gravemente reduzida — monitorar pele e dose"),
    ("comunicacao", "Incapacidade de comunicar desconforto — supervisão contínua"),
    ("fratura", "Fratura instável na região — estabilizar antes"),
    ("dor_nao_investigada", "Dor não investigada — esclarecer a causa antes"),
]

# Sinais para INTERROMPER a sessão imediatamente.
SINAIS_PARADA = [
    "Dor ou queimação",
    "Alteração persistente da pele (vermelhidão que não cede, bolha)",
    "Aumento importante do espasmo / piora do padrão motor",
    "Fadiga excessiva ou perda de qualidade do movimento",
    "Dor no ombro ou impacto subacromial",
    "Resposta autonômica anormal (sudorese, mal-estar, alteração de PA/FC)",
]

# ---------------------------------------------------------------------------
# 3. MODALIDADES — parâmetros base (individualizáveis)
# ---------------------------------------------------------------------------

MODALIDADES = {
    "fes_tarefa": {
        "nome": "FES sincronizada com a tarefa",
        "sigla": "FES",
        "icone": "⚡",
        "evidencia": "1ª escolha para recuperação motora (NMA: 1º em FMA-UE e Barthel).",
        "mecanismo": (
            "Estimula os motoneurônios para produzir contração funcional NO MOMENTO "
            "em que o paciente TENTA o movimento e executa uma tarefa real. O "
            "acoplamento temporal entre intenção, contração, visão e propriocepção "
            "dirige a neuroplasticidade."
        ),
        "params": {
            "Forma de onda": "Pulsada bifásica simétrica ou assimétrica balanceada",
            "Frequência": "30–40 Hz (tetânica funcional; até 50 Hz)",
            "Largura de pulso": "200–350 μs (até 400 μs)",
            "Intensidade": "A suficiente para movimento visível, funcional e confortável",
            "Rampa de subida": "0,5–2 s (evita contração abrupta)",
            "Rampa de descida": "0,5–2 s",
            "Tempo ligado (ON)": "5–10 s",
            "Tempo desligado (OFF)": "10–30 s (início); reduzir conforme tolerância",
            "Sessão": "20–45 min",
            "Frequência semanal": "3–5× (até diário)",
            "Programa": "4–8 semanas, com reavaliação a cada 2–4 semanas",
        },
    },
    "emg_triggered": {
        "nome": "FES/NMES acionada por EMG (EMG-triggered)",
        "sigla": "EMG-FES",
        "icone": "🎯",
        "evidencia": "Opção avançada — reforça o vínculo tentativa→resposta muscular.",
        "mecanismo": (
            "O aparelho detecta a atividade elétrica voluntária; ao atingir um "
            "limiar de esforço, completa o movimento com a estimulação. Exige "
            "iniciativa do paciente — conceitualmente superior à estimulação passiva."
        ),
        "params": {
            "Detecção": "Eletrodos de EMG nos extensores; registrar tentativas máximas",
            "Limiar de disparo": "Abaixo do melhor valor confortável obtido",
            "Frequência de estímulo": "30–40 Hz",
            "Largura de pulso": "200–350 μs",
            "Séries": "3–5 séries de 8–15 tentativas",
            "Sessão": "20–40 min",
            "Frequência semanal": "3–5×",
            "Reajuste": "Elevar o limiar conforme a resposta melhora",
        },
    },
    "ccfes": {
        "nome": "CCFES — estimulação controlada pelo lado não afetado",
        "sigla": "CCFES",
        "icone": "🤝",
        "evidencia": "Promissora para destreza da mão; exige mão contralateral funcional.",
        "mecanismo": (
            "O movimento da mão saudável controla PROPORCIONALMENTE a estimulação da "
            "mão parética (ex.: abrir a mão direita estimula a abertura da esquerda). "
            "Une intenção bilateral e feedback proporcional."
        ),
        "params": {
            "Controle": "Sensor/luva no lado saudável modula a intensidade em tempo real",
            "Frequência": "30–40 Hz",
            "Largura de pulso": "200–350 μs",
            "Foco": "Abertura da mão (extensores) e treino bilateral simétrico",
            "Sessão": "20–40 min",
            "Frequência semanal": "3–5×",
        },
    },
    "nmes_ciclica": {
        "nome": "NMES cíclica (preparatória)",
        "sigla": "NMES",
        "icone": "🔁",
        "evidencia": "Útil na fase grave/preparação; menor transferência funcional isolada.",
        "mecanismo": (
            "Contrai e relaxa o músculo em ciclos predeterminados, independente da "
            "tentativa. Preserva recrutamento, reduz desuso e mantém amplitude — "
            "ponte para o treino funcional."
        ),
        "params": {
            "Forma de onda": "Pulsada bifásica",
            "Frequência": "20–40 Hz",
            "Largura de pulso": "200–350 μs (até 500)",
            "Tempo ON/OFF": "10 s ON / 10–30 s OFF",
            "Intensidade": "Contração visível e sustentada, confortável",
            "Sessão": "20–30 min",
            "Frequência semanal": "5×",
            "Associar": "Imaginação/tentativa mental + terapia do espelho durante o ON",
        },
    },
    "nmes_ombro": {
        "nome": "NMES do ombro (subluxação/hipotonia)",
        "sigla": "NMES-ombro",
        "icone": "💪",
        "evidencia": "Opção reconhecida para dor/alinhamento do ombro pós-AVC.",
        "mecanismo": (
            "Ativa supraespinal e deltoide posterior/médio para melhorar o "
            "alinhamento glenoumeral e a ativação muscular nas fases de hipotonia."
        ),
        "params": {
            "Alvo": "Supraespinal + deltoide posterior (e médio conforme padrão)",
            "Frequência": "25–35 Hz",
            "Largura de pulso": "200–350 μs",
            "Intensidade": "Contração firme com alinhamento, SEM elevação dolorosa",
            "Ciclos": "ON/OFF com descanso suficiente (ex.: 10 s / 20–30 s)",
            "Sessão": "20–30 min",
            "Cuidado": "Nunca estimular em elevação forçada nem provocar impacto subacromial",
        },
    },
    "teas": {
        "nome": "TEAS — estimulação em acupontos (antiespástica)",
        "sigla": "TEAS",
        "icone": "🧩",
        "evidencia": "1ª para espasticidade (NMA: 1º em MAS). Complementar à FES.",
        "mecanismo": (
            "TENS aplicado em acupontos; modula a excitabilidade do motoneurônio por "
            "aferências sensoriais e favorece inibição (GABA/serotonina)."
        ),
        "params": {
            "Frequência": "Densa-dispersa 2/100 Hz (alternada)",
            "Largura de pulso": "100–300 μs (~200)",
            "Intensidade": "Forte e confortável, ABAIXO do limiar motor",
            "Acupontos (MS)": "LI4 (Hegu), LI10, LI11 (Quchi), SJ5/TE5 (Waiguan)",
            "Sessão": "20–30 min",
            "Frequência semanal": "5× (pode ser 1–2×/dia após treino do cuidador)",
            "Programa": "4–6 semanas; reavaliar MAS semanalmente",
        },
    },
    "tens": {
        "nome": "TENS sensorial (dor/coadjuvante)",
        "sigla": "TENS",
        "icone": "🩹",
        "evidencia": "Para dor de ombro e modulação sensorial — NÃO recupera movimento.",
        "mecanismo": (
            "Ativa preferencialmente fibras sensoriais (Aβ) e modula a dor pela "
            "teoria das comportas. Efeito motor mínimo."
        ),
        "params": {
            "Frequência (convencional)": "80–100 Hz para dor",
            "Largura de pulso": "50–100 μs (convencional)",
            "Intensidade": "Parestesia forte e confortável, SEM contração",
            "Sessão": "20–60 min (antes/durante a fisioterapia)",
            "Local": "Ao redor do ombro / trajeto nervoso (abordagem dermatomal)",
        },
    },
}

# ---------------------------------------------------------------------------
# 4. PROTOCOLOS APLICÁVEIS (passo a passo pericial)
# ---------------------------------------------------------------------------

PROTOCOLOS = {
    "p1_mao": {
        "titulo": "Protocolo 1 — Abertura da mão e extensão do punho",
        "modalidade": "fes_tarefa",
        "indicacao": [
            "Mão fechada por fraqueza dos extensores",
            "Dificuldade para soltar objetos; punho em flexão",
            "Início de extensão ativa, ainda insuficiente",
        ],
        "musculos": [
            "Extensor comum dos dedos",
            "Extensores radial longo e curto do carpo",
            "Extensor ulnar do carpo (quando necessário)",
            "Extensor do polegar (conforme a tarefa)",
        ],
        "posicionamento": [
            "Paciente sentado, tronco alinhado; ombro apoiado, sem tração no membro",
            "Cotovelo apoiado sobre a mesa; antebraço neutro ou levemente pronado",
            "Punho inicialmente próximo da posição neutra",
        ],
        "eletrodos": [
            "Localize o ponto motor dos extensores no dorso/posterolateral do antebraço",
            "1 eletrodo sobre a massa muscular proximal",
            "2º eletrodo mais distal — ajuste até obter extensão de punho E dedos",
            "Evite extensão excessiva do punho sem abertura dos dedos",
            "Reposicione até o padrão mais funcional possível",
        ],
        "passos": [
            "Peça ao paciente para olhar para a mão",
            "Comando: “Abra a mão e levante o punho”",
            "O paciente inicia a tentativa",
            "Ative a FES simultaneamente",
            "Durante a contração, o paciente abre a mão",
            "Na fase sem corrente, peça relaxamento controlado",
            "Após adaptação, introduza um objeto",
            "Estimule a abertura para aproximar a mão do objeto",
            "Reduza a estimulação para permitir a preensão",
            "Estimule novamente para soltar o objeto",
        ],
        "dosagem": [
            "10–15 repetições sem objeto",
            "Depois, 20–40 repetições funcionais",
            "Intervalos ao surgir fadiga ou perda de qualidade",
        ],
    },
    "p2_alcance": {
        "titulo": "Protocolo 2 — Alcance, preensão e soltura",
        "modalidade": "fes_tarefa",
        "indicacao": [
            "Paciente inicia o alcance, mas coordena mal ombro/cotovelo/punho/dedos",
        ],
        "musculos": [
            "Tríceps braquial (extensão de cotovelo, para o alcance)",
            "Extensores de punho e dedos (abertura/soltura)",
        ],
        "posicionamento": [
            "Sentado, MS apoiado, objeto-alvo sobre a mesa (copo leve ou cone)",
        ],
        "eletrodos": [
            "Canal 1: tríceps (cabeça longa) — extensão de cotovelo",
            "Canal 2: extensores de punho/dedos — abertura da mão",
            "Eletrodos retangulares sobre os ventres musculares",
        ],
        "passos": [
            "Solicite alcance com extensão do cotovelo",
            "FES nos extensores de punho/dedos durante a aproximação",
            "Ao chegar ao objeto, reduza a estimulação gradualmente",
            "Peça preensão ativa",
            "Oriente o deslocamento do objeto",
            "No momento de soltar, ative novamente os extensores",
            "Repita em diferentes direções e distâncias",
        ],
        "dosagem": [
            "Progressão: objeto grande e leve → menor → mudança de altura",
            "Preensão lateral → cilíndrica → objetos de uso diário",
            "Tarefas de alimentação, higiene e vestuário",
            "Priorize QUALIDADE antes de velocidade",
        ],
    },
    "p3_emg": {
        "titulo": "Protocolo 3 — Estimulação acionada por EMG",
        "modalidade": "emg_triggered",
        "indicacao": [
            "Há atividade voluntária detectável nos extensores, sem amplitude funcional",
        ],
        "musculos": ["Extensores de punho e dedos"],
        "posicionamento": [
            "Sentado, antebraço apoiado, pele limpa e íntegra",
        ],
        "eletrodos": [
            "Posicione os eletrodos de detecção/estimulação sobre os extensores",
        ],
        "passos": [
            "Registre algumas tentativas máximas confortáveis",
            "Configure o limiar de disparo abaixo do melhor valor obtido",
            "Solicite extensão ativa do punho e dedos",
            "Ao atingir o limiar, o aparelho completa o movimento",
            "O paciente CONTINUA tentando durante toda a estimulação",
            "Realize 3–5 séries de 8–15 tentativas",
            "Reajuste o limiar conforme a resposta melhora",
            "Integre progressivamente objetos e tarefas",
        ],
        "dosagem": [
            "Limiar nem tão baixo (dispara sem esforço) nem tão alto (falha repetida)",
        ],
    },
    "p4_ombro": {
        "titulo": "Protocolo 4 — Ombro subluxado ou doloroso",
        "modalidade": "nmes_ombro",
        "indicacao": [
            "Subluxação glenoumeral; hipotonia inicial; ombro doloroso",
        ],
        "musculos": [
            "Deltoide posterior",
            "Deltoide médio (conforme o padrão)",
            "Supraespinal",
        ],
        "posicionamento": [
            "Braço adequadamente apoiado; avaliar subluxação, dor, sensibilidade e ADM",
        ],
        "eletrodos": [
            "Localize os pontos motores do supraespinal e do deltoide posterior",
        ],
        "passos": [
            "Frequência inicial 25–35 Hz; largura ~200–350 μs",
            "Aumente a intensidade até contração firme e ALINHAMENTO",
            "Sem elevação dolorosa do ombro",
            "Ciclos com descanso suficiente",
            "Associe posicionamento, alcance assistido e treino de escápula",
            "Reavalie dor e alinhamento após a sessão",
        ],
        "dosagem": [
            "Sessões de 20–30 min; progredir para integração funcional",
            "NÃO estimular em elevação forçada nem gerar impacto subacromial",
        ],
    },
    "p5_grave": {
        "titulo": "Protocolo 5 — Sem movimento voluntário detectável",
        "modalidade": "nmes_ciclica",
        "indicacao": [
            "Ausência de contração voluntária — fase grave/preparatória",
        ],
        "musculos": ["Extensores de punho e dedos (alvo funcional prioritário)"],
        "posicionamento": [
            "Membro corretamente posicionado; proteção articular; prevenção de contraturas",
        ],
        "eletrodos": [
            "Sobre o ventre dos extensores / ponto motor",
        ],
        "passos": [
            "Avalie se o músculo responde à estimulação",
            "NMES cíclica para produzir extensão de punho e dedos",
            "A cada estímulo, peça que o paciente IMAGINE e TENTE o movimento",
            "Acrescente observação da mão, terapia do espelho ou prática mental",
            "Evite deixar o paciente apenas assistindo passivamente",
            "Teste periodicamente se surgiu atividade voluntária",
            "Ao surgir contração, progrida para FES na tarefa ou EMG-triggered",
        ],
        "dosagem": [
            "Atenção à proteção articular, posicionamento e prevenção de dor/contraturas",
        ],
    },
    "p6_teas": {
        "titulo": "Protocolo 6 — TEAS antiespástico (complementar)",
        "modalidade": "teas",
        "indicacao": [
            "Espasticidade de flexores que atrapalha abertura da mão/função",
        ],
        "musculos": ["Acupontos do MS: LI4, LI10, LI11, SJ5/TE5"],
        "posicionamento": [
            "Sentado, pele limpa nos pontos selecionados",
        ],
        "eletrodos": [
            "Eletrodos pequenos (2–3 cm) sobre os acupontos identificados por palpação",
        ],
        "passos": [
            "Frequência densa-dispersa 2/100 Hz; largura ~200 μs",
            "Intensidade forte e confortável, ABAIXO do limiar motor",
            "20–30 min; aumentar a intensidade lentamente",
            "Aplicar antes/junto ao treino funcional (não substitui a FES)",
        ],
        "dosagem": [
            "5×/semana; reavaliar MAS semanalmente e ajustar",
        ],
    },
}

# ---------------------------------------------------------------------------
# 5. ESCALAS DE REAVALIAÇÃO OBJETIVA
# ---------------------------------------------------------------------------

ESCALAS = [
    ("FMA-UE", "Fugl-Meyer de membro superior — comprometimento motor (0–66)"),
    ("ARAT", "Action Research Arm Test — capacidade de alcance/preensão/pinça"),
    ("Box and Block", "Destreza grosseira da mão (blocos/min)"),
    ("Força", "Força muscular dos alvos (MRC/dinamometria)"),
    ("ADM", "Amplitude ativa e passiva"),
    ("MAS", "Ashworth modificada — espasticidade"),
    ("EVA", "Dor (0–10)"),
    ("Subluxação", "Palpação/imagem do espaço acromio-umeral"),
    ("Sensibilidade", "Tátil, proprioceptiva"),
    ("Repetições funcionais", "Nº de repetições de qualidade por sessão"),
    ("Uso espontâneo", "Uso do braço nas atividades diárias (autorrelato/observação)"),
]

CRONOGRAMA_REAVALIACAO = "Registrar antes de iniciar e a cada 2–4 semanas."

# Escalas NUMÉRICAS acompanhadas na curva de evolução.
# chave -> (rótulo, min, max, direção)  direção: "up" = maior é melhor.
ESCALAS_NUM = {
    "fma_ue": ("FMA-UE", 0, 66, "up", "Comprometimento motor do MS (0–66)"),
    "arat": ("ARAT", 0, 57, "up", "Alcance / preensão / pinça (0–57)"),
    "bbt": ("Box and Block", 0, 150, "up", "Destreza grosseira (blocos/min)"),
    "mas": ("MAS", 0, 4, "down", "Espasticidade — Ashworth modificada (0–4)"),
    "eva": ("EVA", 0, 10, "down", "Dor (0–10)"),
    "reps": ("Repetições", 0, 500, "up", "Repetições funcionais de qualidade"),
}

# Diferença mínima clinicamente relevante (aprox., para leitura de tendência).
_MCID = {"fma_ue": 4.0, "arat": 5.5, "bbt": 5.5, "mas": 1.0, "eva": 2.0, "reps": 5.0}


# ---------------------------------------------------------------------------
# 7. PROGRESSÃO AUTOMÁTICA (marcador evolutivo)
# ---------------------------------------------------------------------------

_NIVEL_MOV = {"ausente": 0, "minima": 1, "parcial": 2, "moderada": 3}


def modalidade_recomendada(av):
    """Topo do ranking para uma avaliação — a modalidade indicada naquele estado."""
    r = _ranquear(av)
    return r[0]["chave"] if r else "fes_tarefa"


def _tendencia_escala(chave, valores):
    """valores: lista ordenada (mais antigo -> mais novo) de floats/None.
    Retorna (tendencia, delta) comparando o 1º e o último válidos."""
    pts = [v for v in valores if v is not None]
    if len(pts) < 2:
        return ("insuficiente", None)
    _rot, _mn, _mx, direcao, _d = ESCALAS_NUM[chave]
    delta = pts[-1] - pts[0]
    mcid = _MCID.get(chave, 0.0)
    ganho = delta if direcao == "up" else -delta  # positivo = melhora clínica
    if ganho >= mcid:
        return ("melhora", delta)
    if ganho <= -mcid:
        return ("piora", delta)
    return ("plateau", delta)


def progressao(sessoes):
    """Analisa o histórico longitudinal e recomenda o próximo passo.

    sessoes: lista de dicts ordenada (mais antiga -> mais nova), cada uma com:
        - "av": dict da avaliação daquela sessão
        - "modalidade": chave da modalidade aplicada
        - "escalas": dict {chave_num: valor|None}
    Retorna dict com tendência global, deltas por escala, mudança de nível
    motor e a modalidade recomendada para a próxima fase.
    """
    if not sessoes:
        return {"status": "sem_dados"}

    primeira, ultima = sessoes[0], sessoes[-1]

    # tendência por escala
    escalas_tend = {}
    for chave in ESCALAS_NUM:
        serie = [s.get("escalas", {}).get(chave) for s in sessoes]
        tend, delta = _tendencia_escala(chave, serie)
        if tend != "insuficiente":
            rot = ESCALAS_NUM[chave][0]
            escalas_tend[chave] = {"rotulo": rot, "tendencia": tend, "delta": delta}

    # nível de movimento
    nv0 = _NIVEL_MOV.get(primeira.get("av", {}).get("movimento"), None)
    nv1 = _NIVEL_MOV.get(ultima.get("av", {}).get("movimento"), None)
    subiu_nivel = (nv0 is not None and nv1 is not None and nv1 > nv0)
    caiu_nivel = (nv0 is not None and nv1 is not None and nv1 < nv0)

    # síntese da tendência global (voto das escalas + nível motor)
    votos = [t["tendencia"] for t in escalas_tend.values()]
    n_mel = votos.count("melhora")
    n_pio = votos.count("piora")
    if subiu_nivel:
        n_mel += 1
    if caiu_nivel:
        n_pio += 1
    if n_mel and n_mel >= n_pio + 1:
        global_tend = "melhora"
    elif n_pio and n_pio >= n_mel + 1:
        global_tend = "piora"
    elif votos or subiu_nivel or caiu_nivel:
        global_tend = "plateau"
    else:
        global_tend = "insuficiente"

    # modalidade indicada agora vs. a que vinha sendo aplicada
    mod_atual = ultima.get("modalidade")
    mod_reco = modalidade_recomendada(ultima.get("av", {}))
    avancar = (mod_atual is not None and mod_reco != mod_atual)

    mensagens = []
    if subiu_nivel:
        mensagens.append(
            "⬆️ Ganho de movimento voluntário desde a 1ª sessão "
            f"({primeira['av'].get('movimento')} → {ultima['av'].get('movimento')}). "
            "Progrida para a modalidade que exige mais participação ativa."
        )
    if caiu_nivel:
        mensagens.append(
            "⚠️ Redução do movimento voluntário registrado — revise fadiga, dor, "
            "tônus e a adesão antes de progredir."
        )
    for chave, t in escalas_tend.items():
        seta = {"melhora": "✅", "piora": "🔻", "plateau": "➖"}[t["tendencia"]]
        sinal = f"{t['delta']:+.1f}" if t["delta"] is not None else "—"
        mensagens.append(f"{seta} {t['rotulo']}: {t['tendencia']} ({sinal}).")

    if global_tend == "melhora":
        conduta = ("Manter e progredir: aumentar a dificuldade da tarefa, o número "
                   "de repetições funcionais e reduzir o tempo OFF conforme tolerância.")
    elif global_tend == "piora":
        conduta = ("Reavaliar o plano: checar dor, espasticidade, fadiga, "
                   "posicionamento e parâmetros; considerar recuar de intensidade "
                   "e reforçar segurança antes de progredir.")
    elif global_tend == "plateau":
        conduta = ("Platô: variar o estímulo — mudar tarefa, migrar para modalidade "
                   "com mais participação ativa (EMG-triggered/FES na tarefa), "
                   "aumentar dose ou associar TEAS/terapia do espelho.")
    else:
        conduta = ("Ainda sem reavaliações suficientes para tendência — registre "
                   "FMA-UE/ARAT/MAS em pelo menos duas sessões.")

    return {
        "status": "ok",
        "n_sessoes": len(sessoes),
        "tendencia": global_tend,
        "escalas": escalas_tend,
        "subiu_nivel": subiu_nivel,
        "caiu_nivel": caiu_nivel,
        "modalidade_atual": mod_atual,
        "modalidade_recomendada": mod_reco,
        "avancar": avancar,
        "mensagens": mensagens,
        "conduta": conduta,
        "mod_atual_info": MODALIDADES.get(mod_atual),
        "mod_reco_info": MODALIDADES.get(mod_reco),
    }


# ---------------------------------------------------------------------------
# 6. MOTOR DE DECISÃO
# ---------------------------------------------------------------------------

def _get(av, chave, default=None):
    v = av.get(chave, default)
    return v


def triagem_seguranca(flags):
    """Recebe a lista de contraindicações marcadas e devolve o veredito.

    flags: iterable de chaves marcadas (absolutas e/ou relativas).
    """
    flags = set(flags or [])
    absolutas = [(k, txt) for (k, txt) in CONTRAINDICACOES_ABSOLUTAS if k in flags]
    relativas = [(k, txt) for (k, txt) in CONTRAINDICACOES_RELATIVAS if k in flags]
    if absolutas:
        nivel = "bloqueado"
    elif relativas:
        nivel = "cautela"
    else:
        nivel = "liberado"
    return {
        "nivel": nivel,
        "absolutas": absolutas,
        "relativas": relativas,
        "sinais_parada": SINAIS_PARADA,
    }


def _ranquear(av):
    """Retorna lista ordenada de (chave_modalidade, score, motivo)."""
    mov = _get(av, "movimento", "ausente")
    obj = _get(av, "objetivo", "abrir_mao")
    contra = _get(av, "contralateral", "limitada")
    cog = _get(av, "cognicao", "boa")
    esp = _get(av, "espasticidade", "nenhuma")
    dor = _get(av, "dor_ombro", "nao")
    equip = set(_get(av, "equipamento", []) or [])

    scores = {k: 0.0 for k in MODALIDADES}
    motivos = {k: [] for k in MODALIDADES}

    def add(k, pts, motivo):
        scores[k] += pts
        if motivo:
            motivos[k].append(motivo)

    # --- FES na tarefa: âncora quando há alguma intenção/contração e cognição ok
    if mov in ("minima", "parcial", "moderada"):
        add("fes_tarefa", 5, "FES é 1ª escolha quando há tentativa ativa (NMA: 1º em função).")
    if cog == "boa":
        add("fes_tarefa", 2, "Boa cognição favorece o treino sincronizado com a tarefa.")
    else:
        add("fes_tarefa", -1, "Cognição reduzida limita a sincronização voluntária.")
    if obj in ("abrir_mao", "alcance", "destreza"):
        add("fes_tarefa", 2, "Objetivo motor de mão/alcance é o alvo clássico da FES.")
    if obj == "ombro":
        add("fes_tarefa", -3, "Para o ombro subluxado/hipotônico, o alvo é o protocolo de ombro.")
    if obj == "manutencao":
        add("fes_tarefa", -3, "Fase de manutenção prioriza a NMES preparatória.")

    # --- EMG-triggered: contração mínima + equipamento + cognição
    if mov in ("minima", "parcial"):
        add("emg_triggered", 4, "Contração mínima detectável é a indicação típica do EMG-triggered.")
    if "emg" in equip:
        add("emg_triggered", 3, "Equipamento com EMG disponível.")
    else:
        add("emg_triggered", -4, "Sem hardware de EMG no equipamento informado.")
    if cog == "boa":
        add("emg_triggered", 1, "Exige iniciativa/compreensão do paciente.")
    else:
        add("emg_triggered", -2, "Cognição reduzida dificulta atingir o limiar voluntário.")

    # --- CCFES: mão contralateral funcional + equipamento + destreza
    if contra == "funcional":
        add("ccfes", 3, "Mão contralateral funcional habilita o controle proporcional.")
    else:
        add("ccfes", -5, "Mão contralateral não funcional inviabiliza a CCFES.")
    if "ccfes" in equip:
        add("ccfes", 3, "Equipamento CCFES disponível.")
    else:
        add("ccfes", -4, "Sem hardware CCFES no equipamento informado.")
    if obj in ("destreza", "abrir_mao") and mov in ("parcial", "moderada"):
        add("ccfes", 2, "Bom para destreza/abertura com algum movimento presente.")
    if cog == "reduzida":
        add("ccfes", -2, "Treino bilateral exige boa cognição.")

    # --- NMES cíclica: fase grave / sem movimento / manutenção
    if mov == "ausente":
        add("nmes_ciclica", 5, "Sem movimento voluntário: NMES cíclica é a ponte inicial.")
    if obj == "manutencao":
        add("nmes_ciclica", 4, "Objetivo de evitar desuso/manter amplitude.")
    if mov in ("parcial", "moderada"):
        add("nmes_ciclica", -2, "Havendo movimento, priorizar estímulo sincronizado com a tarefa.")

    # --- NMES ombro: objetivo ombro
    if obj == "ombro":
        add("nmes_ombro", 6, "Objetivo é ombro subluxado/hipotônico.")
    if dor == "sim":
        add("nmes_ombro", 1, "NMES é opção reconhecida para dor de ombro pós-AVC.")

    # --- TEAS: espasticidade relevante (complementar)
    if esp == "relevante":
        add("teas", 5, "Espasticidade relevante: TEAS é 1º em MAS (complementar à FES).")
    else:
        add("teas", -3, "Sem espasticidade relevante, TEAS não é prioridade.")

    # --- TENS: dor de ombro (coadjuvante, não recupera movimento)
    if dor == "sim":
        add("tens", 4, "Dor de ombro: TENS como coadjuvante analgésico pré-sessão.")
    else:
        add("tens", -4, "Sem dor, TENS não é indicado para recuperação motora.")

    ordenado = sorted(
        MODALIDADES.keys(), key=lambda k: scores[k], reverse=True
    )
    resultado = []
    for k in ordenado:
        if scores[k] <= 0 and k not in ("fes_tarefa",):
            continue
        resultado.append({
            "chave": k,
            "score": round(scores[k], 1),
            "motivos": motivos[k],
            **MODALIDADES[k],
        })
    return resultado


def _protocolos_para(chave_modalidade, av):
    """Protocolos aplicáveis para a modalidade escolhida, dado o objetivo."""
    obj = _get(av, "objetivo", "abrir_mao")
    lista = [pk for pk, p in PROTOCOLOS.items() if p["modalidade"] == chave_modalidade]
    # priorização por objetivo dentro da FES
    prio = []
    if obj == "abrir_mao":
        prio = ["p1_mao", "p2_alcance"]
    elif obj == "alcance":
        prio = ["p2_alcance", "p1_mao"]
    elif obj == "destreza":
        prio = ["p2_alcance", "p1_mao"]
    lista.sort(key=lambda pk: (prio.index(pk) if pk in prio else 99))
    return lista


def prescrever(av, flags_contra=None):
    """Função principal: gera a prescrição completa a partir da avaliação.

    Retorna um dicionário pronto para o template.
    """
    seguranca = triagem_seguranca(flags_contra)
    ranking = _ranquear(av)

    principal = ranking[0] if ranking else None
    # complementos: sempre sugerir TEAS se espasticidade e TENS se dor,
    # mesmo que não sejam a modalidade principal.
    complementos = []
    esp = _get(av, "espasticidade", "nenhuma")
    dor = _get(av, "dor_ombro", "nao")
    chaves_ranking = {r["chave"] for r in ranking}
    if esp == "relevante" and principal and principal["chave"] != "teas":
        complementos.append({**MODALIDADES["teas"], "chave": "teas",
                             "razao": "Controle da espasticidade em paralelo à FES."})
    if dor == "sim" and (not principal or principal["chave"] not in ("tens", "nmes_ombro")):
        complementos.append({**MODALIDADES["tens"], "chave": "tens",
                             "razao": "Analgesia do ombro antes/durante a sessão."})

    protocolos = []
    if principal:
        for pk in _protocolos_para(principal["chave"], av):
            protocolos.append({"chave": pk, **PROTOCOLOS[pk]})
    # se a modalidade principal não tem protocolo dedicado, cair no genérico da FES
    if not protocolos and principal:
        protocolos.append({"chave": "p1_mao", **PROTOCOLOS["p1_mao"]})

    # protocolos dos complementos
    protocolos_compl = []
    for c in complementos:
        for pk, p in PROTOCOLOS.items():
            if p["modalidade"] == c["chave"]:
                protocolos_compl.append({"chave": pk, **p})
                break

    return {
        "versao": VERSAO,
        "seguranca": seguranca,
        "ranking": ranking,
        "principal": principal,
        "complementos": complementos,
        "protocolos": protocolos,
        "protocolos_complementares": protocolos_compl,
        "escalas": ESCALAS,
        "cronograma": CRONOGRAMA_REAVALIACAO,
        "avaliacao": av,
    }
