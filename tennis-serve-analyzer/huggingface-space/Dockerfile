# Dockerfile para o Hugging Face Spaces (SDK: Docker).
# Baixa o código direto do repositório público no GitHub e roda o app.
# O Hugging Face grátis tem 2 vCPU + 16 GB de RAM — aguenta a análise de vídeo
# E a biomecânica (pose por deep learning).
FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    git libglib2.0-0 libgl1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Pega só a pasta do app (sparse checkout) — evita baixar os GIFs do repositório.
RUN git clone --depth 1 --filter=blob:none --sparse \
      https://github.com/viniciusdesimmcees-droid/vc-fisiocoach-gifs.git . \
    && git sparse-checkout set tennis-serve-analyzer

WORKDIR /app/tennis-serve-analyzer
RUN pip install --no-cache-dir -r requirements.txt
# Biomecânica: torch (CPU) + ultralytics. Wheel CPU é bem menor que a versão GPU.
# IMPORTANTE: torch e torchvision precisam ser um PAR COMPATÍVEL, instalados
# JUNTOS e do MESMO índice — senão o torchvision não registra seus operadores e
# o deep learning falha com "operator torchvision::nms does not exist".
# Par testado (CPU): torch 2.4.1 + torchvision 0.19.1.
RUN pip install --no-cache-dir torch==2.4.1 torchvision==0.19.1 \
      --index-url https://download.pytorch.org/whl/cpu \
    && pip install --no-cache-dir "ultralytics>=8.3,<9" \
    && python -c "import torch, torchvision; from torchvision.ops import nms; \
nms(torch.tensor([[0.,0.,1.,1.]]), torch.tensor([0.9]), 0.5); \
print('torch', torch.__version__, '+ torchvision', torchvision.__version__, 'OK')"

# Pré-baixa os modelos (bola e pose) para não baixar a cada requisição.
RUN cd webapp && python -c "from ultralytics import YOLO; YOLO('yolov8n.pt'); YOLO('yolov8n-pose.pt')"

# O runtime do HF roda como usuário sem privilégios: garante pastas/arquivos graváveis.
RUN mkdir -p webapp/static/results webapp/uploads && chmod -R 777 webapp

ENV PORT=7860 \
    MPLCONFIGDIR=/tmp/mpl \
    PROC_MAX_WIDTH=720 \
    PROC_MAX_FRAMES=1500 \
    POSE_MAX_WIDTH=640 \
    POSE_MAX_FRAMES=150

EXPOSE 7860
CMD ["sh", "-c", "gunicorn --chdir webapp --timeout 300 --workers 2 --bind 0.0.0.0:$PORT app:app"]
