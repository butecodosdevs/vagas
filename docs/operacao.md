# Operação do mural

Guia para quem mantém o [Vagas do Buteco](https://github.com/butecodosdevs/vagas). A planilha continua sendo a fonte dos cadastros. O site público só muda depois que o workflow **Sincronizar planilha** grava os Markdown e o workflow **Publicar site** gera as páginas.

## Tirar uma entrada do ar

1. Na planilha, na aba **Candidatos** ou **Vagas**, mude a coluna `status` da linha para `removido`.
2. Rode o sync (veja abaixo) ou espere o agendamento, a cada 6 horas.
3. O sync apaga `content/candidatos/<slug>.md` ou `content/vagas/<slug>.md` e faz commit se houver diferença. O deploy seguinte deixa de publicar a página.

O arquivo some da ponta da `main`, mas o histórico do Git continua com o Markdown antigo. Quem clonar o repositório e olhar commits anteriores ainda vê o texto.

Se for preciso apagar também do histórico, isso reescreve a `main` e pede coordenação com quem já clonou o repositório:

- Use [`git filter-repo`](https://github.com/newren/git-filter-repo) para remover o caminho, ou o fluxo de [remoção de dados sensíveis do GitHub](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/removing-sensitive-data-from-a-repository).
- Faça force-push da `main` só depois de avisar a equipe.
- Peça para quem colabora apagar o clone local e clonar de novo. Um `git pull` comum não basta.

Não há botão no site para isso. A planilha é o lugar da decisão.

## Vaga velha

Vaga com `criado_em` há mais dias do que `VAGA_MAX_DIAS` deixa de ser publicada. O padrão é 60. Candidato não expira.

A variável fica em **Settings > Secrets and variables > Actions > Variables**. Sem a variável, vale 60. Valor vazio, texto ou número negativo também valem 60. Zero expira qualquer vaga cuja data já passou.

O sync compara a data com o momento da execução. Vaga sem `criado_em` reconhecível permanece. Os arquivos de exemplo (`exemplo: true`) só saem quando existe alguma vaga da planilha que ainda pode ser publicada. Uma vaga expirada não conta como publicada e, sozinha, não apaga os exemplos.

## Rodar o sync na mão

1. Abra **Actions > Sincronizar planilha**.
2. **Run workflow**, branch `main`.
3. O job lê a planilha com o secret `GOOGLE_SERVICE_ACCOUNT_JSON` e, se o Markdown mudou, faz commit na `main`.
4. Esse commit dispara **Publicar site**.

Quem dispara precisa de permissão de escrita no repositório. O token de uma integração sem `actions: write` recebe HTTP 403 e o workflow não começa.

## Moderação

São duas chaves com o mesmo nome, e as duas precisam andar juntas.

| Onde | O que faz |
| --- | --- |
| Propriedade de script `MODERATION_ENABLED` no Apps Script | Linha nova nasce `pendente` quando o valor é `true`, `1`, `sim`, `yes` ou `on`. Sem isso, nasce `publicado`. |
| Variável de repositório `MODERATION_ENABLED` | O sync, com `true`, publica só `aprovado`. Com `false` ou ausente, publica tudo que não esteja `removido` nem seja vaga expirada. |

Para ligar:

1. No Apps Script, **Configurações do projeto > Propriedades do script**, crie `MODERATION_ENABLED` = `true`.
2. No GitHub, crie a variável `MODERATION_ENABLED` = `true`.
3. Nas linhas que devem aparecer, mude `status` para `aprovado`.
4. Rode o sync.

Para desligar, apague as duas ou grave `false` nas duas. Linhas `publicado` voltam a entrar no mural no sync seguinte. Linha `pendente` também entra quando a moderação do gerador está desligada.

## Aviso de falha

O workflow **Alertar falha de workflow** escuta **Sincronizar planilha** e **Publicar site** na `main`. Ele usa só o `GITHUB_TOKEN`, com permissão de ler Actions e escrever issues.

Se uma execução falha de verdade, ele abre um issue com o rótulo `falha-workflow`, título `Falha na main: <workflow>` e o link da execução. Se esse workflow já tem um aviso aberto, ele comenta nele. Uma execução posterior **do mesmo workflow** que conclui com sucesso comenta e fecha só esse aviso. O sucesso de **Publicar site** não fecha o aviso de **Sincronizar planilha**, nem o contrário. Execução em que todos os jobs foram ignorados não abre nem fecha nada: é o caso do deploy que nem começa porque o sync falhou.

O aviso significa que o mural automático parou naquele passo. O site no ar continua na última publicação que deu certo.
