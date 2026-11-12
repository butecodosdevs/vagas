# Planilha e Apps Script

A planilha já existe. O id padrão, usado quando o secret ou a variável `SHEET_ID` não está definido, é:

`1mMjsxHBRritkBUIEz4-TsNLBofVC7crG8WNrSwtegsQ`

A conta de serviço só **lê** a planilha (compartilhada como Viewer). Quem publica o Apps Script precisa ter acesso de **edição**, porque o formulário grava por esse script, não pela conta de serviço.

## Abas e cabeçalho

A linha 1 está congelada. O nome da coluna manda, não a ordem, mas o CI confere a ordem abaixo.

Aba **Candidatos**:

`id`, `criado_em`, `status`, `nome`, `cargo_senioridade`, `stack`, `resumo_experiencia`, `links`, `pretensao`, `modalidade`, `consentimento`

Aba **Vagas**:

`id`, `criado_em`, `status`, `empresa`, `cargo_senioridade`, `requisitos_obrigatorios`, `experiencia_desejavel`, `link_vaga`, `modalidade`, `contato`, `consentimento`

`status` aceita:

| Valor | Significado |
| --- | --- |
| `publicado` | Gravado pelo script quando `MODERATION_ENABLED` está desligado. Entra no site. |
| `pendente` | Gravado pelo script quando a moderação do script está ligada. Só entra no site se a moderação do gerador estiver desligada. |
| `aprovado` | Entra no site com a moderação do gerador ligada ou desligada. |
| `removido` | Sai do site. O sync apaga o Markdown correspondente. |

## Conta de serviço

1. No Google Cloud, ative a **Google Sheets API** no projeto da conta.
2. A chave JSON já deve estar no secret `GOOGLE_SERVICE_ACCOUNT_JSON` do repositório. O arquivo não entra no git.
3. Compartilhe a planilha com o `client_email` da conta como **Viewer**. Escrita não é necessária para o sync nem para o CI.
4. O workflow lê com o escopo `spreadsheets.readonly`.

## Apps Script

1. Abra a planilha, **Extensões > Apps Script**.
2. Cole `apps-script/Code.gs` e `apps-script/appsscript.json`.
3. Implante: **Implantar > Nova implantação > App da Web**.
   - Executar como: **Eu**
   - Quem pode acessar: **Qualquer pessoa**
4. Copie a URL que termina em `/exec`.
5. Grave essa URL em `scriptUrl` dentro de `data/forms.yaml`. A implantação atual já está lá: `https://script.google.com/macros/s/AKfycbx8k9Ge5Yt1emFY9zizRvjVmDJx7xogNyyhI6Rafl6Br8adAgs0UX-r_BF5uUiJyNHh/exec`. Se houver uma implantação nova, troque a chave de novo.
6. Faça um push para `main` (ou rode o workflow **Publicar site**) para o formulário publicado passar a usar essa URL.

Propriedades do script, em **Configurações do projeto > Propriedades do script**:

| Propriedade | Uso |
| --- | --- |
| `MODERATION_ENABLED` | `true` grava linhas novas como `pendente`. Sem a propriedade, grava `publicado`. |
| `SHEET_ID` | Só se o script não for o desta planilha. O padrão já é o id acima. |
| `SITE_URL` | Link “voltar ao mural” no comprovante. O padrão é `https://butecodosdevs.github.io/vagas`. |

Mantenha este `MODERATION_ENABLED` igual à variável de repositório de mesmo nome. São duas chaves: a do script decide o status da linha nova; a do GitHub decide o que o gerador publica.

O campo escondido `website` é um honeypot. Se vier preenchido, o script responde sucesso e não grava.

## O que o mantenedor ainda configura

- A URL do Apps Script já está em `scriptUrl`, no arquivo `data/forms.yaml`: `https://script.google.com/macros/s/AKfycbx8k9Ge5Yt1emFY9zizRvjVmDJx7xogNyyhI6Rafl6Br8adAgs0UX-r_BF5uUiJyNHh/exec`. Uma implantação nova exige atualizar essa chave. Se ela voltar a conter `PLACEHOLDER`, o formulário avisa e não envia.
- Em **Settings > Pages**, fonte **GitHub Actions**.
- Se a branch `main` estiver protegida, permitir o push do `github-actions[bot]` para o workflow de sync criar o commit.
- Opcional: variável de repositório `MODERATION_ENABLED` (`true` ou `false`, padrão `false`) e a propriedade homônima no Apps Script.
- Opcional: secret ou variável `SHEET_ID`, se a planilha mudar. Sem isso vale o id padrão.
