#!/usr/bin/env python3
"""Lê as abas Candidatos e Vagas e atualiza content/ no repositório.

Variáveis:
  GOOGLE_SERVICE_ACCOUNT_JSON  JSON da conta de serviço (obrigatório)
  SHEET_ID                      id da planilha (padrão: a planilha do Buteco)
  MODERATION_ENABLED            true publica só status aprovado (padrão: false)
  VAGA_MAX_DIAS                 vaga mais velha que isto sai do mural (padrão: 60)
"""

from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path

from contentgen import (
    CANDIDATO_HEADERS,
    DEFAULT_SHEET_ID,
    VAGA_HEADERS,
    dias_maximos_vaga,
    rows_from_values,
    sanitizar_mensagem,
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


def relatar_falha(erro: BaseException) -> int:
    """Imprime o erro já filtrado. A chave da conta de serviço não entra no log."""
    print(sanitizar_mensagem(f"Não foi possível sincronizar: {erro}"), file=sys.stderr)
    return 1


def main() -> int:
    logging.getLogger("googleapiclient").setLevel(logging.ERROR)
    logging.getLogger("google.auth").setLevel(logging.ERROR)
    try:
        return _executar()
    except Exception as erro:  # noqa: BLE001 — a mensagem passa pelo filtro de segredo
        return relatar_falha(erro)


def _executar() -> int:
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
    limite = dias_maximos_vaga(os.environ.get("VAGA_MAX_DIAS"))
    resultado = sync_content(raiz, candidatos, vagas, moderation_enabled(), max_dias_vaga=limite)
    print(f"Planilha {identificador}")
    print(f"Moderação: {'ligada' if moderation_enabled() else 'desligada'}")
    print(f"Vaga expira depois de {limite} dias")
    print(
        f"Escritos: {len(resultado.written)}; "
        f"removidos: {len(resultado.removed)}; "
        f"ignorados: {len(resultado.skipped)}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
