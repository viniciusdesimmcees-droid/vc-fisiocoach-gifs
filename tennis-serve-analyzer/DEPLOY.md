# Como colocar o app online (HTTPS automático, sem terminal)

O app já está pronto para produção (servidor gunicorn). Abaixo, o caminho mais
simples — conectar o GitHub a uma plataforma que faz o deploy e o **HTTPS
automático** sozinha. Você acessa por uma URL `https://...` de qualquer lugar, e
a câmera do celular funciona (porque a plataforma serve em HTTPS).

> Importante: o app fica online a partir do **seu** repositório no GitHub. Hoje
> estamos na branch `claude/tennis-serve-analyzer-83yayv`. Para publicar, faça o
> merge para a branch principal (ou aponte a plataforma para essa branch).

---

## Opção A — Render (recomendada, tem plano grátis)

1. Crie uma conta em https://render.com (pode entrar com o GitHub).
2. No painel: **New → Blueprint**.
3. Conecte o repositório `vc-fisiocoach-gifs`.
4. O Render detecta o arquivo **`render.yaml`** e já configura tudo
   (pasta `tennis-serve-analyzer`, build e start). Clique em **Apply/Deploy**.
5. Em ~2–4 min ele te dá uma URL `https://fisiocoach-saque.onrender.com`.
   Pronto — abra no celular e instale na tela inicial.

Não precisa rodar nenhum comando: a cada push no GitHub, o Render reimplanta.

---

## Opção B — Railway (também simples)

1. Conta em https://railway.app (login com GitHub).
2. **New Project → Deploy from GitHub repo** → escolha o repositório.
3. Em Settings, defina **Root Directory** = `tennis-serve-analyzer`.
   O Railway usa o **`Dockerfile`** (ou o `Procfile`) automaticamente.
4. Gere um domínio público (**Settings → Networking → Generate Domain**) — vem
   com HTTPS. Acesse a URL.

---

## Opção C — Fly.io / Google Cloud Run (Docker)

Use o **`Dockerfile`** incluído. Exige a CLI da plataforma uma única vez:

```bash
# Fly.io
fly launch        # detecta o Dockerfile; defina o diretório tennis-serve-analyzer
fly deploy
```

Cloud Run: `gcloud run deploy --source tennis-serve-analyzer` (HTTPS automático).

---

## O que esperar (limitações honestas)

- **Plano grátis = detector clássico.** O blueprint instala a versão leve
  (numpy/opencv/flask), que cabe no grátis. O **deep learning** e a
  **biomecânica** dependem do `torch` (~1 GB) — para usá-los online, escolha um
  plano com mais memória/disco e instale também `requirements-dl.txt`.
- **Armazenamento temporário.** Nessas plataformas o disco é efêmero: o vídeo
  enviado e os resultados existem durante a sessão, mas não ficam guardados.
  O **histórico do atleta** (banco de dados + gráficos evolutivos) é o próximo
  passo e é o que dá persistência de verdade.
- **Plano grátis “dorme”.** No grátis do Render, o app hiberna sem uso e demora
  alguns segundos para acordar no primeiro acesso. Um plano pago evita isso.
- **Tamanho de upload.** Vídeos muito grandes/long os podem estourar limites da
  plataforma. Prefira clipes curtos do saque.

## Domínio próprio (opcional)

Todas as plataformas acima permitem ligar um domínio seu (ex.:
`saque.seudominio.com`) com HTTPS automático, deixando ainda mais profissional.
