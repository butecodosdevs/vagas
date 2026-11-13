#!/usr/bin/env python3
"""Confere links e recursos internos do site gerado, sem rede externa."""

from __future__ import annotations

import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse

RAIZ = Path(__file__).resolve().parents[1]
SAIDA = RAIZ / "target" / "roq"
PREFIXO = "/vagas"
ORIGEM = "https://butecodosdevs.github.io"


class _Coletor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.refs: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        valores = {nome: valor for nome, valor in attrs if valor}
        for chave in ("href", "src", "content"):
            valor = valores.get(chave)
            if not valor:
                continue
            if chave == "content" and not (
                valor.startswith("/") or valor.startswith("http://") or valor.startswith("https://")
            ):
                continue
            self.refs.append(valor)


def eh_interno(referencia: str, origem: str = ORIGEM, prefixo: str = PREFIXO) -> bool:
    texto = (referencia or "").strip()
    if not texto or texto.startswith("#") or texto.startswith("//"):
        return False
    analisado = urlparse(texto)
    esquema = analisado.scheme.lower()
    if esquema in {"mailto", "tel", "javascript", "data"}:
        return False
    if esquema in {"http", "https"}:
        if not origem:
            return False
        if analisado.netloc.lower() != urlparse(origem).netloc.lower():
            return False
        caminho = analisado.path or "/"
        base = prefixo.rstrip("/") or "/"
        return caminho == base or caminho.startswith(base + "/")
    return True


def arquivo_do_link(referencia: str, saida: Path, prefixo: str = PREFIXO) -> Path | None:
    caminho = urlparse(referencia).path
    if not caminho.startswith(prefixo):
        return None
    resto = caminho[len(prefixo) :].lstrip("/")
    candidato = (saida / resto).resolve()
    base = saida.resolve()
    if base != candidato and base not in candidato.parents:
        return None
    if candidato.is_dir():
        return candidato / "index.html"
    if candidato.is_file():
        return candidato
    indice = candidato / "index.html"
    if indice.is_file():
        return indice
    return None


def verificar(saida: Path = SAIDA, prefixo: str = PREFIXO, origem: str = ORIGEM) -> list[str]:
    faltando: list[str] = []
    for html in saida.rglob("*.html"):
        coletor = _Coletor()
        coletor.feed(html.read_text(encoding="utf-8"))
        for referencia in coletor.refs:
            if not eh_interno(referencia, origem, prefixo):
                continue
            destino = arquivo_do_link(referencia, saida, prefixo)
            if destino is None or not destino.is_file():
                faltando.append(f"{html.relative_to(saida)} -> {referencia}")
    return faltando


def main() -> int:
    if not SAIDA.is_dir():
        print(f"Site gerado não encontrado em {SAIDA}", file=sys.stderr)
        return 1
    faltando = verificar()
    if faltando:
        print("Links internos quebrados:", file=sys.stderr)
        for item in faltando:
            print(f"  {item}", file=sys.stderr)
        return 1
    print(f"Links internos ok em {SAIDA}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
