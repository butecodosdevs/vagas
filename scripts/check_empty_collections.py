#!/usr/bin/env python3
"""Gera o site sem nenhum documento e confere HTTP 200 com o estado vazio.

Tira os Markdown de content/vagas e content/candidatos, roda `roq generate`
e pede as listagens. Os arquivos voltam ao lugar mesmo se a geração falhar.
"""

from __future__ import annotations

import os
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import urlopen

RAIZ = Path(__file__).resolve().parents[1]
COLECOES = ("vagas", "candidatos")
VAZIO = {
    "vagas": "Ainda não há vagas publicadas.",
    "candidatos": "Ainda não há apresentações publicadas.",
}


def _porta_livre() -> int:
    with socket.socket() as soquete:
        soquete.bind(("127.0.0.1", 0))
        return soquete.getsockname()[1]


def _mover_documentos(backup: Path) -> list[tuple[Path, Path]]:
    movidos: list[tuple[Path, Path]] = []
    for colecao in COLECOES:
        origem_dir = RAIZ / "content" / colecao
        for origem in origem_dir.glob("*.md"):
            destino = backup / colecao / origem.name
            destino.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(origem, destino)
            movidos.append((destino, origem))
    return movidos


def _restaurar(movidos: list[tuple[Path, Path]]) -> None:
    for destino, origem in movidos:
        origem.parent.mkdir(parents=True, exist_ok=True)
        if destino.exists():
            shutil.move(destino, origem)


def _servir(diretorio: Path, porta: int) -> ThreadingHTTPServer:
    handler = partial(SimpleHTTPRequestHandler, directory=str(diretorio))
    servidor = ThreadingHTTPServer(("127.0.0.1", porta), handler)
    threading.Thread(target=servidor.serve_forever, daemon=True).start()
    return servidor


def _pagina(base: str, caminho: str) -> str:
    try:
        with urlopen(base + caminho, timeout=10) as resposta:
            status = resposta.status
            corpo = resposta.read().decode("utf-8")
    except HTTPError as erro:
        raise SystemExit(f"{caminho} respondeu HTTP {erro.code}") from erro
    if status != 200:
        raise SystemExit(f"{caminho} respondeu HTTP {status}")
    return corpo


def main() -> int:
    backup = Path(tempfile.mkdtemp(prefix="vagas-vazias-"))
    movidos = _mover_documentos(backup)
    if not movidos:
        print("Nenhum Markdown de vaga ou candidato para afastar.", file=sys.stderr)
    try:
        ambiente = os.environ.copy()
        ambiente["QUARKUS_ROQ_GENERATOR_BATCH"] = "true"
        subprocess.run(
            [str(RAIZ / "mvnw"), "-B", "package", "quarkus:run", "-DskipTests"],
            cwd=RAIZ,
            check=True,
            env=ambiente,
        )
        publicado = Path(tempfile.mkdtemp(prefix="vagas-http-"))
        shutil.copytree(RAIZ / "target" / "roq", publicado / "vagas")
        porta = _porta_livre()
        servidor = _servir(publicado, porta)
        base = f"http://127.0.0.1:{porta}/vagas/"
        try:
            home = _pagina(base, "")
            if "Vagas do Buteco" not in home:
                raise SystemExit("A home vazia não renderizou.")
            for colecao, texto in VAZIO.items():
                corpo = _pagina(base, f"{colecao}/")
                if texto not in corpo:
                    raise SystemExit(f"/{colecao}/ não mostrou o estado vazio.")
                if "sortByDate" in corpo:
                    raise SystemExit(f"/{colecao}/ deixou a expressão Qute no HTML.")
                print(f"GET /vagas/{colecao}/ 200 — {texto}")
            print("GET /vagas/ 200")
        finally:
            servidor.shutdown()
    finally:
        _restaurar(movidos)
    return 0


if __name__ == "__main__":
    sys.exit(main())
