"""Manual do Operador — conteúdo único usado na página /manual e no PDF.

Cada seção: título, ícone (só na web) e itens (bullets em linguagem direta,
escritos para o professor/operador, não para programador).
"""

from __future__ import annotations

VERSAO = "1.3"

SECOES = [
    {"icone": "🎾", "titulo": "1. O que é o VF Tênis Scanner",
     "itens": [
         "Sistema completo de avaliação do tenista pelo celular: mede a velocidade "
         "do saque, analisa a biomecânica do gesto, reconhece o golpe, avalia a "
         "postura, calcula risco de lesão e monta plano de treino com exercícios.",
         "Tudo fica registrado por aluno: evolução do saque, evolução postural com "
         "fotos, laudos em PDF com assinatura e exportação completa dos dados.",
         "Cada medição vem com um selo de confiança (margem de erro) e verificações "
         "automáticas de qualidade — o sistema diz o quanto confiar em cada número.",
     ]},
    {"icone": "📋", "titulo": "2. Antes de filmar — protocolo de captura",
     "itens": [
         "Câmera DE LADO (perpendicular ao saque), parada, em tripé ou apoio firme. "
         "A bola deve atravessar a tela na horizontal — é o fator nº 1 de precisão.",
         "Use câmera lenta do app nativo do celular: 120–240 fps. A 30/60 fps a "
         "velocidade fica imprecisa para saques rápidos.",
         "Boa luz, bola contrastante com o fundo, corpo inteiro e bola sempre no quadro.",
         "Tenha uma medida conhecida visível para calibrar (ex.: altura da rede no "
         "centro = 0,914 m).",
         "A página 'Protocolo de captura' no app tem o checklist completo com "
         "Faça/Evite para conferir antes de gravar.",
     ]},
    {"icone": "🚀", "titulo": "3. Análise do saque — passo a passo",
     "itens": [
         "Na tela inicial: grave na hora ou envie um vídeo já filmado em câmera lenta.",
         "Preencha o nome do aluno (sempre igual, para o histórico juntar tudo).",
         "fps: deixe 0 para usar o do arquivo; se filmou a 240 fps e o arquivo diz "
         "30, informe o fps REAL — isso muda diretamente a velocidade.",
         "Calibração pela quadra: toque em 2 pontos de uma medida conhecida e "
         "informe a distância. Se não calibrar, o app usa o tamanho da bola "
         "(6,7 cm) como régua automática.",
         "Golpe: deixe em 'Detectar automaticamente' ou force manualmente "
         "(saque/forehand/backhand). A escolha manual sempre vence.",
         "Marque 'biomecânica' para ângulos, fases, X-Factor, golpe automático e "
         "para alimentar o boneco 3D e o saque animado.",
     ]},
    {"icone": "🔍", "titulo": "4. Entendendo o resultado",
     "itens": [
         "Selo de confiança (± margem de erro): ferramenta INTERNA do operador e "
         "vem DESLIGADO — o atleta vê só a velocidade. Ligue em Configurações "
         "quando quiser conferir a margem e os fatores (fps, calibração, rastreio).",
         "Qualidade da captura (pré-voo): checa câmera lateral, fps × velocidade, "
         "bola visível, calibração plausível e desfoque — cada problema vem com "
         "'como melhorar'.",
         "Percurso da bola: SEMPRE confira o card 'Confira o que foi medido' — o "
         "ponto verde é o início e o X vermelho é o impacto. Se o caminho não for "
         "o saque, corte o vídeo e analise de novo.",
         "Calibração × bola: se a quadra e a bola divergirem, o app avisa e mostra "
         "a velocidade que a bola sugere — geralmente a calibração manual é a errada.",
         "O relatório PDF completo sai com velocímetro, nota técnica, biomecânica, "
         "plano inteligente, benchmark, referências científicas e glossário.",
     ]},
    {"icone": "🧍", "titulo": "5. Avaliação postural",
     "itens": [
         "Menu 'Avaliação postural': envie foto ou vídeo do aluno de frente, costas "
         "ou lado — corpo inteiro, ereto, boa luz, fundo limpo.",
         "São 4 posições: de frente, de costas, PERFIL DIREITO e PERFIL ESQUERDO — "
         "o comparativo de evolução só compara a mesma posição entre si.",
         "O app mede ombros, cabeça, pélvis, tronco e joelhos (frente/costas) e "
         "cabeça anteriorizada + inclinação do tronco (nos perfis).",
         "A foto anotada fica salva no banco (permanente) e alimenta o comparativo "
         "primeira × última avaliação, no app e no PDF.",
         "É triagem 2D: apoio à avaliação do profissional, não diagnóstico médico.",
         "TESTES DE MOVIMENTO (menu próprio): screening funcional por vídeo no padrão "
         "dos grandes protocolos — agachamento profundo com braços elevados (perfil) e "
         "agachamento unilateral D/E (frente). O app mede o gesto, aponta os MÚSCULOS "
         "com déficit provável (glúteo médio, core, tornozelo, ombros…) e já encaminha "
         "os exercícios da biblioteca VC Fisiocoach.",
     ]},
    {"icone": "👥", "titulo": "6. Alunos: ficha, histórico e edição",
     "itens": [
         "Menu 'Histórico': lista de todos os alunos com resumo (saques, posturais, "
         "ficha). Toque no nome para abrir tudo do aluno.",
         "Cadastre a FICHA (anamnese): idade, altura/peso, mão dominante, lesões, "
         "dores, horas de treino, objetivos — ela deixa o risco de lesão e o plano "
         "inteligente mais precisos.",
         "Cada análise pode ser corrigida (✏️), excluída (🗑️) ou tirada do laudo "
         "(🚫) — análises 'fora do laudo' continuam guardadas, mas não entram nas "
         "estatísticas nem no laudo consolidado. Use quando a captura ficou ruim.",
         "Dá para renomear o aluno (move todo o histórico junto) ou excluir tudo.",
     ]},
    {"icone": "🧍‍♂️", "titulo": "7. Boneco 3D, comparativo e saque animado",
     "itens": [
         "Boneco 3D: gira 360° com o dedo; pontos verdes = positivos, âmbar = "
         "atenção/músculos a trabalhar, vermelho = atenção maior. Toque num ponto "
         "ou na lista para ver a explicação (o boneco gira até o ponto).",
         "Comparativo 3D: dois bonecos lado a lado (primeira × última avaliação) + "
         "lista 'O que mudou' com o quanto cada medida melhorou/piorou.",
         "Saque 3D: o boneco executa as 6 fases do saque usando os ÂNGULOS MEDIDOS "
         "do aluno (joelho no carregamento, cotovelo e tronco no contato). Controles "
         "de play, avanço quadro a quadro e câmera lenta.",
         "Modo apresentação (⛶): tela cheia para mostrar ao aluno na quadra; a tela "
         "não apaga durante a apresentação.",
     ]},
    {"icone": "🧠", "titulo": "8. Plano inteligente e benchmark profissional",
     "itens": [
         "Inteligência VF: cruza a biomecânica com a ficha e gera índice de risco "
         "de lesão (com os fatores), músculos a priorizar (com o motivo) e "
         "exercícios da biblioteca VC Fisiocoach com GIFs.",
         "Benchmark vs. pro: cada métrica posicionada de Iniciante a Profissional, "
         "com % rumo ao padrão pro, gráfico radar e 'o que falta para o nível pro' "
         "com dicas de treino.",
         "São regras transparentes e faixas da literatura — apoio à decisão do "
         "profissional, não avaliação oficial de ranking.",
     ]},
    {"icone": "📄", "titulo": "9. Laudos, exportação e envio ao aluno",
     "itens": [
         "Relatório por análise: em qualquer análise do histórico, '📄 Baixar "
         "relatório desta análise' reconstrói o PDF completo a qualquer momento.",
         "Laudo consolidado do aluno: ficha + evolução do saque + golpe + postura "
         "com fotos + comparativo antes × agora + mapa corporal + plano inteligente "
         "+ histórico completo + objetivo.",
         "Livro de dados (ZIP): TUDO do aluno — laudo, dados brutos em JSON, "
         "gráficos, todas as fotos posturais, o percurso da bola de cada saque e o "
         "relatório PDF de cada análise.",
         "Relatório personalizado ('🧾 Montar relatório'): marque só as seções que "
         "quer enviar ao atleta (ficha, saque, postura, comparativo, mapa, plano, "
         "histórico) e anexe as análises individuais que escolher.",
         "Botão '📤 Enviar' em todo PDF: compartilha direto no WhatsApp, e-mail etc.",
     ]},
    {"icone": "⚙️", "titulo": "10. Configurações e armazenamento permanente",
     "itens": [
         "Configurações: desmarque métricas que não devem participar da leitura "
         "(referências e benchmark respeitam a escolha).",
         "Como a análise é feita: ligue/desligue cada bloco (verificação pela bola, "
         "pré-voo, didático, glossário, referências, benchmark, plano) e defina o "
         "diâmetro padrão da bola (foam/junior variam).",
         "Avaliações posturais do mesmo dia formam uma SESSÃO; o comparativo só "
         "compara a mesma vista (frontal com frontal, lateral com lateral).",
         "Armazenamento permanente: confira o selo no topo do Histórico. Verde ✅ = "
         "tudo salvo num Dataset privado do Hugging Face; amarelo ⚠️ = configure o "
         "segredo HF_TOKEN (passo a passo na página 'Armazenamento permanente').",
         "Com o token ativo, banco, fotos e percursos sobrevivem a qualquer "
         "reinício do servidor.",
     ]},
    {"icone": "🔬", "titulo": "11. Confiabilidade e limites (honestidade técnica)",
     "itens": [
         "A página 'Validação & acurácia' documenta o método, a acurácia esperada "
         "(±4% no cenário ideal) e o autoteste por queda livre: solte uma bola de "
         "altura H, a física diz a velocidade (v = √(2gH)) — compare com o app.",
         "É medição 2D por vídeo — não é radar Doppler. Ângulos e faixas têm margem; "
         "biomecânica e postura são estimativas educativas.",
         "Captura Ruim no pré-voo (ou confiança baixa, se o selo estiver ligado) = "
         "refilme seguindo o protocolo antes de registrar o resultado no histórico "
         "(ou tire a análise do laudo).",
         "Nada aqui substitui avaliação presencial nem diagnóstico médico.",
     ]},
]
