"""Gera Markdown com front matter a partir das linhas da planilha.

As colunas são lidas pelo nome do cabeçalho. O texto de quem preencheu o
formulário fica só no front matter, com aspas YAML e sem marcação Qute, para
não virar HTML nem expressão de template.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse

DEFAULT_SHEET_ID = "1mMjsxHBRritkBUIEz4-TsNLBofVC7crG8WNrSwtegsQ"
DIAS_PADRAO_VAGA = 60

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

_CONSENTIMENTOS = {"sim", "true", "1", "yes", "on", "aceito", "aceite"}
_SLUGS_RESERVADOS = {"index", "con", "aux", "nul", "prn"}
_DATA_ROQ = re.compile(r"^\d{4}-\d{2}-\d{2}( \d{2}:\d{2}(:\d{2})?( [+-]\d{4})?)?$")
_DATA_ISO = re.compile(
    r"^(\d{4}-\d{2}-\d{2})[T ](\d{2}:\d{2})(:\d{2})?(Z|[+-]\d{2}:?\d{2})?$"
)


class SheetError(Exception):
    """A planilha não tem o cabeçalho esperado."""


class HeaderMismatch(SheetError):
    """A linha 1 de uma aba não é o esquema documentado."""

    def __init__(self, aba: str, esperado: list[str], encontrado: list[str]):
        self.aba = aba
        self.esperado = esperado
        self.encontrado = encontrado
        achado = ", ".join(encontrado) if encontrado else "(vazio)"
        super().__init__(
            f"Aba {aba}: cabeçalho não confere.\n"
            f"Esperado: {', '.join(esperado)}\n"
            f"Encontrado: {achado}"
        )


_CHAVE_PRIVADA = re.compile(
    r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----"
)


def sanitizar_mensagem(texto: str) -> str:
    """Remove material de credencial antes de qualquer log."""
    if not texto:
        return ""
    limpo = _CHAVE_PRIVADA.sub("[redacted]", texto)
    limpo = re.sub(r'("private_key"\s*:\s*")[^"]*(")', r"\1[redacted]\2", limpo)
    if "PRIVATE KEY" in limpo or "private_key" in limpo:
        return "Falha de autenticação. O detalhe foi omitido para não expor o secret."
    return limpo[:800]


def cabecalhos_da_linha(linha: list[object]) -> list[str]:
    nomes = [str(celula).strip() for celula in linha]
    while nomes and nomes[-1] == "":
        nomes.pop()
    return nomes


def conferir_cabecalho(aba: str, linha: list[object], esperado: list[str]) -> list[str]:
    """Confere a linha 1, na ordem documentada. Células vazias no fim são ignoradas."""
    encontrado = cabecalhos_da_linha(linha)
    if encontrado != list(esperado):
        raise HeaderMismatch(aba, list(esperado), encontrado)
    return encontrado


@dataclass
class SyncResult:
    written: list[str] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)


def rows_from_values(values: list[list[object]], required: list[str] | None = None) -> list[dict[str, str]]:
    """Converte a grade da API (primeira linha = cabeçalho) em dicionários."""
    if not values:
        if required:
            raise SheetError("Planilha sem cabeçalho.")
        return []
    headers = [str(cell).strip() for cell in values[0]]
    if required:
        missing = [name for name in required if name not in headers]
        if missing:
            raise SheetError("Cabeçalhos ausentes: " + ", ".join(missing))
    rows: list[dict[str, str]] = []
    for raw in values[1:]:
        cells = list(raw) + [""] * max(0, len(headers) - len(raw))
        item: dict[str, str] = {}
        for index, header in enumerate(headers):
            if not header or header in item:
                continue
            value = cells[index]
            item[header] = "" if value is None else str(value).strip()
        if any(item.values()):
            rows.append(item)
    return rows


def should_publish(status: str, moderation_enabled: bool) -> bool:
    """Moderação desligada publica tudo, menos `removido`. Ligada, só `aprovado`."""
    normalizado = (status or "").strip().lower()
    if normalizado == "removido":
        return False
    if moderation_enabled:
        return normalizado == "aprovado"
    return True


def tem_consentimento(valor: str) -> bool:
    return (valor or "").strip().lower() in _CONSENTIMENTOS


def slug_from_id(raw_id: str) -> str:
    """Slug estável, só com [a-z0-9-], derivado do id."""
    texto = unicodedata.normalize("NFKD", str(raw_id))
    texto = "".join(ch for ch in texto if not unicodedata.combining(ch))
    texto = texto.lower()
    texto = re.sub(r"[^a-z0-9]+", "-", texto).strip("-")
    if not texto:
        raise ValueError("id sem slug utilizável")
    if texto in _SLUGS_RESERVADOS:
        texto = f"id-{texto}"
    return texto[:80].strip("-")


def normalizar_modalidade(valor: str) -> str:
    chave = unicodedata.normalize("NFKD", valor or "")
    chave = "".join(ch for ch in chave if not unicodedata.combining(ch))
    chave = chave.strip().lower()
    return {
        "remoto": "remoto",
        "remote": "remoto",
        "presencial": "presencial",
        "hibrido": "híbrido",
        "hibrida": "híbrido",
    }.get(chave, "")


# Caracteres que quebram HTML, Markdown ou o Qute quando a URL cai num template.
_URL_PERIGOSO = re.compile(r"""[<>"'`{}\\]|[\x00-\x1f\u0085\u2028\u2029]""")


def validar_urls(texto: str) -> list[str]:
    """Devolve só URLs http(s) com domínio. javascript: e HTML/Qute são descartados."""
    if not texto:
        return []
    encontradas: list[str] = []
    vistas: set[str] = set()
    for pedaco in re.split(r"[\s,;]+", str(texto).strip()):
        if not pedaco:
            continue
        url = pedaco.rstrip(".,]>\"'")
        if not re.match(r"https?://", url, re.IGNORECASE):
            continue
        if _URL_PERIGOSO.search(url):
            continue
        partes = urlparse(url)
        if partes.scheme.lower() not in {"http", "https"} or not partes.hostname:
            continue
        if url not in vistas:
            vistas.add(url)
            encontradas.append(url)
    return encontradas


def _limitar(valor: str, limite: int) -> str:
    texto = (valor or "").strip()
    if len(texto) <= limite:
        return texto
    return texto[: limite - 1].rstrip() + "…"


def _html(valor: str) -> str:
    return (
        valor.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _neutralizar_qute(valor: str) -> str:
    # Um espaço de largura zero quebra `{=` e `{#`, que o Qute executaria.
    return valor.replace("{", "{\u200b")


def yaml_quote(valor: str) -> str:
    texto = _neutralizar_qute(valor or "")
    saida: list[str] = []
    for caractere in texto.replace("\r\n", "\n").replace("\r", "\n"):
        if caractere == "\\":
            saida.append("\\\\")
        elif caractere == '"':
            saida.append('\\"')
        elif caractere == "\n":
            saida.append("\\n")
        elif caractere == "\t":
            saida.append("\\t")
        elif ord(caractere) < 32 or caractere in "\u0085\u2028\u2029":
            saida.append(f"\\u{ord(caractere):04x}")
        else:
            saida.append(caractere)
    return '"' + "".join(saida) + '"'


def _uma_linha(valor: str, limite: int) -> str:
    return _limitar(re.sub(r"\s+", " ", valor or "").strip(), limite)


def _data_publicacao(valor: str) -> str:
    """Normaliza para o formato do Roq: yyyy-MM-dd[ HH:mm][:ss][ Z]."""
    texto = (valor or "").strip()
    if _DATA_ROQ.match(texto):
        return texto
    encontrado = _DATA_ISO.match(texto)
    if not encontrado:
        return ""
    data, hora, segundos, fuso = encontrado.groups()
    segundos = segundos or ":00"
    if fuso == "Z":
        fuso = " +0000"
    elif fuso:
        sinal = fuso[0]
        resto = fuso[1:].replace(":", "")
        if len(resto) == 2:
            resto += "00"
        fuso = f" {sinal}{resto}"
    else:
        fuso = ""
    return f"{data} {hora}{segundos}{fuso}"


def dias_maximos_vaga(valor: str | None = None) -> int:
    """Lê VAGA_MAX_DIAS. Vazio, inválido ou negativo volta ao padrão de 60."""
    if valor is None or str(valor).strip() == "":
        return DIAS_PADRAO_VAGA
    try:
        dias = int(str(valor).strip())
    except ValueError:
        return DIAS_PADRAO_VAGA
    if dias < 0:
        return DIAS_PADRAO_VAGA
    return dias


def instante_criado(valor: str) -> datetime | None:
    normalizado = _data_publicacao(valor)
    if not normalizado:
        return None
    for formato in (
        "%Y-%m-%d %H:%M:%S %z",
        "%Y-%m-%d %H:%M %z",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%d",
    ):
        try:
            momento = datetime.strptime(normalizado, formato)
        except ValueError:
            continue
        if momento.tzinfo is None:
            return momento.replace(tzinfo=timezone.utc)
        return momento
    return None


def vaga_expirada(criado_em: str, agora: datetime, max_dias: int) -> bool:
    """Verdadeiro se a vaga foi criada há mais dias do que o limite."""
    momento = instante_criado(criado_em)
    if momento is None:
        return False
    referencia = agora if agora.tzinfo else agora.replace(tzinfo=timezone.utc)
    return referencia - momento > timedelta(days=max_dias)


def _arquivo_exemplo(caminho: Path) -> bool:
    if not caminho.is_file():
        return False
    texto = caminho.read_text(encoding="utf-8")
    if not texto.startswith("---"):
        return False
    fim = texto.find("\n---", 3)
    if fim < 0:
        return False
    return re.search(r"(?m)^exemplo:\s*true\s*$", texto[3:fim]) is not None


def _destino(diretorio: Path, slug: str) -> Path:
    base = diretorio.resolve()
    destino = (base / f"{slug}.md").resolve()
    if base not in destino.parents:
        raise ValueError("slug escapou do diretório de conteúdo")
    return destino


def render_candidato(row: dict[str, str]) -> str:
    nome = _limitar(row.get("nome", ""), 80)
    cargo = _limitar(row.get("cargo_senioridade", ""), 120)
    stack = _limitar(row.get("stack", ""), 300)
    resumo = _limitar(row.get("resumo_experiencia", ""), 2000)
    pretensao = _limitar(row.get("pretensao", ""), 120)
    modalidade = normalizar_modalidade(row.get("modalidade", ""))
    links = validar_urls(_limitar(row.get("links", ""), 500))
    titulo = " — ".join(parte for parte in (nome, cargo) if parte) or row.get("id", "Candidato")
    return _documento(
        layout="candidato",
        titulo=titulo,
        descricao=_uma_linha(resumo, 180) or titulo,
        row=row,
        campos=[
            ("nome", nome),
            ("cargo_senioridade", cargo),
            ("stack", stack),
            ("resumo_experiencia", resumo),
            ("pretensao", pretensao),
            ("modalidade", modalidade),
        ],
        links=links,
        link_unico=None,
    )


def render_vaga(row: dict[str, str]) -> str:
    empresa = _limitar(row.get("empresa", ""), 120)
    cargo = _limitar(row.get("cargo_senioridade", ""), 120)
    requisitos = _limitar(row.get("requisitos_obrigatorios", ""), 2000)
    experiencia = _limitar(row.get("experiencia_desejavel", ""), 2000)
    contato = _limitar(row.get("contato", ""), 200)
    modalidade = normalizar_modalidade(row.get("modalidade", ""))
    links = validar_urls(_limitar(row.get("link_vaga", ""), 500))
    titulo = " — ".join(parte for parte in (cargo, empresa) if parte) or row.get("id", "Vaga")
    return _documento(
        layout="vaga",
        titulo=titulo,
        descricao=_uma_linha(requisitos, 180) or titulo,
        row=row,
        campos=[
            ("empresa", empresa),
            ("cargo_senioridade", cargo),
            ("requisitos_obrigatorios", requisitos),
            ("experiencia_desejavel", experiencia),
            ("modalidade", modalidade),
            ("contato", contato),
        ],
        links=None,
        link_unico=links[0] if links else "",
    )


def _documento(
    layout: str,
    titulo: str,
    descricao: str,
    row: dict[str, str],
    campos: list[tuple[str, str]],
    links: list[str] | None,
    link_unico: str | None,
) -> str:
    slug = slug_from_id(row.get("id", ""))
    status = (row.get("status") or "").strip().lower()
    linhas = [
        "---",
        f"layout: {layout}",
        f"title: {yaml_quote(_uma_linha(titulo, 160))}",
        f"description: {yaml_quote(descricao)}",
        f"slug: {yaml_quote(slug)}",
        f"id: {yaml_quote(slug)}",
    ]
    data = _data_publicacao(row.get("criado_em", ""))
    if data:
        linhas.append(f"date: {yaml_quote(data)}")
    linhas.append("exemplo: false")
    linhas.append(f"status: {yaml_quote(status)}")
    for nome, valor in campos:
        linhas.append(f"{nome}: {yaml_quote(valor)}")
    if links is not None:
        if links:
            linhas.append("links:")
            linhas.extend(f"  - {yaml_quote(url)}" for url in links)
        else:
            linhas.append("links: []")
    if link_unico is not None:
        linhas.append(f"link_vaga: {yaml_quote(link_unico)}")
    linhas.append(f"consentimento: {yaml_quote((row.get('consentimento') or '').strip().lower())}")
    linhas.append("---")
    linhas.append("")
    linhas.append(
        "Apresentação publicada no mural Vagas do Buteco. Os dados públicos estão nos campos acima."
    )
    if links:
        # HTML escapado, não Markdown: um ")" no meio da URL não fecha o link.
        linhas.append("")
        linhas.append('<ul class="links">')
        for url in links:
            seguro = _html(_neutralizar_qute(url))
            linhas.append(f'<li><a href="{seguro}" rel="noopener noreferrer">{seguro}</a></li>')
        linhas.append("</ul>")
    linhas.append("")
    return "\n".join(linhas)


def _publicar_linha(row: dict[str, str], tipo: str, moderation_enabled: bool) -> bool:
    if not should_publish(row.get("status", ""), moderation_enabled):
        return False
    if not tem_consentimento(row.get("consentimento", "")):
        return False
    if tipo == "candidato":
        return bool((row.get("nome") or "").strip())
    return bool((row.get("empresa") or "").strip() or (row.get("cargo_senioridade") or "").strip())


def _sincronizar_pasta(
    diretorio: Path,
    rows: list[dict[str, str]],
    tipo: str,
    moderation_enabled: bool,
    resultado: SyncResult,
    max_dias: int | None = None,
    agora: datetime | None = None,
) -> None:
    diretorio.mkdir(parents=True, exist_ok=True)
    vistos: set[str] = set()
    publicou = False
    for row in rows:
        bruto = (row.get("id") or "").strip()
        if not bruto:
            resultado.skipped.append(f"{tipo}:sem-id")
            continue
        try:
            slug = slug_from_id(bruto)
        except ValueError:
            resultado.skipped.append(f"{tipo}:{bruto}")
            continue
        if slug in vistos:
            resultado.skipped.append(f"{tipo}:duplicado:{slug}")
            continue
        vistos.add(slug)
        destino = _destino(diretorio, slug)
        if _arquivo_exemplo(destino):
            resultado.skipped.append(str(destino))
            continue
        expirada = (
            tipo == "vaga"
            and agora is not None
            and max_dias is not None
            and vaga_expirada(row.get("criado_em", ""), agora, max_dias)
        )
        if not expirada and _publicar_linha(row, tipo, moderation_enabled):
            texto = render_candidato(row) if tipo == "candidato" else render_vaga(row)
            destino.write_text(texto, encoding="utf-8")
            resultado.written.append(str(destino))
            publicou = True
            continue
        if destino.exists():
            destino.unlink()
            resultado.removed.append(str(destino))
        else:
            resultado.skipped.append(str(destino))
    if publicou:
        _remover_exemplos(diretorio, resultado)


def _remover_exemplos(diretorio: Path, resultado: SyncResult) -> None:
    """Tira os cards fictícios quando a aba já tem alguma linha publicável."""
    for caminho in diretorio.glob("*.md"):
        if _arquivo_exemplo(caminho):
            caminho.unlink()
            resultado.removed.append(str(caminho))


def sync_content(
    content_root: Path,
    candidatos: list[dict[str, str]],
    vagas: list[dict[str, str]],
    moderation_enabled: bool,
    max_dias_vaga: int = DIAS_PADRAO_VAGA,
    agora: datetime | None = None,
) -> SyncResult:
    """Escreve os Markdown publicados e apaga os que deixaram de ser públicos.

    Sem linha publicável na aba, os arquivos `exemplo: true` ficam. Com ao
    menos uma linha publicável, os exemplos daquela coleção saem. Vaga mais
    velha que `max_dias_vaga` sai do mural. Candidato não expira.
    """
    raiz = Path(content_root)
    momento = agora or datetime.now(timezone.utc)
    if momento.tzinfo is None:
        momento = momento.replace(tzinfo=timezone.utc)
    resultado = SyncResult()
    _sincronizar_pasta(raiz / "candidatos", candidatos, "candidato", moderation_enabled, resultado)
    _sincronizar_pasta(
        raiz / "vagas",
        vagas,
        "vaga",
        moderation_enabled,
        resultado,
        max_dias=max_dias_vaga,
        agora=momento,
    )
    return resultado
