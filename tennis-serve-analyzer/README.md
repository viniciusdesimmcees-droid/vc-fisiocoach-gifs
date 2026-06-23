# Analisador de Saque de Tênis — Protótipo

Protótipo de visão computacional que, a partir de um vídeo do celular, entrega
duas análises do saque:

1. **Velocidade da bola** — rastreio + calibração + velocidade no impacto.
2. **Biomecânica do gesto** — pose do atleta, ângulos articulares, fases do
   saque e sequência da cadeia cinética (proximal→distal).

Gera vídeos anotados, gráficos, CSV e resumos JSON prontos para protocolar e
entregar à equipe do atleta. Faz parte do ecossistema **VC Fisiocoach**.

## Abrir o app (interface web)

A forma visual de usar — abre no navegador do celular ou do computador:

```bash
pip install -r requirements.txt          # inclui o Flask
python webapp/app.py                      # sobe o servidor
```

Depois abra **http://localhost:5000** no navegador. Você envia o vídeo do saque,
informa a calibração e o app mostra, na mesma tela: a **velocidade** em destaque,
o **GIF anotado** (com a bola rastreada), o **gráfico de velocidade** e, se marcar
a opção, a **biomecânica** (ângulos e fases). Tudo com botões para baixar os
relatórios (MP4, CSV, JSON).

> O app roda na sua máquina. Para usar do celular na mesma rede, acesse
> `http://IP-DO-COMPUTADOR:5000`. O detector clássico é o padrão (rápido); o
> deep learning e a biomecânica exigem `requirements-dl.txt`.

Prefere automação/integração? Há também a CLI (abaixo).

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

## Camada de biomecânica (análise do gesto)

Mede o GESTO do atleta, não só a bola. Pipeline:
`pose (YOLOv8-pose) → ângulos articulares → fases do saque → cadeia cinética`.

```bash
python src/analyze_biomech.py --video saque.mp4 --athlete "Nome" --fps 240
```

Mede, por quadro: ângulos de **cotovelo, ombro, joelho, quadril** e inclinação
do tronco; segmenta as fases (**loading → cocking → contato → follow-through**)
pela trajetória do punho; e avalia a **sequência da cadeia cinética** — no saque
eficiente os picos de velocidade angular vão de proximal a distal
(quadril/tronco → ombro → cotovelo). Saídas: `biomech_angulos.png`,
`biomech_resumo.json` e `biomech_esqueleto.mp4` (vídeo com esqueleto + fases).

A matemática dos ângulos é geometria pura e tem testes determinísticos:

```bash
python tools/test_biomechanics.py     # ângulo reto=90, fases, cadeia, etc.
python tools/demo_biomech.py          # gera um relatório-exemplo (keypoints sintéticos)
```

A pose foi validada em foto real (17/17 keypoints; cotovelo 98°, joelho 174°).
Como a pose só funciona em pessoas reais filmadas, a `demo_biomech` usa
keypoints sintéticos apenas para mostrar o FORMATO do relatório.

## Fine-tuning do detector de bola

O YOLOv8 pré-treinado já detecta a bola, mas o ganho de robustez vem do
fine-tuning com dados anotados. O harness está pronto:

```bash
# 1) dataset (troque por imagens REAIS anotadas no formato YOLO p/ produção)
python tools/make_dataset.py --out dataset --n-train 200 --n-val 40
# 2) treino
python tools/train_detector.py --data dataset/data.yaml --base yolov8n.pt \
    --epochs 50 --imgsz 960 --name tennis_ball
# 3) usar os pesos treinados no medidor de velocidade
python src/analyze.py --video saque.mp4 --detector dl \
    --model runs/detect/tennis_ball/weights/best.pt ...
```

Estrutura esperada dos dados (compatível com export do Roboflow/CVAT):
`images/{train,val}/*.jpg` + `labels/{train,val}/*.txt` (`classe cx cy w h`
normalizado) + `data.yaml`.

Pipeline validado no dataset sintético: o fine-tuning convergiu para
**mAP50 ≈ 0,99 / mAP50-95 ≈ 0,95** no conjunto de validação held-out,
confirmando que o loop de treino aprende e exporta o `best.pt`.

## Limitações (transparência técnica)

- **Velocidade absoluta da bola não é "radar Doppler".** A escala vale no plano
  da referência; se a bola sai muito desse plano há erro de perspectiva. É
  honesto chamar de *estimativa de alta precisão sob protocolo padronizado*,
  não de medição pericial certificada.
- O detector clássico (cor + movimento) erra mais em fundo poluído; para quadra
  real use `--detector dl` (YOLOv8). O YOLOv8 pré-treinado detecta bola de tênis
  como "sports ball", mas o recall cai com a bola muito pequena/borrada — o
  ganho real vem de **fine-tuning** com dataset de bola de tênis (`--model`).
- A biomecânica usa pose 2D: ângulos no plano da imagem. Movimentos fora do
  plano da câmera têm erro de projeção. Pose 3D / multi-câmera é trabalho futuro.
- Os números de validação de bola (mAP ~0,99) e a `demo_biomech` vêm de dados
  **sintéticos** — provam que os pipelines funcionam, não a acurácia em quadra.
  Validação real exige filmagem do atleta.
- Sem correção de distorção de lente nem de perspectiva 3D (roadmap).

## Roadmap

- [x] Detector de bola por deep learning (YOLOv8, `--detector dl`).
- [x] Harness de fine-tuning do detector (dataset YOLO + treino + val).
- [x] Estimativa de pose + biomecânica (ângulos, fases, cadeia cinética).
- [ ] Fine-tuning com dataset REAL de bola de tênis (Roboflow/CVAT).
- [ ] Calibração assistida (clicar 2 pontos / detectar a quadra automaticamente).
- [ ] Correção de perspectiva via homografia da quadra.
- [ ] Banco de dados do atleta + gráficos evolutivos e comparativos.
- [ ] Relatório PDF protocolável e integração com a biblioteca de exercícios.

## Estrutura

```
tennis-serve-analyzer/
├── src/
│   ├── analyze.py          # CLI velocidade da bola
│   ├── analyze_biomech.py  # CLI biomecânica do gesto
│   ├── tracking.py         # associação temporal + interface de detector
│   ├── ball_tracker.py     # detector clássico (cor + movimento)
│   ├── detector_dl.py      # detector deep learning (YOLOv8)
│   ├── pose_estimator.py   # pose do atleta (YOLOv8-pose)
│   ├── biomechanics.py     # ângulos, fases, cadeia cinética (geometria pura)
│   ├── calibration.py      # conversão pixel → metro
│   ├── speed_estimator.py  # cálculo de velocidade
│   ├── report.py           # saídas da velocidade
│   └── biomech_report.py   # saídas da biomecânica
├── tools/
│   ├── generate_test_video.py    # saque sintético p/ validação
│   ├── render_realistic_ball.py  # bola sombreada p/ testar o detector DL
│   ├── make_dataset.py           # dataset YOLO rotulado (fine-tuning)
│   ├── train_detector.py         # fine-tuning do YOLOv8
│   ├── test_biomechanics.py      # testes determinísticos da biomecânica
│   └── demo_biomech.py           # relatório-exemplo de biomecânica
├── webapp/                 # app web (Flask): abra http://localhost:5000
│   ├── app.py
│   ├── templates/          # index.html (upload) e result.html (resultado)
│   └── static/             # estilo + logo (resultados gerados ficam aqui)
├── output/                 # exemplos gerados (velocidade e biomech)
├── requirements.txt        # núcleo + Flask (app web)
└── requirements-dl.txt     # detector DL + pose + treino (opcional)
```
