# Listar seguidores do Instagram

Script em Python + Selenium que abre o Chrome com **a sua conta** logada e lista os seguidores
e/ou quem um perfil segue. Para cada pessoa: **nome de usuário, nome e foto de perfil**.

Nada é publicado: as listas e o login ficam só no seu computador.

## Instalar (uma vez)

Precisa de Python 3.10+ e do Google Chrome instalados.

```bash
git clone https://github.com/parisifit/scraping_insta.git
cd scraping_insta
python -m venv .venv
# Windows: .venv\Scripts\activate    ·    Mac/Linux: source .venv/bin/activate
pip install -r requirements.txt
```

O Selenium baixa sozinho o chromedriver compatível com o seu Chrome.

## Usar

```bash
python listar_seguidores.py nome_do_perfil                    # seguidores e seguindo
python listar_seguidores.py nome_do_perfil --tipo seguidores  # só seguidores
python listar_seguidores.py nome_do_perfil --sem-fotos        # não baixa as fotos
```

Na primeira vez, o Chrome abre na tela de login do Instagram: entre com a sua conta **no navegador**
(a senha nunca passa pelo script) e aperte Enter no terminal. O login fica guardado em
`.chrome-instagram/`, então das próximas vezes ele entra direto.

## O que sai

Em `saida/<perfil>/`:

| Arquivo | Conteúdo |
| --- | --- |
| `seguidores.csv`, `seguindo.csv` | usuário, nome, link da foto, arquivo da foto, privado, verificado, id. Separado por `;`, abre direto no Excel |
| `seguidores.json`, `seguindo.json` | os mesmos dados em JSON |
| `seguidores.html`, `seguindo.html` | galeria com foto, @ e nome. Clique para abrir o perfil |
| `fotos/<usuario>.jpg` | foto de perfil de cada pessoa |

Os links de foto do Instagram expiram depois de alguns dias; os `.jpg` baixados ficam.

## Como funciona

1. Lê os dados do perfil (id, se é privado, total de seguidores/seguindo).
2. **Modo padrão:** pede a lista aos mesmos endereços que o site do Instagram usa quando você clica em
   "seguidores", de dentro do navegador logado, 25 pessoas por vez, com pausa de 2,5 a 5,5 s entre as páginas.
3. **Se isso falhar** (o Instagram muda essas chamadas de vez em quando), ele abre a janela de seguidores
   e rola a lista na tela até ela parar de crescer. Para forçar um modo: `--modo api` ou `--modo tela`.

Com menos de mil seguidores, cada lista leva cerca de 2 a 4 minutos.

## Cuidados

- **Perfil privado:** só funciona se você seguir a pessoa (o perfil te seguir não basta).
- **Bloqueio:** se o Instagram pedir para "esperar alguns minutos", o script para e salva o que já pegou.
  Espere algumas horas antes de tentar de novo. Não rode várias vezes seguidas nem para muitos perfis no mesmo dia.
- **Lista menor que o total:** o Instagram às vezes não entrega todo mundo (contas desativadas, restritas etc.).
  O script avisa quando o número coletado fica abaixo do total do perfil.
- **Privacidade:** a lista é dado pessoal de terceiros (LGPD). Guarde só para consulta e não versione
  `saida/` nem `.chrome-instagram/`: o `.gitignore` desta pasta já impede isso.
  Coleta automatizada também vai contra os Termos de Uso do Instagram; use com moderação.
