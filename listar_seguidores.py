#!/usr/bin/env python3
"""
Lista os seguidores e/ou quem um perfil do Instagram segue, usando o Chrome via Selenium
com a SUA conta logada. Para cada pessoa salva: nome de usuário, nome e foto de perfil.

Uso:
    python listar_seguidores.py <usuario>                  # seguidores e seguindo
    python listar_seguidores.py <usuario> --tipo seguidores
    python listar_seguidores.py <usuario> --sem-fotos      # não baixa as fotos

Na primeira execução o Chrome abre na tela de login: entre com a sua conta no navegador
e volte ao terminal. O login fica guardado na pasta .chrome-instagram (não vai para o git).

Como funciona: depois do login, o script pede as listas aos mesmos endereços que o site do
Instagram usa quando você abre "seguidores" na tela, de dentro do próprio navegador, em
páginas pequenas e com pausas. Se isso falhar, ele abre a janela de seguidores e rola a
lista na tela (modo "tela"), que é mais lento e mais sujeito a mudanças no site.
"""

from __future__ import annotations

import argparse
import csv
import html
import json
import random
import sys
import time
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path
from urllib.parse import quote

from selenium import webdriver
from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

PASTA = Path(__file__).resolve().parent
BASE = "https://www.instagram.com"
# Identificador público do aplicativo web do Instagram, enviado pelo próprio site em toda chamada.
IG_APP_ID = "936619743392459"
POR_PAGINA = 25

TIPOS = {"seguidores": "followers", "seguindo": "following"}


@dataclass
class Pessoa:
    usuario: str
    nome: str
    foto_url: str
    foto_arquivo: str = ""
    privado: bool | None = None
    verificado: bool | None = None
    id: str = ""


class Bloqueio(Exception):
    """O Instagram pediu para esperar ou recusou a chamada."""


def pausa(minimo: float, maximo: float) -> None:
    time.sleep(random.uniform(minimo, maximo))


# --------------------------------------------------------------------------- navegador


def abrir_navegador(pasta_perfil: Path) -> webdriver.Chrome:
    opcoes = webdriver.ChromeOptions()
    opcoes.add_argument(f"--user-data-dir={pasta_perfil}")
    opcoes.add_argument("--lang=pt-BR")
    opcoes.add_argument("--window-size=1200,900")
    driver = webdriver.Chrome(options=opcoes)  # o Selenium Manager baixa o chromedriver certo
    driver.set_script_timeout(60)
    return driver


def garantir_login(driver: webdriver.Chrome) -> None:
    driver.get(BASE + "/")
    pausa(2, 3)
    if driver.get_cookie("sessionid"):
        print("Sessão do Instagram encontrada.")
        return
    driver.get(BASE + "/accounts/login/")
    print("\nFaça login no Instagram na janela do Chrome que abriu.")
    print("(Se pedir código de verificação, conclua por lá.)")
    input("Quando a sua página inicial aparecer, aperte Enter aqui... ")
    if not driver.get_cookie("sessionid"):
        sys.exit("Não encontrei o login. Rode de novo e entre com a sua conta no navegador.")


JS_FETCH = """
const url = arguments[0], appId = arguments[1], done = arguments[arguments.length - 1];
const csrf = (document.cookie.match(/csrftoken=([^;]+)/) || [])[1] || "";
fetch(url, {
  credentials: "include",
  headers: {"X-IG-App-ID": appId, "X-CSRFToken": csrf, "X-Requested-With": "XMLHttpRequest"},
})
  .then(r => r.text().then(t => done({status: r.status, body: t})))
  .catch(e => done({status: 0, body: String(e)}));
"""


def buscar_json(driver: webdriver.Chrome, caminho: str) -> dict:
    resp = driver.execute_async_script(JS_FETCH, BASE + caminho, IG_APP_ID)
    status, corpo = resp["status"], resp["body"]
    try:
        dados = json.loads(corpo)
    except ValueError:
        dados = {}
    if status == 429 or dados.get("spam") or "wait a few minutes" in corpo.lower():
        raise Bloqueio("o Instagram pediu para esperar alguns minutos")
    if status != 200 or not dados:
        raise Bloqueio(f"resposta {status}: {corpo[:200]}")
    return dados


# --------------------------------------------------------------------------- modo api


def info_perfil(driver: webdriver.Chrome, usuario: str) -> dict:
    dados = buscar_json(driver, f"/api/v1/users/web_profile_info/?username={quote(usuario)}")
    u = (dados.get("data") or {}).get("user")
    if not u:
        sys.exit(f"Perfil @{usuario} não encontrado.")
    return {
        "id": u["id"],
        "nome": u.get("full_name", ""),
        "privado": u.get("is_private", False),
        "eu_sigo": u.get("followed_by_viewer", False),
        "seguidores": (u.get("edge_followed_by") or {}).get("count"),
        "seguindo": (u.get("edge_follow") or {}).get("count"),
    }


def listar_api(driver: webdriver.Chrome, user_id: str, tipo: str, total: int | None) -> list[Pessoa]:
    pessoas: dict[str, Pessoa] = {}
    max_id = ""
    while True:
        caminho = f"/api/v1/friendships/{user_id}/{TIPOS[tipo]}/?count={POR_PAGINA}"
        if tipo == "seguidores":
            caminho += "&search_surface=follow_list_page"
        if max_id:
            caminho += f"&max_id={quote(str(max_id))}"
        try:
            dados = buscar_json(driver, caminho)
        except Bloqueio as e:
            if not pessoas:
                raise
            print(f"\n  Parei antes do fim: {e}. Salvando o que já veio.")
            break
        for u in dados.get("users", []):
            pessoas[u["username"]] = Pessoa(
                usuario=u["username"],
                nome=u.get("full_name", ""),
                foto_url=u.get("profile_pic_url", ""),
                privado=u.get("is_private"),
                verificado=u.get("is_verified"),
                id=str(u.get("pk") or u.get("id") or ""),
            )
        print(f"\r  {tipo}: {len(pessoas)}" + (f" de {total}" if total else ""), end="", flush=True)
        max_id = dados.get("next_max_id")
        if not max_id or not dados.get("users"):
            break
        pausa(2.5, 5.5)
    print()
    return list(pessoas.values())


# --------------------------------------------------------------------------- modo tela

JS_LER_DIALOGO = """
const dialogo = document.querySelector('div[role="dialog"]');
if (!dialogo) return [];
const ignorar = new Set(["Seguir", "Seguindo", "Remover", "Solicitado", "·", "Follow",
                         "Following", "Remove", "Requested", "Verificado", "Verified"]);
const vistos = {};
for (const img of dialogo.querySelectorAll("img")) {
  let linha = img.parentElement, link = null;
  for (let i = 0; i < 8 && linha && linha !== dialogo; i++) {
    link = [...linha.querySelectorAll('a[href^="/"]')]
      .find(a => /^\\/[A-Za-z0-9._]+\\/$/.test(a.getAttribute("href")) && a.innerText.trim());
    if (link) break;
    linha = linha.parentElement;
  }
  if (!link) continue;
  const usuario = link.getAttribute("href").slice(1, -1);
  if (vistos[usuario]) continue;
  // Pedaços de texto da linha (elementos sem filhos), tirando o @ e os botões.
  const textos = [...linha.querySelectorAll("*")]
    .filter(el => !el.children.length)
    .map(el => (el.textContent || "").trim())
    .filter(s => s && !ignorar.has(s) && s !== usuario);
  vistos[usuario] = {usuario, nome: textos[0] || "", foto_url: img.src};
}
return Object.values(vistos);
"""

JS_ROLAR = """
const dialogo = document.querySelector('div[role="dialog"]');
if (!dialogo) return -1;
const caixas = [...dialogo.querySelectorAll("div")].filter(d => {
  const s = getComputedStyle(d);
  return d.scrollHeight > d.clientHeight + 10 && /(auto|scroll)/.test(s.overflowY);
});
if (!caixas.length) return -1;
const caixa = caixas.sort((a, b) => b.scrollHeight - a.scrollHeight)[0];
caixa.scrollTop = caixa.scrollHeight;
return caixa.scrollHeight;
"""


def listar_tela(driver: webdriver.Chrome, usuario: str, tipo: str, total: int | None) -> list[Pessoa]:
    caminho = "followers" if tipo == "seguidores" else "following"
    driver.get(f"{BASE}/{usuario}/")
    try:
        link = WebDriverWait(driver, 15).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, f'a[href="/{usuario}/{caminho}/"]'))
        )
        link.click()
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, 'div[role="dialog"] img'))
        )
    except TimeoutException:
        sys.exit(f"Não consegui abrir a lista de {tipo} na tela.")

    pessoas: dict[str, Pessoa] = {}
    sem_novidade = 0
    while sem_novidade < 6:
        antes = len(pessoas)
        for p in driver.execute_script(JS_LER_DIALOGO):
            pessoas.setdefault(p["usuario"], Pessoa(**p))
        print(f"\r  {tipo}: {len(pessoas)}" + (f" de {total}" if total else ""), end="", flush=True)
        if total and len(pessoas) >= total:
            break
        sem_novidade = sem_novidade + 1 if len(pessoas) == antes else 0
        if driver.execute_script(JS_ROLAR) == -1:
            break
        pausa(1.5, 3.5)
    print()
    return list(pessoas.values())


# --------------------------------------------------------------------------- saída


def baixar_fotos(pessoas: list[Pessoa], pasta: Path) -> None:
    pasta.mkdir(parents=True, exist_ok=True)
    for i, p in enumerate(pessoas, 1):
        if not p.foto_url:
            continue
        destino = pasta / f"{p.usuario}.jpg"
        if not destino.exists():
            try:
                req = urllib.request.Request(p.foto_url, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req, timeout=20) as r:
                    destino.write_bytes(r.read())
                pausa(0.2, 0.6)
            except OSError as e:
                print(f"\n  foto de @{p.usuario} falhou: {e}")
                continue
        p.foto_arquivo = str(destino.relative_to(pasta.parent))
        print(f"\r  fotos: {i}/{len(pessoas)}", end="", flush=True)
    print()


def salvar(pessoas: list[Pessoa], pasta: Path, tipo: str, alvo: str) -> None:
    campos = list(Pessoa.__dataclass_fields__)
    # ";" e utf-8 com BOM para o Excel em português abrir em colunas e com acentos.
    with open(pasta / f"{tipo}.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=campos, delimiter=";")
        w.writeheader()
        w.writerows(asdict(p) for p in pessoas)
    (pasta / f"{tipo}.json").write_text(
        json.dumps([asdict(p) for p in pessoas], ensure_ascii=False, indent=2), encoding="utf-8"
    )

    cartoes = "\n".join(
        f'<a class="c" href="{BASE}/{html.escape(p.usuario)}/" target="_blank">'
        f'<img src="{html.escape(p.foto_arquivo or p.foto_url)}" alt="" loading="lazy">'
        f"<b>@{html.escape(p.usuario)}</b><span>{html.escape(p.nome)}</span></a>"
        for p in pessoas
    )
    (pasta / f"{tipo}.html").write_text(
        f"""<!doctype html><meta charset="utf-8"><title>{tipo} de @{html.escape(alvo)}</title>
<style>body{{font-family:system-ui,sans-serif;margin:24px;background:#fafafa}}
.g{{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:12px}}
.c{{display:flex;flex-direction:column;align-items:center;gap:4px;padding:12px;background:#fff;
border:1px solid #ddd;border-radius:10px;text-decoration:none;color:#222;text-align:center}}
.c img{{width:80px;height:80px;border-radius:50%;object-fit:cover;background:#eee}}
.c b{{font-size:14px;word-break:break-all}}.c span{{font-size:13px;color:#666}}</style>
<h1>{tipo.capitalize()} de @{html.escape(alvo)} ({len(pessoas)})</h1><div class="g">{cartoes}</div>""",
        encoding="utf-8",
    )


# --------------------------------------------------------------------------- principal


def main() -> None:
    ap = argparse.ArgumentParser(description="Lista seguidores e/ou seguindo de um perfil do Instagram.")
    ap.add_argument("usuario", help="nome de usuário do perfil, sem @")
    ap.add_argument("--tipo", choices=["seguidores", "seguindo", "ambos"], default="ambos")
    ap.add_argument("--modo", choices=["auto", "api", "tela"], default="auto",
                    help="auto: tenta pelas chamadas do site e cai para a rolagem na tela se falhar")
    ap.add_argument("--sem-fotos", action="store_true", help="não baixa as fotos de perfil")
    ap.add_argument("--saida", type=Path, default=PASTA / "saida")
    ap.add_argument("--perfil-chrome", type=Path, default=PASTA / ".chrome-instagram")
    args = ap.parse_args()

    alvo = args.usuario.strip().lstrip("@").strip("/").lower()
    tipos = ["seguidores", "seguindo"] if args.tipo == "ambos" else [args.tipo]
    pasta = args.saida / alvo
    pasta.mkdir(parents=True, exist_ok=True)

    try:
        driver = abrir_navegador(args.perfil_chrome)
    except WebDriverException as e:
        sys.exit(f"Não consegui abrir o Chrome: {e.msg}\n"
                 "Feche outras janelas do Chrome que usem a pasta .chrome-instagram e tente de novo.")

    try:
        garantir_login(driver)
        info = None
        try:
            info = info_perfil(driver, alvo)
            print(f"@{alvo} ({info['nome']}): {info['seguidores']} seguidores, {info['seguindo']} seguindo")
            if info["privado"] and not info["eu_sigo"]:
                sys.exit("Esse perfil é privado e você não o segue: o Instagram não mostra as listas.")
        except Bloqueio as e:
            if args.modo == "api":
                sys.exit(f"Falhou: {e}")
            print(f"Não consegui ler o perfil pelas chamadas do site ({e}). Vou pela tela.")

        for i, tipo in enumerate(tipos):
            if i:
                pausa(8, 15)
            total = info[tipo] if info else None
            pessoas = None
            if info and args.modo in ("auto", "api"):
                try:
                    pessoas = listar_api(driver, info["id"], tipo, total)
                except Bloqueio as e:
                    if args.modo == "api":
                        sys.exit(f"Falhou: {e}")
                    print(f"\n  As chamadas do site falharam ({e}). Vou rolar a lista na tela.")
            if pessoas is None:
                pessoas = listar_tela(driver, alvo, tipo, total)

            if not args.sem_fotos:
                baixar_fotos(pessoas, pasta / "fotos")
            salvar(pessoas, pasta, tipo, alvo)
            falta = f" (o perfil mostra {total})" if total and len(pessoas) < total else ""
            print(f"  {len(pessoas)} {tipo}{falta} → {pasta / (tipo + '.csv')}")
    finally:
        driver.quit()

    print(f"\nPronto. Abra {pasta}/seguidores.html (ou seguindo.html) para ver com as fotos.")


if __name__ == "__main__":
    main()
