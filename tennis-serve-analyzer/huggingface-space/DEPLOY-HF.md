# Publicar no Hugging Face Spaces (grátis, sem cartão)

O Hugging Face Spaces grátis tem **2 vCPU + 16 GB de RAM** — forte o bastante
para a análise de vídeo rodar liso. Não pede cartão.

Você só precisa criar um Space e colar **2 arquivos** (o código vem do GitHub
automaticamente pelo Dockerfile).

## Passo a passo

1. **Crie uma conta** em https://huggingface.co/join (pode usar e-mail ou Google).

2. **Crie um Space:** acesse https://huggingface.co/new-space
   - **Owner:** sua conta
   - **Space name:** `vf-tenis-scanner`
   - **License:** pode deixar a padrão
   - **Select the Space SDK:** escolha **Docker** → template **Blank**
   - **Space hardware:** **CPU basic** (grátis)
   - **Visibility:** Public
   - Clique em **Create Space**.

3. **Configure o README:** o Space abre com um arquivo `README.md`.
   - Clique em **Files** → no `README.md` clique em **Edit**.
   - Apague tudo e cole o conteúdo do `README.md` desta pasta
     (`huggingface-space/README.md`).
   - Clique em **Commit changes**.

4. **Adicione o Dockerfile:**
   - Em **Files**, clique em **Add file → Create a new file**.
   - Nome do arquivo: `Dockerfile`
   - Cole o conteúdo do `Dockerfile` desta pasta
     (`huggingface-space/Dockerfile`).
   - Clique em **Commit new file**.

5. **Aguarde o build.** O Space mostra **Building** e depois **Running** (uns
   2–5 min na primeira vez). Quando estiver **Running**, o app aparece na própria
   página do Space, com uma URL pública tipo:
   `https://SEU-USUARIO-vf-tenis-scanner.hf.space`

Pronto — abra no celular, instale na tela inicial e use.

## Atualizar depois

Como o Dockerfile baixa o código do GitHub no build, para pegar novidades do
app é só clicar em **Settings → Factory rebuild** no Space.

## Observações

- O armazenamento é temporário (resultados não ficam guardados entre sessões) —
  isso é resolvido pelo próximo passo do projeto: o **histórico do atleta**.
- Detector clássico (rápido). Deep learning/biomecânica ficam para um upgrade
  futuro (precisam do torch).
