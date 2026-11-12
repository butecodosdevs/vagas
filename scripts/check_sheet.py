#!/usr/bin/env python3
"""Confere, só lendo, a linha 1 das abas Candidatos e Vagas.

Não imprime o JSON da conta de serviço nem a chave privada.
"""

from __future__ import annotations

import json
import logging
import os
import sys

from contentgen import (
    CANDIDATO_HEADERS,
    DEFAULT_SHEET_ID,
    VAGA_HEADERS,
    HeaderMismatch,
    conferir_cabecalho,
    sanitizar_mensagem,
)

SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]
ABAS = (
    ("Candidatos", CANDIDATO_HEADERS),
    ("Vagas", VAGA_HEADERS),
)


def _falha(mensagem: str) -> int:
    print(sanitizar_mensagem(mensagem), file=sys.stderr)
    return 1


def ler_linha_1(service, spreadsheet_id: str, aba: str) -> list[object]:
    resposta = (
        service.spreadsheets()
        .values()
        .get(
            spreadsheetId=spreadsheet_id,
            range=f"'{aba}'!1:1",
            valueRenderOption="FORMATTED_VALUE",
        )
        .execute()
    )
    valores = resposta.get("values") or []
    if not valores:
        return []
    return valores[0]


def main() -> int:
    logging.getLogger("googleapiclient").setLevel(logging.ERROR)
    logging.getLogger("google.auth").setLevel(logging.ERROR)

    bruto = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON", "").strip()
    if not bruto:
        return _falha(
            "Secret GOOGLE_SERVICE_ACCOUNT_JSON ausente. "
            "A checagem só roda em PR do próprio repositório ou em workflow_dispatch."
        )
    try:
        info = json.loads(bruto)
    except json.JSONDecodeError:
        return _falha("GOOGLE_SERVICE_ACCOUNT_JSON não é um JSON válido.")
    if not isinstance(info, dict) or "client_email" not in info or "private_key" not in info:
        return _falha("GOOGLE_SERVICE_ACCOUNT_JSON não parece uma conta de serviço.")

    identificador = os.environ.get("SHEET_ID", "").strip() or DEFAULT_SHEET_ID
    print(f"Checagem somente leitura da planilha {identificador}.")

    try:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build

        credenciais = service_account.Credentials.from_service_account_info(info, scopes=SCOPES)
        servico = build("sheets", "v4", credentials=credenciais, cache_discovery=False)
        for aba, esperado in ABAS:
            linha = ler_linha_1(servico, identificador, aba)
            conferido = conferir_cabecalho(aba, linha, esperado)
            print(f"Aba {aba}: cabeçalho confere ({len(conferido)} colunas): {', '.join(conferido)}")
    except HeaderMismatch as erro:
        return _falha(str(erro))
    except Exception as erro:  # noqa: BLE001 — a mensagem passa pelo filtro de segredo
        return _falha(f"Não foi possível autenticar ou ler a planilha: {erro}")

    print("Autenticação com a conta de serviço: ok. Cabeçalhos lidos e conferidos.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
