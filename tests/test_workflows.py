"""Permissões e o commit condicional dos workflows, sem imprimir segredo."""

from pathlib import Path

from check_internal_links import arquivo_do_link, eh_interno, verificar

RAIZ = Path(__file__).resolve().parents[1]
WORKFLOWS = RAIZ / ".github" / "workflows"


def _ler(nome: str) -> str:
    return (WORKFLOWS / nome).read_text(encoding="utf-8")


def test_ci_so_le_o_repositorio_e_nao_imprime_o_secret():
    texto = _ler("ci.yml")
    assert "contents: read" in texto
    assert "contents: write" not in texto
    assert "id-token" not in texto
    assert "pages:" not in texto
    assert "pull_request_target" not in texto
    assert "GOOGLE_SERVICE_ACCOUNT_JSON" not in texto
    assert "printenv" not in texto


def test_checagem_da_planilha_nao_executa_o_codigo_do_pr():
    texto = _ler("sheet-check.yml")
    assert "pull_request_target:" in texto
    assert "workflow_dispatch:" in texto
    assert "contents: read" in texto
    assert "contents: write" not in texto
    assert "persist-credentials: false" in texto
    assert "pull_request.base.sha" in texto
    assert "head.sha" not in texto
    assert "head.repo.full_name" in texto
    assert "secrets.GOOGLE_SERVICE_ACCOUNT_JSON" in texto
    assert 'echo "$GOOGLE_SERVICE_ACCOUNT_JSON"' not in texto
    assert "printenv" not in texto


def test_deploy_pede_pages_e_id_token_so_no_job_de_publicacao():
    texto = _ler("deploy.yml")
    assert "contents: write" not in texto
    assert "pages: write" in texto
    assert texto.count("id-token:") == 1
    assert texto.index("name: GitHub Pages") < texto.index("id-token: write")
    assert "pull_request_target" not in texto
    assert "cancel-in-progress: false" in texto
    assert "group: pages" in texto


def test_sync_escreve_so_conteudo_e_so_faz_commit_com_diff():
    texto = _ler("sync-sheet.yml")
    assert "contents: write" in texto
    assert "id-token" not in texto
    assert "pages:" not in texto
    assert "pull_request_target" not in texto
    assert "group: sincronizar-planilha" in texto
    assert "cancel-in-progress: false" in texto
    assert "git add content/vagas content/candidatos" in texto
    assert "git add -A" not in texto
    assert "--force" not in texto
    bloco = texto.split("git diff --staged --quiet", 1)[1]
    assert bloco.index("exit 0") < bloco.index("git commit") < bloco.index("git push")
    assert 'echo "$GOOGLE_SERVICE_ACCOUNT_JSON"' not in texto
    assert "printenv" not in texto


def test_alerta_de_falha_so_usa_o_token_e_issues():
    texto = _ler("alerta-falha.yml")
    assert 'workflows: ["Sincronizar planilha", "Publicar site"]' in texto
    assert "types: [completed]" in texto
    assert "head_branch == 'main'" in texto
    assert "issues: write" in texto
    assert "actions: read" in texto
    assert "contents:" not in texto
    assert "pull_request" not in texto
    assert "falha-workflow" in texto
    assert "Falha na main:" in texto
    assert "mesmo workflow" in texto or "select(.title" in texto
    assert "secrets." not in texto
    assert "github.token" in texto
    assert "issue create" in texto
    assert "issue close" in texto
    assert "issue comment" in texto


def test_pull_request_target_so_na_checagem_da_planilha():
    for caminho in WORKFLOWS.glob("*.yml"):
        texto = caminho.read_text(encoding="utf-8")
        if caminho.name == "sheet-check.yml":
            assert "pull_request_target" in texto
        else:
            assert "pull_request_target" not in texto, caminho.name
    assert "GOOGLE_SERVICE_ACCOUNT_JSON" not in _ler("deploy.yml")
    assert "GOOGLE_SERVICE_ACCOUNT_JSON" not in _ler("ci.yml")


def test_links_internos_ignoram_a_rede_e_acham_arquivo(tmp_path: Path):
    site = tmp_path / "roq"
    (site / "vagas").mkdir(parents=True)
    (site / "vagas" / "index.html").write_text(
        '<a href="/vagas/vagas/">Vagas</a><a href="https://discord.gg/buteco-dos-devs">Discord</a>'
        '<img src="/vagas/images/logo.png">',
        encoding="utf-8",
    )
    (site / "images").mkdir()
    (site / "images" / "logo.png").write_bytes(b"png")
    assert eh_interno("/vagas/vagas/")
    assert eh_interno("#conteudo") is False
    assert eh_interno("https://example.com") is False
    assert eh_interno("https://butecodosdevs.github.io/vagas/images/logo.png")
    assert arquivo_do_link("/vagas/vagas/", site) == (site / "vagas" / "index.html").resolve()
    assert arquivo_do_link("https://butecodosdevs.github.io/vagas/images/logo.png", site) == (
        site / "images" / "logo.png"
    ).resolve()
    assert verificar(site) == []
    (site / "index.html").write_text('<a href="/vagas/sumiu/">Quebrou</a>', encoding="utf-8")
    faltando = verificar(site)
    assert len(faltando) == 1
    assert "/vagas/sumiu/" in faltando[0]
