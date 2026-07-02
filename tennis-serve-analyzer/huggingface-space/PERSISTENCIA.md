# Armazenamento permanente (grátis) — não perca dados nem fotos

Por padrão, o disco do Hugging Face Space é **efêmero**: quando o Space dorme ou
reinicia, o banco (`history.db`) é recriado e você perde histórico, fichas,
**fotos das avaliações** e os **percursos da bola**.

Para tornar tudo **permanente e grátis**, o app sincroniza o banco inteiro com um
**Dataset privado** do Hugging Face a cada gravação. Basta ativar um token.

## Passo a passo (uma vez)

1. **Crie um token de escrita**
   Hugging Face → **Settings → Access Tokens → New token** → tipo **Write**. Copie.

2. **Adicione o segredo no Space**
   Seu Space → **Settings → Variables and secrets → New secret**
   - Name: `HF_TOKEN`
   - Value: (cole o token)

3. **(Opcional) Defina o Dataset**
   Novo secret `DATA_REPO` com um nome, ex.: `seu_usuario/vf-tenis-data`.
   Se não definir, o app usa `<seu_usuario>/vf-tenis-data` automaticamente.

4. **Factory rebuild** no Space.

Pronto. Na próxima inicialização o app **restaura** o banco do Dataset e, a cada
nova gravação (análise, avaliação, foto, ficha, percurso da bola), **envia** a
versão atualizada. O Dataset é **privado**.

## Como conferir

Abra **Histórico** no app: há um selo no topo —
- ✅ *Armazenamento permanente ativo*  → tudo salvo no Dataset.
- ⚠️ *Dados podem se perder*  → o `HF_TOKEN` ainda não está configurado.

## Segurança

O token fica **apenas** nos segredos do Space — nunca aparece no código, nos
laudos ou nos exports. Sem o token, o app continua funcionando normalmente, só
que com dados efêmeros.

## O que fica salvo

Tudo no `history.db` (sincronizado): fichas/anamnese, todas as análises de saque
(com golpe, plano inteligente e o **percurso da bola** em imagem), todas as
avaliações posturais **com as fotos anotadas**, e as preferências do operador.
