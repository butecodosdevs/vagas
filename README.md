# Vagas do Buteco

Mural estático de vagas e de apresentações de quem está na procura, da comunidade [Buteco dos Devs](https://butecodosdevs.com/). Onde código e cerveja se encontram.

O site é gerado com [Roq](https://iamroq.dev/). Os formulários gravam numa planilha Google por um Apps Script. Um workflow lê essa planilha e atualiza o Markdown do repositório.

## Como as peças se encontram

1. A pessoa preenche `/cadastro/candidato` ou `/cadastro/vaga`.
2. O formulário faz POST no Apps Script (`apps-script/`), que valida, gera `id` e `criado_em` e acrescenta uma linha na aba certa.
3. A cada 6 horas (ou no disparo manual), `.github/workflows/sync-sheet.yml` lê as duas abas com a conta de serviço e reescreve `content/vagas/` e `content/candidatos/`.
4. Se houve diff, o workflow faz commit. O workflow **Publicar site** gera o Roq e publica em GitHub Pages.
5. Enquanto a planilha não tem linhas reais, o site mostra quatro registros marcados como exemplo.

A conta de serviço só lê. Quem implanta o Apps Script precisa poder editar a planilha.

## Esquema da planilha

Id padrão: `1mMjsxHBRritkBUIEz4-TsNLBofVC7crG8WNrSwtegsQ`. Dá para trocar com o secret ou a variável `SHEET_ID`.

A linha 1 é o cabeçalho, congelada. O gerador acha a coluna pelo nome.

**Candidatos:** `id`, `criado_em`, `status`, `nome`, `cargo_senioridade`, `stack`, `resumo_experiencia`, `links`, `pretensao`, `modalidade`, `consentimento`

**Vagas:** `id`, `criado_em`, `status`, `empresa`, `cargo_senioridade`, `requisitos_obrigatorios`, `experiencia_desejavel`, `link_vaga`, `modalidade`, `contato`, `consentimento`

`status`:

| Valor | Quando aparece |
| --- | --- |
| `publicado` | Padrão do Apps Script com `MODERATION_ENABLED` desligado. |
| `pendente` | Padrão do Apps Script com a moderação do script ligada. |
| `aprovado` | Marcação manual para publicar com a moderação do gerador ligada. |
| `removido` | O sync apaga o arquivo dessa linha. |

`MODERATION_ENABLED` vem da variável de repositório (padrão `false`):

- `false`: publica toda linha que não esteja `removido` e que tenha consentimento.
- `true`: publica só `aprovado`.

O Apps Script tem uma propriedade de script com o mesmo nome. Ela só escolhe o status inicial (`publicado` ou `pendente`). As duas precisam andar juntas. O passo a passo está em [docs/setup-google.md](docs/setup-google.md).

## Desenvolvimento local

Java 21. Instale o Roq:

```bash
curl -Ls https://sh.jbang.dev | bash -s - app install --fresh --force roq@quarkiverse/quarkus-roq
```

```bash
roq start
```

Abre em <http://localhost:8080>. Não existe comando `roq dev`; o modo de desenvolvimento é o `roq start`.

```bash
roq generate   # site estático em target/roq/
roq serve      # pré-visualiza o que foi gerado
```

No perfil de produção o site fica sob `/vagas`, que é o caminho do GitHub Pages deste repositório. O `roq start` usa o perfil dev, na raiz.

Testes do gerador:

```bash
python -m pip install -r requirements.txt
python -m pytest
node --test tests/apps_script.test.mjs
```

O e2e sobe o site gerado e usa o Chromium. Ele não chama o Apps Script de verdade: o envio é interceptado.

```bash
roq generate
cd e2e
npm ci
npx playwright install --with-deps chromium
npm test
```

## Secrets e variáveis

| Nome | Onde | Função |
| --- | --- | --- |
| `GOOGLE_SERVICE_ACCOUNT_JSON` | Secret | JSON da conta de serviço. O CI e o sync leem a planilha. Nunca vai para o log. |
| `SHEET_ID` | Secret ou variável, opcional | Id da planilha. Sem isso, vale o id padrão acima. |
| `MODERATION_ENABLED` | Variável de repositório, opcional | `true` ou `false`. Padrão `false`. |
| `VAGA_MAX_DIAS` | Variável de repositório, opcional | Vaga mais velha que isto sai do mural. Padrão `60`. Candidato não expira. |

A URL do Apps Script fica em `data/forms.yaml`, na chave `scriptUrl`. O valor atual é `https://script.google.com/macros/s/AKfycbzpI1PDL1ShmXnN5EzSgwB-B6hSN6T0Z4h6zdDYDFBJtQYocrB0OHNt4YdhxFsFFsuA/exec`. Se a chave voltar a conter `PLACEHOLDER`, o formulário avisa e não envia.

## CI e publicação

- **CI**, em pull request e em disparo manual: testes e `roq generate`. Esse workflow não recebe o secret.
- **Checagem da planilha**: `pull_request_target` (código da branch padrão, nunca o do PR) e `workflow_dispatch`. Autentica com o secret, lê a linha 1 de **Candidatos** e **Vagas** e compara com o esquema. Não imprime o JSON. Fork não roda. O workflow só passa a valer depois do merge em `main`.
- **Sincronizar planilha**: cron `0 */6 * * *` e disparo manual. Commit só quando o Markdown mudou.
- **Publicar site**: push em `main`, disparo manual e depois de uma sincronização bem-sucedida. Gera com Roq e publica com `actions/deploy-pages`.
- **Alertar falha de workflow**: se o sync ou a publicação falham na `main`, abre ou comenta um issue com o rótulo `falha-workflow`. Uma execução posterior bem-sucedida fecha o aviso.
- O CI também confere os links internos do HTML gerado, sem sair da rede. Acessibilidade com axe, nas páginas home, vagas, candidatos e nos dois formulários, já roda no Playwright.

Em **Settings > Pages**, a fonte precisa ser **GitHub Actions**.

## O que configurar na mão

1. Pages com fonte GitHub Actions.
2. A URL do Apps Script já está em `scriptUrl`, no arquivo `data/forms.yaml`. Se a implantação mudar, atualize essa chave.
3. Secret `GOOGLE_SERVICE_ACCOUNT_JSON` e a planilha compartilhada com a conta como Viewer. Isso já foi feito para a planilha atual.
4. Se `main` tiver proteção de branch, deixar o `github-actions[bot]` fazer push no sync.
5. Opcional: `MODERATION_ENABLED` no repositório e a propriedade de mesmo nome no Apps Script.
6. Opcional: `SHEET_ID`, se a planilha for outra.

O guia da planilha, do script e da conta de serviço está em [docs/setup-google.md](docs/setup-google.md). O dia a dia (remover uma entrada, expiração, sync manual, moderação e o aviso de falha) está em [docs/operacao.md](docs/operacao.md).
