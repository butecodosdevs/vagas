"""Testes do gerador de conteúdo a partir de linhas da planilha."""

from pathlib import Path

import pytest

from contentgen import (
    CANDIDATO_HEADERS,
    DEFAULT_SHEET_ID,
    VAGA_HEADERS,
    HeaderMismatch,
    SheetError,
    conferir_cabecalho,
    normalizar_modalidade,
    rows_from_values,
    sanitizar_mensagem,
    should_publish,
    slug_from_id,
    sync_content,
    validar_urls,
)

CANDIDATO_HEADERS = [
    "id",
    "criado_em",
    "status",
    "nome",
    "cargo_senioridade",
    "stack",
    "resumo_experiencia",
    "links",
    "pretensao",
    "modalidade",
    "consentimento",
]

VAGA_HEADERS = [
    "id",
    "criado_em",
    "status",
    "empresa",
    "cargo_senioridade",
    "requisitos_obrigatorios",
    "experiencia_desejavel",
    "link_vaga",
    "modalidade",
    "contato",
    "consentimento",
]


def candidato(**overrides):
    row = {
        "id": "c-11111111-2222-4333-8444-555555555555",
        "criado_em": "2026-11-12T15:04:05-03:00",
        "status": "publicado",
        "nome": "Ana Exemplo",
        "cargo_senioridade": "Dev backend pleno",
        "stack": "Java, Quarkus",
        "resumo_experiencia": "Trabalha com APIs.",
        "links": "https://www.linkedin.com/in/ana-exemplo",
        "pretensao": "A combinar",
        "modalidade": "remoto",
        "consentimento": "sim",
    }
    row.update(overrides)
    return row


def vaga(**overrides):
    row = {
        "id": "v-aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee",
        "criado_em": "2026-11-10T09:00:00-03:00",
        "status": "publicado",
        "empresa": "Padaria Digital",
        "cargo_senioridade": "Pessoa engenheira de software pleno",
        "requisitos_obrigatorios": "Java e testes.",
        "experiencia_desejavel": "Quarkus.",
        "link_vaga": "https://example.com/vagas/backend",
        "modalidade": "híbrido",
        "contato": "vagas@example.com",
        "consentimento": "sim",
    }
    row.update(overrides)
    return row


def test_planilha_padrao_esta_documentada_no_codigo():
    assert DEFAULT_SHEET_ID == "1mMjsxHBRritkBUIEz4-TsNLBofVC7crG8WNrSwtegsQ"


def test_mapeia_colunas_pelo_nome_e_nao_pela_posicao():
    headers = list(reversed(CANDIDATO_HEADERS))
    values = ["sim", "remoto", "A combinar", "https://example.com/a", "APIs", "Java", "Dev", "Ana", "publicado", "2026-11-12T15:04:05-03:00", "c-1"]
    rows = rows_from_values([headers, values])
    assert rows[0]["nome"] == "Ana"
    assert rows[0]["id"] == "c-1"
    assert rows[0]["links"] == "https://example.com/a"
    assert rows[0]["consentimento"] == "sim"


def test_cabecalho_exato_na_ordem_documentada():
    assert conferir_cabecalho("Candidatos", CANDIDATO_HEADERS + [""], CANDIDATO_HEADERS) == CANDIDATO_HEADERS
    assert conferir_cabecalho("Vagas", list(VAGA_HEADERS), VAGA_HEADERS) == VAGA_HEADERS
    with pytest.raises(HeaderMismatch) as erro:
        conferir_cabecalho("Vagas", ["empresa", "id"], VAGA_HEADERS)
    assert "Vagas" in str(erro.value)
    assert "Esperado:" in str(erro.value)


def test_sanitizar_nao_deixa_vazar_chave():
    vazado = 'erro -----BEGIN PRIVATE KEY-----\nABC\n-----END PRIVATE KEY----- fim'
    assert "ABC" not in sanitizar_mensagem(vazado)
    assert "BEGIN PRIVATE KEY" not in sanitizar_mensagem(vazado)


def test_workflow_de_ci_nao_imprime_o_secret():
    texto = Path(__file__).resolve().parents[1].joinpath(".github/workflows/ci.yml").read_text(encoding="utf-8")
    assert "sheet-connectivity" in texto
    assert "secrets.GOOGLE_SERVICE_ACCOUNT_JSON" in texto
    assert "workflow_dispatch" in texto
    assert "pull_request" in texto
    assert "head.repo.full_name" in texto
    assert "echo \"$GOOGLE_SERVICE_ACCOUNT_JSON\"" not in texto
    assert "printenv" not in texto


def test_cabecalho_obrigatorio_ausente_falha():
    with pytest.raises(SheetError):
        rows_from_values([["id", "nome"], ["c-1", "Ana"]], required=CANDIDATO_HEADERS)


def test_linha_vazia_e_ignorada():
    rows = rows_from_values([CANDIDATO_HEADERS, [""] * len(CANDIDATO_HEADERS), ["c-1", "", "", "Ana"] + [""] * 7])
    assert len(rows) == 1
    assert rows[0]["id"] == "c-1"


def test_slug_estavel_e_seguro():
    assert slug_from_id("C-ABC") == slug_from_id("C-ABC")
    assert slug_from_id("C-ABC") == "c-abc"
    assert "/" not in slug_from_id("../../etc/passwd")
    assert "\\" not in slug_from_id("..\\windows")
    assert slug_from_id("Olá Mundo!") == "ola-mundo"
    assert slug_from_id("index") != "index"
    with pytest.raises(ValueError):
        slug_from_id("...")


def test_urls_validas_e_rejeita_javascript():
    assert validar_urls("https://example.com/vaga") == ["https://example.com/vaga"]
    assert validar_urls("javascript:alert(1)") == []
    assert validar_urls("data:text/html,hi") == []
    assert validar_urls("veja https://example.com/a, https://example.com/b.") == [
        "https://example.com/a",
        "https://example.com/b",
    ]
    assert validar_urls("") == []


def test_modalidade_hibrido_sem_acento():
    assert normalizar_modalidade("Hibrido") == "híbrido"
    assert normalizar_modalidade("híbrido") == "híbrido"
    assert normalizar_modalidade("Presencial") == "presencial"
    assert normalizar_modalidade("remoto") == "remoto"


@pytest.mark.parametrize(
    ("status", "moderacao", "esperado"),
    [
        ("publicado", False, True),
        ("pendente", False, True),
        ("aprovado", False, True),
        ("removido", False, False),
        ("", False, True),
        ("publicado", True, False),
        ("pendente", True, False),
        ("aprovado", True, True),
        ("removido", True, False),
        ("APROVADO", True, True),
    ],
)
def test_moderacao(status, moderacao, esperado):
    assert should_publish(status, moderacao) is esperado


def test_escaping_nao_injeta_html_nem_qute(tmp_path: Path):
    malicioso = 'Ana " <script>alert(1)</script>\n{#include evil}\n{=site.title}'
    content = tmp_path / "content"
    sync_content(
        content,
        [candidato(nome=malicioso, resumo_experiencia=malicioso)],
        [],
        moderation_enabled=False,
    )
    texto = (content / "candidatos" / f"{slug_from_id(candidato()['id'])}.md").read_text(encoding="utf-8")
    corpo = texto.split("---", 2)[2]
    assert "<script>" not in corpo
    assert "{=" not in texto
    assert "{#" not in texto
    assert 'nome: "' in texto
    assert "alert(1)" in texto
    assert "\\n" in texto.split("---", 2)[1]


def test_gera_vaga_e_candidato_com_slug_do_id(tmp_path: Path):
    content = tmp_path / "content"
    result = sync_content(content, [candidato()], [vaga()], moderation_enabled=False)
    slug_c = slug_from_id(candidato()["id"])
    slug_v = slug_from_id(vaga()["id"])
    assert (content / "candidatos" / f"{slug_c}.md").is_file()
    assert (content / "vagas" / f"{slug_v}.md").is_file()
    vaga_txt = (content / "vagas" / f"{slug_v}.md").read_text(encoding="utf-8")
    assert "layout: vaga" in vaga_txt
    assert 'modalidade: "híbrido"' in vaga_txt
    assert "https://example.com/vagas/backend" in vaga_txt
    assert 'date: "2026-11-12 15:04:05 -0300"' in (content / "candidatos" / f"{slug_c}.md").read_text(encoding="utf-8")
    assert slug_c in result.written[0] or slug_v in result.written[0]


def test_removido_apaga_arquivo_e_preserva_exemplo(tmp_path: Path):
    content = tmp_path / "content"
    exemplo = content / "vagas" / "exemplo-vaga-backend.md"
    exemplo.parent.mkdir(parents=True)
    exemplo.write_text("---\nlayout: vaga\nexemplo: true\n---\n\nExemplo.\n", encoding="utf-8")
    slug = slug_from_id("v-remover")
    alvo = content / "vagas" / f"{slug}.md"
    alvo.write_text("---\nlayout: vaga\nexemplo: false\n---\n\nAntiga.\n", encoding="utf-8")
    sync_content(
        content,
        [],
        [vaga(id="v-remover", status="removido")],
        moderation_enabled=False,
    )
    assert not alvo.exists()
    assert exemplo.is_file()
    assert "Exemplo." in exemplo.read_text(encoding="utf-8")


def test_moderacao_ligada_so_publica_aprovado_e_remove_o_resto(tmp_path: Path):
    content = tmp_path / "content"
    sync_content(
        content,
        [],
        [
            vaga(id="v-ok", status="aprovado", empresa="Ok"),
            vaga(id="v-nao", status="publicado", empresa="Nao"),
            vaga(id="v-espera", status="pendente", empresa="Espera"),
        ],
        moderation_enabled=True,
    )
    assert (content / "vagas" / "v-ok.md").is_file()
    assert not (content / "vagas" / "v-nao.md").exists()
    assert not (content / "vagas" / "v-espera.md").exists()

    # Arquivo previamente publicado some quando a moderação passa a exigir aprovado.
    (content / "vagas" / "v-nao.md").write_text("velho\n", encoding="utf-8")
    sync_content(
        content,
        [],
        [vaga(id="v-nao", status="publicado")],
        moderation_enabled=True,
    )
    assert not (content / "vagas" / "v-nao.md").exists()


def test_sem_consentimento_nao_publica(tmp_path: Path):
    content = tmp_path / "content"
    slug = slug_from_id(candidato()["id"])
    alvo = content / "candidatos" / f"{slug}.md"
    alvo.parent.mkdir(parents=True)
    alvo.write_text("velho\n", encoding="utf-8")
    sync_content(content, [candidato(consentimento="não")], [], moderation_enabled=False)
    assert not alvo.exists()


def test_moderacao_desligada_publica_pendente_e_publicado(tmp_path: Path):
    content = tmp_path / "content"
    sync_content(
        content,
        [
            candidato(id="c-pub", status="publicado"),
            candidato(id="c-pen", status="pendente", nome="Pendente"),
        ],
        [],
        moderation_enabled=False,
    )
    assert (content / "candidatos" / "c-pub.md").is_file()
    assert (content / "candidatos" / "c-pen.md").is_file()
