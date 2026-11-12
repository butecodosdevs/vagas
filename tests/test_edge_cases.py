"""Casos de borda do gerador: injeção, unicode, limites, duplicatas e moderação."""

import re
from pathlib import Path

import pytest

from contentgen import (
    CANDIDATO_HEADERS,
    VAGA_HEADERS,
    SheetError,
    rows_from_values,
    slug_from_id,
    sync_content,
    validar_urls,
    yaml_quote,
)
from sync_sheet import moderation_enabled
from test_contentgen import candidato, vaga

INJECAO = [
    "<script>alert(1)</script>",
    '"><img src=x onerror=alert(1)>',
    "{=site.url}",
    "{#include evil}",
    "---\nlayout: default",
    'valor: "injetado"',
    "😀 cerveja & código",
    "ana\u2028status: publicado",
    "ana\u2029fim",
    "ana\u0085layout: x",
    "=\tHYPERLINK(\"http://evil.example\")",
    "javascript:alert(1)",
    "a](javascript:alert(1))",
]

_LINHA_FM = re.compile(r'^[a-z0-9_]+: (".*"|\[\]|true|false|[A-Za-z0-9_-]+)$')


def _frente_e_corpo(texto: str) -> tuple[str, str]:
    assert texto.startswith("---\n")
    fim = texto.index("\n---\n")
    return texto[4:fim], texto[fim + 5 :]


def assert_markdown_seguro(texto: str) -> None:
    frente, corpo = _frente_e_corpo(texto)
    assert "<script" not in corpo.lower()
    assert "onerror" not in corpo.lower()
    assert "javascript:" not in corpo.lower()
    assert "{=" not in texto
    assert "{#" not in texto
    assert "\u2028" not in texto
    assert "\u2029" not in texto
    assert "\u0085" not in texto
    for linha in frente.splitlines():
        if linha == "links:" or linha.startswith("  - "):
            if linha.startswith("  - "):
                assert linha.endswith('"')
            continue
        assert _LINHA_FM.fullmatch(linha), linha


@pytest.mark.parametrize("campo", [
    "nome",
    "cargo_senioridade",
    "stack",
    "resumo_experiencia",
    "links",
    "pretensao",
    "modalidade",
    "consentimento",
    "status",
    "id",
    "criado_em",
])
@pytest.mark.parametrize("carga", INJECAO)
def test_campo_de_candidato_nao_injeta_html_qute_nem_front_matter(tmp_path: Path, campo: str, carga: str):
    content = tmp_path / "content"
    linha = candidato(**{campo: carga})
    if campo == "nome":
        linha["nome"] = carga or "Ana"
    sync_content(content, [linha], [], moderation_enabled=False)
    slug = slug_from_id(linha["id"]) if campo != "id" else None
    arquivos = list((content / "candidatos").glob("*.md")) if (content / "candidatos").exists() else []
    if campo == "id":
        try:
            slug = slug_from_id(carga)
        except ValueError:
            assert arquivos == []
            return
    if not arquivos:
        return
    texto = arquivos[0].read_text(encoding="utf-8")
    assert_markdown_seguro(texto)
    if campo == "id":
        assert "<script>" not in texto
        assert "javascript:" not in texto


@pytest.mark.parametrize("campo", [
    "empresa",
    "cargo_senioridade",
    "requisitos_obrigatorios",
    "experiencia_desejavel",
    "link_vaga",
    "modalidade",
    "contato",
    "consentimento",
    "status",
    "id",
    "criado_em",
])
@pytest.mark.parametrize("carga", INJECAO)
def test_campo_de_vaga_nao_injeta_html_qute_nem_front_matter(tmp_path: Path, campo: str, carga: str):
    content = tmp_path / "content"
    linha = vaga(**{campo: carga})
    sync_content(content, [], [linha], moderation_enabled=False)
    arquivos = list((content / "vagas").glob("*.md")) if (content / "vagas").exists() else []
    if not arquivos:
        return
    assert_markdown_seguro(arquivos[0].read_text(encoding="utf-8"))


def test_url_com_html_ou_qute_nao_entra_no_markdown(tmp_path: Path):
    content = tmp_path / "content"
    links = " ".join([
        "https://evil.example/a)<script>alert(1)</script>",
        "https://evil.example/{=site.url}",
        "https://evil.example/{#include evil}",
        "javascript:alert(1)",
        "https://ok.example/ana",
    ])
    sync_content(content, [candidato(links=links)], [], moderation_enabled=False)
    texto = next((content / "candidatos").glob("*.md")).read_text(encoding="utf-8")
    assert_markdown_seguro(texto)
    assert "https://ok.example/ana" in texto
    assert "<script>" not in texto
    assert "site.url" not in texto
    _, corpo = _frente_e_corpo(texto)
    assert "<script>" not in corpo
    assert "{=" not in corpo
    assert 'href="https://ok.example/ana"' in corpo
    assert 'rel="noopener noreferrer"' in corpo


def test_validar_urls_rejeita_esquemas_e_quebras():
    assert validar_urls("javascript:alert(1)") == []
    assert validar_urls("https://evil.example/a)<script>alert(1)</script>") == []
    assert validar_urls("https://evil.example/{=site.url}") == []
    assert validar_urls('https://evil.example/a"onclick=alert(1)') == []
    assert validar_urls("https://ok.example/ana") == ["https://ok.example/ana"]
    assert validar_urls("https://ok.example/wiki/Foo_(bar)") == ["https://ok.example/wiki/Foo_(bar)"]


def test_yaml_quote_escapa_separadores_de_linha_unicode():
    citado = yaml_quote("a\u2028b\u2029c\u0085d")
    assert "\u2028" not in citado
    assert "\u2029" not in citado
    assert "\u0085" not in citado
    assert "\\u2028" in citado


def test_texto_muito_longo_e_cortado_e_emoji_permanece(tmp_path: Path):
    content = tmp_path / "content"
    marcador = "FIMLARGOUNICO"
    sync_content(
        content,
        [candidato(
            nome="Ana 😀 " + ("n" * 500),
            resumo_experiencia=("á" * 5000) + marcador,
            stack="Java ☕ " + ("s" * 800),
        )],
        [vaga(
            requisitos_obrigatorios=("r" * 5000) + marcador,
            contato=("c" * 500) + marcador,
        )],
        moderation_enabled=False,
    )
    candidato_txt = next((content / "candidatos").glob("*.md")).read_text(encoding="utf-8")
    vaga_txt = next((content / "vagas").glob("*.md")).read_text(encoding="utf-8")
    assert marcador not in candidato_txt
    assert marcador not in vaga_txt
    assert "😀" in candidato_txt
    assert "☕" in candidato_txt
    assert "…" in candidato_txt
    assert "…" in vaga_txt
    assert_markdown_seguro(candidato_txt)
    assert_markdown_seguro(vaga_txt)


def test_id_so_com_emoji_e_ignorado(tmp_path: Path):
    content = tmp_path / "content"
    resultado = sync_content(content, [candidato(id="😀🍺")], [], moderation_enabled=False)
    assert list((content / "candidatos").glob("*.md")) == []
    assert any(item.startswith("candidato:") for item in resultado.skipped)


def test_ids_duplicados_a_primeira_linha_vence(tmp_path: Path):
    content = tmp_path / "content"
    resultado = sync_content(
        content,
        [
            candidato(id="c-dup", nome="Primeiro"),
            candidato(id="C-DUP", nome="Segundo"),
        ],
        [],
        moderation_enabled=False,
    )
    texto = (content / "candidatos" / "c-dup.md").read_text(encoding="utf-8")
    assert "Primeiro" in texto
    assert "Segundo" not in texto
    assert "candidato:duplicado:c-dup" in resultado.skipped


def test_duplicado_depois_de_removido_nao_republica(tmp_path: Path):
    content = tmp_path / "content"
    alvo = content / "candidatos" / "c-dup.md"
    alvo.parent.mkdir(parents=True)
    alvo.write_text("velho\n", encoding="utf-8")
    resultado = sync_content(
        content,
        [
            candidato(id="c-dup", status="removido", nome="Some"),
            candidato(id="c-dup", status="publicado", nome="Volta"),
        ],
        [],
        moderation_enabled=False,
    )
    assert not alvo.exists()
    assert "Volta" not in resultado.written
    assert "candidato:duplicado:c-dup" in resultado.skipped


def test_slug_longo_nao_passa_de_80(tmp_path: Path):
    content = tmp_path / "content"
    bruto = "c-" + ("ab" * 100)
    sync_content(content, [candidato(id=bruto, nome="Longa")], [], moderation_enabled=False)
    arquivo = next((content / "candidatos").glob("*.md"))
    assert len(arquivo.stem) <= 80
    assert_markdown_seguro(arquivo.read_text(encoding="utf-8"))


def test_planilha_sem_linhas_e_coluna_ausente():
    with pytest.raises(SheetError):
        rows_from_values([], required=CANDIDATO_HEADERS)
    faltando = [nome for nome in VAGA_HEADERS if nome != "contato"]
    with pytest.raises(SheetError, match="contato"):
        rows_from_values([faltando, ["x"] * len(faltando)], required=VAGA_HEADERS)
    with pytest.raises(SheetError, match="cabeçalho"):
        rows_from_values([], required=CANDIDATO_HEADERS)


@pytest.mark.parametrize("moderacao", [False, True])
@pytest.mark.parametrize("tipo", ["candidato", "vaga"])
def test_status_removido_apaga_e_nao_recria(tmp_path: Path, moderacao: bool, tipo: str):
    content = tmp_path / "content"
    pasta = content / ("candidatos" if tipo == "candidato" else "vagas")
    slug = "c-sai" if tipo == "candidato" else "v-sai"
    alvo = pasta / f"{slug}.md"
    alvo.parent.mkdir(parents=True)
    alvo.write_text("velho\n", encoding="utf-8")
    linha = candidato(id=slug, status="removido") if tipo == "candidato" else vaga(id=slug, status="removido")
    kwargs = {"candidatos": [linha], "vagas": []} if tipo == "candidato" else {"candidatos": [], "vagas": [linha]}
    resultado = sync_content(content, moderation_enabled=moderacao, **kwargs)
    assert not alvo.exists()
    assert str(alvo) in resultado.removed
    assert not any(slug in item for item in resultado.written)


@pytest.mark.parametrize("valor,esperado", [
    ("true", True),
    ("TRUE", True),
    ("yes", True),
    ("on", True),
    ("sim", True),
    ("1", True),
    ("false", False),
    ("FALSE", False),
    ("", False),
    ("nao", False),
])
def test_flag_de_moderacao(monkeypatch, valor, esperado):
    monkeypatch.setenv("MODERATION_ENABLED", valor)
    assert moderation_enabled() is esperado


def test_moderacao_ligada_e_desligada_nos_dois_tipos(tmp_path: Path):
    content = tmp_path / "content"
    candidatos = [
        candidato(id="c-ok", status="aprovado", nome="Ok"),
        candidato(id="c-pub", status="publicado", nome="Pub"),
        candidato(id="c-pen", status="pendente", nome="Pen"),
    ]
    vagas = [
        vaga(id="v-ok", status="aprovado", empresa="Ok"),
        vaga(id="v-pub", status="publicado", empresa="Pub"),
    ]
    sync_content(content, candidatos, vagas, moderation_enabled=True)
    assert (content / "candidatos" / "c-ok.md").is_file()
    assert not (content / "candidatos" / "c-pub.md").exists()
    assert not (content / "candidatos" / "c-pen.md").exists()
    assert (content / "vagas" / "v-ok.md").is_file()
    assert not (content / "vagas" / "v-pub.md").exists()

    sync_content(content, candidatos, vagas, moderation_enabled=False)
    assert (content / "candidatos" / "c-pub.md").is_file()
    assert (content / "candidatos" / "c-pen.md").is_file()
    assert (content / "vagas" / "v-pub.md").is_file()


def test_relatar_falha_omite_chave(capsys):
    from sync_sheet import relatar_falha

    codigo = relatar_falha(RuntimeError(
        'falha -----BEGIN PRIVATE KEY-----\nABC\n-----END PRIVATE KEY----- "private_key": "segredo"'
    ))
    assert codigo == 1
    saida = capsys.readouterr().err
    assert "ABC" not in saida
    assert "segredo" not in saida
    assert "BEGIN PRIVATE KEY" not in saida
