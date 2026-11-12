#!/usr/bin/env python3
"""Lê as abas Candidatos e Vagas e atualiza content/ no repositório.

Variáveis:
  GOOGLE_SERVICE_ACCOUNT_JSON  JSON da conta de serviço (obrigatório)
  SHEET_ID                      id da planilha (padrão: a planilha do Buteco)
  MODERATION_ENABLED            true publica só status aprovado (padrão: false)
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from contentgen import (
    CANDIDATO_HEADERS,
    DEFAULT_SHEET_ID,
    VAGA_HEADERS,
    rows_from_values,
    sync_content,
)

SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]
_VERDADEIRO = {"1", "true", "yes", "on", "sim"}


def moderation_enabled() -> bool:
    return os.environ.get("MODERATION_ENABLED", "false").strip().lower() in _VERDADEIRO


def sheet_id() -> str:
    return os.environ.get("SHEET_ID", "").strip() or DEFAULT_SHEET_ID


def fetch_tab(service, spreadsheet_id: str, aba: str, obrigatorios: list[str]) -> list[dict[str, str]]:
    resposta = (
        service.spreadsheets()
        .values()
        .get(
            spreadsheetId=spreadsheet_id,
            range=f"'{aba}'",
            valueRenderOption="FORMATTED_VALUE",
        )
        .execute()
    )
    return rows_from_values(resposta.get("values", []), required=obrigatorios)


def main() -> int:
    bruto = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON", "").strip()
    if not bruto:
        print("Defina o secret GOOGLE_SERVICE_ACCOUNT_JSON.", file=sys.stderr)
        return 1
    try:
        info = json.loads(bruto)
    except json.JSONDecodeError:
        print("GOOGLE_SERVICE_ACCOUNT_JSON não é um JSON válido.", file=sys.stderr)
        return 1

    from google.oauth2 import service_account
    from googleapiclient.discovery import build

    credenciais = service_account.Credentials.from_service_account_info(info, scopes=SCOPES)
    servico = build("sheets", "v4", credentials=credenciais, cache_discovery=False)
    identificador = sheet_id()
    candidatos = fetch_tab(servico, identificador, "Candidatos", CANDIDATO_HEADERS)
    vagas = fetch_tab(servico, identificador, "Vagas", VAGA_HEADERS)
    raiz = Path(__file__).resolve().parents[1] / "content"
    resultado = sync_content(raiz, candidatos, vagas, moderation_enabled())
    print(f"Planilha {identificador}")
    print(f"Moderação: {'ligada' if moderation_enabled() else 'desligada'}")
    print(
        f"Escritos: {len(resultado.written)}; "
        f"removidos: {len(resultado.removed)}; "
        f"ignorados: {len(resultado.skipped)}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
