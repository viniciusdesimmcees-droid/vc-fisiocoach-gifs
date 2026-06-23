# Medidor de Velocidade de Saque — Protótipo

Protótipo de visão computacional que mede a **velocidade da bola no saque de
tênis** a partir de um vídeo gravado com a câmera do celular, gera vídeo
anotado, gráfico de velocidade, CSV da trajetória e um resumo JSON pronto para
protocolar e entregar à equipe do atleta.

Faz parte do ecossistema **VC Fisiocoach** (análise técnica + acompanhamento
fisio/performance do atleta).

## Como funciona

```
vídeo  →  rastreio da bola  →  calibração px→m  →  velocidade  →  relatórios
          (cor + movimento)    (objeto ref.)      (janela de impacto)
```

1. **Rastreio** (`ball_tracker.py`): subtração de fundo (MOG2) + filtro de cor
   HSV (amarelo-esverdeado da bola) + detecção de blobs circulares, associados
   quadro-a-quadro por proximidade e consistência de tamanho.
2. **Calibração** (`calibration.py`): converte pixels em metros usando um
   objeto de referência de tamanho real conhecido no plano do saque.
3. **Velocidade** (`speed_estimator.py`): velocidade instantânea entre
   detecções; a velocidade do saque é a **maior mediana de uma janela
   deslizante sustentada** — robusta a picos isolados e artefatos.
4. **Relatórios** (`report.py`): vídeo anotado (esqueleto da trajetória +
   velocidade sobreposta), `*_velocidade.png`, `*_trajetoria.csv` e
   `*_resumo.json`.

## Dois detectores de bola (intercambiáveis)

O rastreio é dividido em **detector de candidatos** (por quadro) + **associação
temporal** (`tracking.py`). Há duas implementações com a mesma interface:

| Detector | Flag | Quando usar | Dependências |
|----------|------|-------------|--------------|
| Clássico (cor + movimento) | `--detector classic` (padrão) | Fundo controlado, sem GPU, zero setup | numpy, opencv |
| Deep learning (YOLOv8) | `--detector dl` | Quadra real, fundo poluído, robustez | + torch, ultralytics |

O detector DL usa a classe COCO 32 ("sports ball"), que os pesos pré-treinados
do YOLOv8 já reconhecem — **não exige treinar nada para começar**. Para máxima
robustez, faça fine-tuning com um dataset de bola de tênis e aponte `--model`
para esses pesos.

## Instalação

```bash
pip install -r requirements.txt        # núcleo (detector clássico)
pip install -r requirements-dl.txt     # opcional (detector DL: torch + YOLOv8)
```

## Uso

```bash
python src/analyze.py \
  --video saque.mp4 \
  --athlete "Nome do Atleta" \
  --ref-length-m 0.914 \      # comprimento REAL do objeto de referência (m)
  --ref-length-px 220 \       # quanto ele ocupa no quadro (pixels)
  --fps 240 \                 # fps REAL da captura (slow-motion!)
  --outdir output
```

Saídas em `output/`: `saque_anotado.mp4`, `saque_velocidade.png`,
`saque_trajetoria.csv`, `saque_resumo.json`.

Com o detector por deep learning:

```bash
python src/analyze.py --video saque.mp4 --athlete "Nome" \
  --detector dl --model yolov8m.pt --conf 0.05 \
  --ref-length-m 0.914 --ref-length-px 220 --fps 240
```

### Testar sem filmagem (vídeo sintético com velocidade conhecida)

```bash
# bola chapada (detector clássico)
python tools/generate_test_video.py --serve-kmh 180 --fps 240
python src/analyze.py --video output/saque_sintetico.mp4 \
  --ref-length-m 1.0 --ref-length-px 200 --fps 240

# bola sombreada/realista (detector DL)
python tools/generate_test_video.py --serve-kmh 180 --fps 240 \
  --realistic --ball-radius 22 --out output/saque_realista.mp4
python src/analyze.py --video output/saque_realista.mp4 \
  --detector dl --model yolov8m.pt --conf 0.05 \
  --ref-length-m 1.0 --ref-length-px 200 --fps 240
```

> O detector DL foi treinado em **fotos reais**; o círculo chapado do sintético
> não dispara. Por isso o gerador tem `--realistic`. Validação de precisão de
> verdade exige filmagem real.

## Precisão validada (vídeo sintético, ground truth conhecido)

| Velocidade real | fps | Medido      | Erro  |
|-----------------|-----|-------------|-------|
| 100 km/h        | 240 | 103,6 km/h  | 3,6%  |
| 120 km/h        | 240 | 123,4 km/h  | 2,8%  |
| 150 km/h        | 240 | 153,0 km/h  | 2,0%  |
| 180 km/h        | 240 | 182,7 km/h  | 1,5%  |
| 200 km/h        | 240 | 203,2 km/h  | 1,6%  |
| 220 km/h        | 240 | 224,2 km/h  | 1,9%  |

Erro de **0,7%–3,6%** em condições ideais (sem perspectiva, sem blur, escala
exata). No mundo real o erro será maior — ver limitações.

## Protocolo de captura (essencial para precisão)

Para a velocidade ser confiável, padronize a filmagem:

1. **Slow-motion 120 ou 240 fps.** A 30 fps a bola "pula" pixels demais e a
   medição vira chute. Confirme o fps real — alguns celulares gravam em 240 mas
   o arquivo reporta 30.
2. **Câmera fixa (tripé), lateral ao atleta**, no plano do saque.
3. **Objeto de referência** de tamanho conhecido no mesmo plano da bola
   (ex.: rede = 0,914 m no centro, um bastão de calibração, a fita de uma
   linha). Meça quantos pixels ele ocupa e passe em `--ref-length-px`.
4. **Boa iluminação** e fundo contrastante com a bola.

## Limitações (transparência técnica)

- **Velocidade absoluta da bola não é "radar Doppler".** A escala vale no plano
  da referência; se a bola sai muito desse plano há erro de perspectiva. É
  honesto chamar de *estimativa de alta precisão sob protocolo padronizado*,
  não de medição pericial certificada.
- O detector clássico (cor + movimento) erra mais em fundo poluído; para quadra
  real use `--detector dl` (YOLOv8). O YOLOv8 pré-treinado detecta bola de tênis
  como "sports ball", mas o recall cai com a bola muito pequena/borrada — o
  ganho real vem de **fine-tuning** com dataset de bola de tênis (`--model`).
- Sem correção de distorção de lente nem de perspectiva 3D (roadmap).

## Roadmap

- [x] Detector de bola por deep learning (YOLOv8, `--detector dl`).
- [ ] Fine-tuning do detector com dataset de bola de tênis.
- [ ] Calibração assistida (clicar 2 pontos / detectar a quadra automaticamente).
- [ ] Estimativa de pose para biomecânica do gesto (ângulos, cadeia cinética).
- [ ] Correção de perspectiva via homografia da quadra.
- [ ] Banco de dados do atleta + gráficos evolutivos e comparativos.
- [ ] Relatório PDF protocolável e integração com a biblioteca de exercícios.

## Estrutura

```
tennis-serve-analyzer/
├── src/
│   ├── analyze.py          # CLI principal
│   ├── tracking.py         # associação temporal + interface de detector
│   ├── ball_tracker.py     # detector clássico (cor + movimento)
│   ├── detector_dl.py      # detector deep learning (YOLOv8)
│   ├── calibration.py      # conversão pixel → metro
│   ├── speed_estimator.py  # cálculo de velocidade
│   └── report.py           # CSV, gráfico, vídeo anotado, JSON
├── tools/
│   ├── generate_test_video.py    # saque sintético p/ validação
│   └── render_realistic_ball.py  # bola sombreada p/ testar o detector DL
├── output/                 # exemplos gerados (classic) e output/dl (DL)
├── requirements.txt        # núcleo
└── requirements-dl.txt     # detector DL (opcional)
```
