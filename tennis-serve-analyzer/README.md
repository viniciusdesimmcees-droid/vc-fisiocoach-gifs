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

## Instalação

```bash
pip install -r requirements.txt
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

### Testar sem filmagem (vídeo sintético com velocidade conhecida)

```bash
python tools/generate_test_video.py --serve-kmh 180 --fps 240
python src/analyze.py --video output/saque_sintetico.mp4 \
  --ref-length-m 1.0 --ref-length-px 200 --fps 240
```

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
- O rastreador atual é clássico (cor + movimento). Em fundo poluído ou
  iluminação ruim erra mais. Em produção, trocar por um detector treinado
  (YOLO/TrackNet para bola de tênis) mantendo a mesma interface.
- Sem correção de distorção de lente nem de perspectiva 3D (roadmap).

## Roadmap

- [ ] Detector de bola por deep learning (robustez em quadra real).
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
│   ├── ball_tracker.py     # detecção + rastreio da bola
│   ├── calibration.py      # conversão pixel → metro
│   ├── speed_estimator.py  # cálculo de velocidade
│   └── report.py           # CSV, gráfico, vídeo anotado, JSON
├── tools/
│   └── generate_test_video.py  # saque sintético p/ validação
├── output/                 # exemplos gerados
└── requirements.txt
```
