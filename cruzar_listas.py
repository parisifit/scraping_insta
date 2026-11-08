#!/usr/bin/env python3
"""
Cruza as listas de seguidores e de "seguindo" de um perfil (geradas pelo ler_pagina_salva.py)
e mostra quem está nas duas: pessoas que seguem o perfil e que o perfil também segue.

Uso:
    python cruzar_listas.py fulana          # lê saida/fulana/seguidores.json e seguindo.json
    python cruzar_listas.py --pasta caminho/da/pasta
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from ler_pagina_salva import PASTA, Pessoa, salvar


def carregar(arquivo: Path) -> list[Pessoa]:
    if not arquivo.is_file():
        sys.exit(f"Não achei {arquivo}. Gere essa lista antes com o ler_pagina_salva.py.")
    return [Pessoa(**p) for p in json.loads(arquivo.read_text(encoding="utf-8"))]


def main() -> None:
    ap = argparse.ArgumentParser(description="Mostra quem está nas listas de seguidores e de seguindo.")
    ap.add_argument("perfil", nargs="?", default="", help="@ do perfil (nome da pasta em saida/)")
    ap.add_argument("--pasta", type=Path, help="pasta com seguidores.json e seguindo.json")
    args = ap.parse_args()

    perfil = args.perfil.strip().lstrip("@").strip("/").lower()
    if not (perfil or args.pasta):
        sys.exit("Diga o perfil (ex.: python cruzar_listas.py fulana) ou a pasta com --pasta.")
    pasta = args.pasta or PASTA / "saida" / perfil

    seguidores = carregar(pasta / "seguidores.json")
    seguindo = {p.usuario.lower(): p for p in carregar(pasta / "seguindo.json")}

    # Mantém a ordem da lista de seguidores; completa nome e foto com a outra lista se faltar.
    mutuos = []
    for p in seguidores:
        outro = seguindo.get(p.usuario.lower())
        if outro:
            mutuos.append(Pessoa(
                usuario=p.usuario,
                nome=p.nome or outro.nome,
                foto_arquivo=p.foto_arquivo or outro.foto_arquivo,
                foto_url=p.foto_url or outro.foto_url,
            ))

    nome_perfil = perfil or pasta.name
    salvar(mutuos, pasta, "mutuos", nome_perfil,
           titulo=f"Seguem e são seguidos por @{nome_perfil}")
    print(f"{len(seguidores)} seguidores, {len(seguindo)} seguindo, {len(mutuos)} nas duas listas.")
    print(f"Planilha: {pasta / 'mutuos.csv'}")
    print(f"Galeria:  {pasta / 'mutuos.html'}")


if __name__ == "__main__":
    main()
