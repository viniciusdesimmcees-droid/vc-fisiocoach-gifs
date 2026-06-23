# Imagem de produção do Analisador de Saque (detector clássico, leve).
# Serve em qualquer plataforma com Docker: Railway, Fly.io, Cloud Run, etc.
# A plataforma termina o HTTPS na borda; o app serve HTTP atrás dela.
FROM python:3.11-slim

# libglib é necessária para o OpenCV headless em algumas operações.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PORT=8080
EXPOSE 8080

CMD ["sh", "-c", "gunicorn --chdir webapp --timeout 120 --workers 1 --bind 0.0.0.0:$PORT app:app"]
