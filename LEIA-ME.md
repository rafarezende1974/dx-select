# DX Select v0.1 — protótipo Windows de seleção de fotos

Seleção (culling) no estilo Aftershoot, em versão protótipo e offline:
importa uma pasta de JPGs, agrupa fotos parecidas tiradas em sequência,
sugere a melhor de cada grupo e exporta só as mantidas.

**Não é uma cópia do Aftershoot.** Não usa nome, marca, textos ou
imagens dele. A ideia é a mesma — tirar o trabalho repetitivo da
triagem — com implementação própria, simples e explicável.

## O que faz na v0.1

- Abre qualquer pasta de JPGs, incluindo subpastas (ex.:
  `D:\Eventos\<data>_<evento>\01_Fotos_JPG`)
- Agrupa sequências: fotos visualmente parecidas (dHash) tiradas com
  até 60 segundos de diferença viram um grupo
- Pontua cada foto de 0 a 100: 70% nitidez (gradiente) + 30% exposição
- Sugere a melhor nota de cada grupo como "Manter" (★)
- Atalhos: `→ / ←` navega no grupo, `G` próximo grupo, `M` ou `Espaço`
  mantém, `X` rejeita, `U` volta para "a decidir", `B` mantém só a
  melhor do grupo e rejeita as outras
- Salva as decisões em `.dxselect.json` na pasta de origem: fechar e
  reabrir continua de onde parou
- Exporta por **cópia** (nunca move) as mantidas para a pasta de
  destino, preservando as subpastas, e grava `selecao.csv` com o
  relatório (arquivo, grupo, decisão, nota, nitidez, brilho)

## O que NÃO faz na v0.1 (de propósito)

- Não apaga, move ou altera nenhum original
- Não edita, não retoca e não lê RAW — JPG primeiro, para validar o
  fluxo de triagem antes de complicar
- Não detecta rosto nem olho fechado, não aprende seu estilo e não
  usa nuvem: tudo roda local, offline
- Não sobe nada para servidor nenhum

## Como testar primeiro (recomendado)

1. Copie uma pasta pequena de JPGs (20 a 50 fotos de um evento) para
   uma pasta de teste — não teste direto na pasta original na 1ª vez.
2. Abra o `DXSelect.exe`, clique em "Abrir pasta…" e escolha a pasta
   de teste.
3. Revise grupo por grupo. Confira se as sequências agruparam certo
   e se a sugestão ★ faz sentido.
4. Clique em "Exportar mantidas…", escolha outra pasta e confira as
   cópias + o `selecao.csv`.

## Build (mesmo esquema do Editor Assistente)

1. Criar o repositório no GitHub pela web (a integração não cria
   repositórios): sugestão `rafarezende1974/dx-select`.
2. Subir: `app.py`, `culling_core.py`, `generate_assets.py`,
   `requirements.txt`, `test_core.py`, `LEIA-ME.md`,
   `WORKFLOW-BUILD-WINDOWS.yml.txt`, `.gitignore`.
   Não subir `assets/` (o workflow gera o ícone no runner).
3. Criar pela web o arquivo `.github/workflows/build-windows.yml`
   colando o conteúdo de `WORKFLOW-BUILD-WINDOWS.yml.txt`
   (a integração não cria arquivos de workflow).
4. O build gera o artefato `dx-select` com `DXSelect.exe`.
   Apagar o .exe antigo antes de baixar o novo — os artefatos têm
   o mesmo nome.

Sem certificado de assinatura, o Windows pode mostrar "editor
desconhecido" (SmartScreen) na primeira execução — é o aviso padrão
para .exe sem assinatura, igual ao dos outros apps DX.

## Arquivos

- `app.py` — interface Tkinter
- `culling_core.py` — varredura, dHash, agrupamento, nota, exportação
- `generate_assets.py` — gera o ícone (fotos empilhadas + check verde)
- `test_core.py` — teste com fotos simuladas (rode com
  `python test_core.py`; não precisa de fotos reais nem de tela)
