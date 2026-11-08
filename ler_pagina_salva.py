#!/usr/bin/env python3
"""
Lê uma página do Instagram salva no navegador (com a lista de seguidores ou de "seguindo"
aberta e rolada até o fim) e gera a lista com nome de usuário, nome e foto de perfil.

Não acessa o Instagram: só lê o arquivo salvo no seu computador. As fotos vêm da pasta
que o navegador salva junto com a página; se faltar alguma, ela é baixada pelo link.

Uso:
    python ler_pagina_salva.py seguidores.html
    python ler_pagina_salva.py seguindo.html --tipo seguindo
    python ler_pagina_salva.py pagina.html --tipo seguidores --perfil fulana
"""

from __future__ import annotations

import argparse
import csv
import html
import json
import re
import shutil
import sys
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path
from urllib.parse import unquote, urlparse

from bs4 import BeautifulSoup, Tag

PASTA = Path(__file__).resolve().parent
BASE = "https://www.instagram.com"

# Textos dos botões e marcadores que aparecem em cada linha da lista, não são nomes.
IGNORAR = {
    "Seguir", "Seguindo", "Remover", "Solicitado", "Seguir de volta", "·", "•", "Verificado",
    "Follow", "Following", "Remove", "Requested", "Follow Back", "Verified",
}
# Caminhos do Instagram que não são perfis.
NAO_PERFIL = {
    "explore", "reels", "reel", "p", "stories", "direct", "accounts", "about", "legal",
    "developer", "web", "challenge", "emails", "privacy", "help", "tv",
}
USUARIO = re.compile(r"^[A-Za-z0-9._]{1,30}$")


@dataclass
class Pessoa:
    usuario: str
    nome: str
    foto_arquivo: str = ""
    foto_url: str = ""


def usuario_do_link(href: str) -> str | None:
    """'/fulana/' ou 'https://www.instagram.com/fulana/' -> 'fulana'."""
    url = urlparse(href or "")
    if url.netloc and "instagram.com" not in url.netloc:
        return None
    partes = [p for p in url.path.split("/") if p]
    if len(partes) != 1:
        return None
    nome = partes[0]
    if nome.lower() in NAO_PERFIL or not USUARIO.match(nome):
        return None
    return nome


def textos_folha(el: Tag) -> list[str]:
    """Textos dos elementos sem filhos dentro da linha."""
    saida = []
    for filho in el.find_all(True):
        if filho.find(True) is None:
            t = filho.get_text(" ", strip=True)
            if t:
                saida.append(t)
    return saida


def ler_lista(arquivo: Path) -> list[tuple[str, str, str]]:
    sopa = BeautifulSoup(arquivo.read_text(encoding="utf-8", errors="replace"), "html.parser")
    dialogos = sopa.select('div[role="dialog"]')
    if not dialogos:
        sys.exit("Não achei a janela de seguidores nessa página. Salve a página com a lista ABERTA "
                 "(depois de clicar em \"seguidores\" ou \"seguindo\" e rolar até o fim).")
    # Se houver mais de uma janela, a da lista é a que tem mais fotos.
    dialogo = max(dialogos, key=lambda d: len(d.find_all("img")))

    vistos: dict[str, tuple[str, str, str]] = {}
    for img in dialogo.find_all("img"):
        linha, usuario = img.parent, None
        for _ in range(8):
            if linha is None or linha is dialogo:
                break
            for a in linha.find_all("a", href=True):
                u = usuario_do_link(a["href"])
                if u and a.get_text(strip=True):
                    usuario = u
                    break
            if usuario:
                break
            linha = linha.parent
        if not usuario or usuario in vistos:
            continue
        textos = [t for t in textos_folha(linha) if t not in IGNORAR and t != usuario]
        vistos[usuario] = (usuario, textos[0] if textos else "", img.get("src", ""))
    return list(vistos.values())


def guardar_foto(src: str, pagina: Path, destino: Path) -> str:
    """Copia a foto salva pelo navegador ou, se não houver, baixa pelo link. Devolve o link original."""
    if not src:
        return ""
    url = urlparse(src)
    if url.scheme in ("http", "https"):
        if not destino.exists():
            try:
                req = urllib.request.Request(src, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req, timeout=20) as r:
                    destino.write_bytes(r.read())
            except OSError as e:
                print(f"  foto de {destino.stem} não baixou ({e})")
        return src
    if url.scheme in ("", "file"):
        local = Path(unquote(url.path))
        if not local.is_absolute():
            local = pagina.parent / local
        if local.is_file():
            shutil.copyfile(local, destino)
        else:
            print(f"  foto de {destino.stem} não está na pasta salva ({local.name})")
    return ""


def salvar(pessoas: list[Pessoa], pasta: Path, tipo: str, perfil: str) -> None:
    campos = list(Pessoa.__dataclass_fields__)
    # ";" e utf-8 com BOM para o Excel em português abrir em colunas e com acentos.
    with open(pasta / f"{tipo}.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=campos, delimiter=";")
        w.writeheader()
        w.writerows(asdict(p) for p in pessoas)
    (pasta / f"{tipo}.json").write_text(
        json.dumps([asdict(p) for p in pessoas], ensure_ascii=False, indent=2), encoding="utf-8"
    )
    titulo = f"{tipo.capitalize()}" + (f" de @{perfil}" if perfil else "")
    cartoes = "\n".join(
        f'<a class="c" href="{BASE}/{html.escape(p.usuario)}/" target="_blank">'
        f'<img src="{html.escape(p.foto_arquivo or p.foto_url)}" alt="" loading="lazy">'
        f"<b>@{html.escape(p.usuario)}</b><span>{html.escape(p.nome)}</span></a>"
        for p in pessoas
    )
    (pasta / f"{tipo}.html").write_text(
        f"""<!doctype html><meta charset="utf-8"><title>{html.escape(titulo)}</title>
<style>body{{font-family:system-ui,sans-serif;margin:24px;background:#fafafa}}
.g{{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:12px}}
.c{{display:flex;flex-direction:column;align-items:center;gap:4px;padding:12px;background:#fff;
border:1px solid #ddd;border-radius:10px;text-decoration:none;color:#222;text-align:center}}
.c img{{width:80px;height:80px;border-radius:50%;object-fit:cover;background:#eee}}
.c b{{font-size:14px;word-break:break-all}}.c span{{font-size:13px;color:#666}}</style>
<h1>{html.escape(titulo)} ({len(pessoas)})</h1><div class="g">{cartoes}</div>""",
        encoding="utf-8",
    )


def main() -> None:
    ap = argparse.ArgumentParser(description="Gera a lista de seguidores a partir de uma página salva do Instagram.")
    ap.add_argument("pagina", type=Path, help="arquivo .html salvo pelo navegador")
    ap.add_argument("--tipo", choices=["seguidores", "seguindo"], default="seguidores",
                    help="qual lista estava aberta na página (só muda o nome dos arquivos)")
    ap.add_argument("--perfil", default="", help="@ do perfil, para nomear a pasta de saída")
    ap.add_argument("--saida", type=Path, default=PASTA / "saida")
    args = ap.parse_args()

    if not args.pagina.is_file():
        sys.exit(f"Arquivo não encontrado: {args.pagina}")
    perfil = args.perfil.strip().lstrip("@").strip("/").lower()
    pasta = args.saida / (perfil or args.pagina.stem)
    fotos = pasta / "fotos"
    fotos.mkdir(parents=True, exist_ok=True)

    pessoas = []
    for usuario, nome, src in ler_lista(args.pagina):
        destino = fotos / f"{usuario}.jpg"
        url = guardar_foto(src, args.pagina, destino)
        pessoas.append(Pessoa(
            usuario=usuario,
            nome=nome,
            foto_arquivo=f"fotos/{destino.name}" if destino.exists() else "",
            foto_url=url,
        ))
    if not pessoas:
        sys.exit("A janela foi encontrada, mas não li nenhuma pessoa nela. Me mande a página para ajustar.")

    salvar(pessoas, pasta, args.tipo, perfil)
    sem_foto = sum(1 for p in pessoas if not p.foto_arquivo)
    print(f"{len(pessoas)} {args.tipo} lidos" + (f" ({sem_foto} sem foto)" if sem_foto else "") + ".")
    print(f"Planilha: {pasta / (args.tipo + '.csv')}")
    print(f"Galeria:  {pasta / (args.tipo + '.html')}")


if __name__ == "__main__":
    main()
