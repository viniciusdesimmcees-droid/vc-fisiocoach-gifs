# Dockerfile para o Hugging Face Spaces (SDK: Docker).
# Baixa o código direto do repositório público no GitHub e roda o app.
# O Hugging Face grátis tem 2 vCPU + 16 GB de RAM — bem mais forte que o Render
# grátis, então a análise de vídeo roda tranquila.
FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    git libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Pega só a pasta do app (sparse checkout) — evita baixar os GIFs do repositório.
RUN git clone --depth 1 --filter=blob:none --sparse \
      https://github.com/viniciusdesimmcees-droid/vc-fisiocoach-gifs.git . \
    && git sparse-checkout set tennis-serve-analyzer

WORKDIR /app/tennis-serve-analyzer
RUN pip install --no-cache-dir -r requirements.txt

# O runtime do HF roda como usuário sem privilégios: garante pastas graváveis.
RUN mkdir -p webapp/static/results webapp/uploads && chmod -R 777 webapp

ENV PORT=7860 \
    MPLCONFIGDIR=/tmp/mpl \
    PROC_MAX_WIDTH=720 \
    PROC_MAX_FRAMES=1500

EXPOSE 7860
CMD ["sh", "-c", "gunicorn --chdir webapp --timeout 300 --workers 2 --bind 0.0.0.0:$PORT app:app"]
