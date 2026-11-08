# Listar seguidores do Instagram

Gera a lista de seguidores (ou de quem a pessoa segue) de um perfil do Instagram com
**nome de usuário, nome e foto de perfil**, a partir de uma página que **você** salva no navegador.

O script não entra no Instagram nem automatiza nada no site: ele só lê o arquivo salvo no seu
computador. Por isso não tem captcha nem risco de bloquear a sua conta.

## Instalar (uma vez)

Precisa de Python 3.10+.

```bash
git clone https://github.com/parisifit/scraping_insta.git
cd scraping_insta
python -m venv .venv
# Windows: .venv\Scripts\activate    ·    Mac/Linux: source .venv/bin/activate
pip install -r requirements.txt
```

## Usar

1. No computador, abra o Instagram no seu navegador de sempre (Chrome, Edge, Firefox) e entre no perfil da pessoa.
2. Clique em **seguidores**. Na janela que abre, role a lista até o fim, até parar de carregar gente nova.
   (Com menos de mil pessoas, leva poucos minutos.)
3. Com a janela ainda aberta, salve a página: **Ctrl+S** (Mac: Cmd+S) → tipo **"Página da Web, completa"**.
   Salve na pasta do projeto, por exemplo como `seguidores.html`. O navegador cria junto uma pasta
   `seguidores_files` com as fotos: deixe-a ao lado do arquivo.
4. Rode:

```bash
python ler_pagina_salva.py seguidores.html --perfil fulana
```

Para "seguindo", repita os passos clicando em **seguindo** e rode:

```bash
python ler_pagina_salva.py seguindo.html --tipo seguindo --perfil fulana
```

## O que sai

Em `saida/<perfil>/`:

| Arquivo | Conteúdo |
| --- | --- |
| `seguidores.csv` / `seguindo.csv` | usuário, nome, arquivo da foto, link da foto. Separado por `;`, abre direto no Excel |
| `seguidores.json` / `seguindo.json` | os mesmos dados em JSON |
| `seguidores.html` / `seguindo.html` | galeria com foto, @ e nome. Clique para abrir o perfil |
| `fotos/<usuario>.jpg` | foto de perfil de cada pessoa |

As fotos são copiadas da pasta `_files` que o navegador salvou. Se alguma não estiver lá, o script
tenta baixá-la pelo link da página.

## Se algo der errado

- **"Não achei a janela de seguidores"**: a página foi salva com a lista fechada. Abra a lista de novo, role e salve.
- **Faltou gente**: a lista não foi rolada até o fim antes de salvar. Compare o número lido com o total do perfil.
- **Perfil privado**: o Instagram só mostra a lista se você seguir a pessoa.
- **Leu 0 pessoas ou nomes estranhos**: o Instagram mudou o layout. Abra uma issue com a mensagem do terminal.

## Privacidade

As listas são dados pessoais de terceiros (LGPD): guarde só para consulta. O `.gitignore` impede
que `saida/` e as páginas salvas sejam enviadas para o GitHub.
