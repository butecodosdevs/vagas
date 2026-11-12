import assert from "node:assert/strict";
import fs from "node:fs";
import test from "node:test";
import vm from "node:vm";

const FONTE = fs.readFileSync(new URL("../apps-script/Code.gs", import.meta.url), "utf8");

function carregar(props = {}, aba = "candidato", cabecalhoFixo = null) {
  const gravados = [];
  let aberturas = 0;
  const sandbox = {
    Utilities: {
      getUuid: () => "11111111-2222-4333-8444-555555555555",
      formatDate: () => "2026-11-12T15:04:05-03:00",
    },
    PropertiesService: {
      getScriptProperties: () => ({
        getProperty: (nome) => (Object.prototype.hasOwnProperty.call(props, nome) ? props[nome] : null),
      }),
    },
    HtmlService: {
      createHtmlOutput: (html) => ({ html }),
    },
    LockService: {
      getScriptLock: () => ({
        waitLock() {},
        releaseLock() {},
      }),
    },
    SpreadsheetApp: {
      openById() {
        aberturas += 1;
        return {
          getSheetByName(nome) {
            assert.equal(nome, aba === "candidato" ? "Candidatos" : "Vagas");
            return {
              getLastColumn: () => 20,
              getLastRow: () => 1,
              getRange(row) {
                if (row === 1) {
                  return { getValues: () => [cabecalhoFixo || sandbox.CABECALHOS[aba]] };
                }
                return {
                  setNumberFormat(formato) {
                    assert.equal(formato, "@");
                  },
                  setValues(valores) {
                    gravados.push(valores[0]);
                  },
                };
              },
            };
          },
        };
      },
    },
  };
  vm.createContext(sandbox);
  vm.runInContext(FONTE, sandbox);
  return {
    sandbox,
    gravados,
    aberturas: () => aberturas,
  };
}

function candidato(extra = {}) {
  return {
    tipo: "candidato",
    nome: "Ana",
    cargo_senioridade: "Dev pleno",
    stack: "Java",
    resumo_experiencia: "APIs",
    links: "https://example.com/ana",
    pretensao: "a combinar",
    modalidade: "híbrido",
    consentimento: "sim",
    ...extra,
  };
}

function vaga(extra = {}) {
  return {
    tipo: "vaga",
    empresa: "Padaria",
    cargo_senioridade: "Pessoa engenheira pleno",
    requisitos_obrigatorios: "Java",
    experiencia_desejavel: "",
    link_vaga: "https://example.com/vaga",
    modalidade: "remoto",
    contato: "vagas@example.com",
    consentimento: "sim",
    ...extra,
  };
}

function celula(ctx, tipo, nome) {
  const cabecalhos = ctx.sandbox.CABECALHOS[tipo];
  assert.equal(ctx.gravados.length, 1);
  return ctx.gravados[0][cabecalhos.indexOf(nome)];
}

test("honeypot preenchido responde sucesso e não grava", () => {
  const ctx = carregar();
  const saida = ctx.sandbox.doPost({ parameter: candidato({ website: "http://bot.example" }) });
  assert.equal(ctx.gravados.length, 0);
  assert.equal(ctx.aberturas(), 0);
  assert.match(saida.html, /Recebemos/);
  assert.doesNotMatch(saida.html, /bot\.example/);
});

test("sem consentimento, sem modalidade ou sem campo obrigatório não grava", () => {
  for (const extra of [{ consentimento: "" }, { modalidade: "" }, { nome: "  " }, { links: "" }]) {
    const ctx = carregar();
    const saida = ctx.sandbox.doPost({ parameter: candidato(extra) });
    assert.equal(ctx.gravados.length, 0, JSON.stringify(extra));
    assert.match(saida.html, /Não deu para enviar/);
  }
});

test("rejeita javascript, html, qute e link sem domínio", () => {
  const ruins = [
    "javascript:alert(1)",
    "https://evil.example/a)<script>alert(1)</script>",
    "https://evil.example/{=site.url}",
    "https://evil.example/{#include evil}",
    'https://evil.example/a"onclick=alert(1)',
    "https://",
    "data:text/html,hi",
  ];
  for (const links of ruins) {
    const ctx = carregar();
    const saida = ctx.sandbox.doPost({ parameter: candidato({ links }) });
    assert.equal(ctx.gravados.length, 0, links);
    assert.match(saida.html, /link|http/i);
    assert.doesNotMatch(saida.html, /<script>alert/);
  }
});

test("aceita link https e guarda o status do servidor, não o do formulário", () => {
  const ctx = carregar();
  const saida = ctx.sandbox.doPost({
    parameter: candidato({ status: "aprovado", links: "https://example.com/ana, https://example.com/b" }),
  });
  assert.match(saida.html, /Recebemos/);
  assert.equal(celula(ctx, "candidato", "status"), "publicado");
  assert.match(celula(ctx, "candidato", "links"), /https:\/\/example.com\/ana/);
  assert.equal(celula(ctx, "candidato", "modalidade"), "híbrido");
});

test("texto que parece fórmula de planilha é gravado como texto", () => {
  const ctx = carregar();
  ctx.sandbox.doPost({ parameter: candidato({ nome: '=HYPERLINK("http://evil.example")', stack: "+cmd", pretensao: "-1+1" }) });
  for (const nome of ["nome", "stack", "pretensao"]) {
    const valor = celula(ctx, "candidato", nome);
    assert.match(valor, /^'/, nome);
    assert.doesNotMatch(valor, /^[=+\-@]/, nome);
  }
});

test("campo longo demais é recusado", () => {
  const ctx = carregar();
  const saida = ctx.sandbox.doPost({ parameter: candidato({ nome: "a".repeat(81) }) });
  assert.equal(ctx.gravados.length, 0);
  assert.match(saida.html, /80/);
});

test("emoji e texto longo dentro do limite são gravados", () => {
  const ctx = carregar();
  ctx.sandbox.doPost({ parameter: candidato({ nome: "Ana 😀", resumo_experiencia: "á".repeat(2000) }) });
  assert.equal(celula(ctx, "candidato", "nome"), "Ana 😀");
  assert.equal(celula(ctx, "candidato", "resumo_experiencia").length, 2000);
});

test("moderação true, yes, on, sim e 1 gravam pendente", () => {
  for (const flag of ["true", "TRUE", "yes", "on", "sim", "1"]) {
    const ctx = carregar({ MODERATION_ENABLED: flag });
    ctx.sandbox.doPost({ parameter: candidato() });
    assert.equal(celula(ctx, "candidato", "status"), "pendente", flag);
  }
  const desligada = carregar({ MODERATION_ENABLED: "false" });
  desligada.sandbox.doPost({ parameter: candidato() });
  assert.equal(celula(desligada, "candidato", "status"), "publicado");
});

test("vaga sem link opcional grava e link perigoso não", () => {
  const ok = carregar({}, "vaga");
  ok.sandbox.doPost({ parameter: vaga({ link_vaga: "" }) });
  assert.equal(celula(ok, "vaga", "link_vaga"), "");

  const ruim = carregar({}, "vaga");
  const saida = ruim.sandbox.doPost({
    parameter: vaga({ link_vaga: "https://evil.example/a)<script>alert(1)</script>" }),
  });
  assert.equal(ruim.gravados.length, 0);
  assert.doesNotMatch(saida.html, /<script>alert/);
});

test("url do comprovante não vira html nem javascript", () => {
  const ctx = carregar({ SITE_URL: 'https://evil.example/"><script>alert(1)</script>' });
  const saida = ctx.sandbox.doPost({ parameter: candidato() });
  assert.match(saida.html, /Recebemos/);
  assert.doesNotMatch(saida.html, /<script>alert/);
  assert.match(saida.html, /https:\/\/butecodosdevs\.github\.io\/vagas/);
});

test("tipo desconhecido e coluna ausente falham sem gravar lixo", () => {
  const tipo = carregar();
  const saida = tipo.sandbox.doPost({ parameter: { tipo: "admin", consentimento: "sim" } });
  assert.match(saida.html, /desconhecido/);
  assert.equal(tipo.gravados.length, 0);

  const semColuna = carregar({}, "candidato", ["id", "nome"]);
  const erro = semColuna.sandbox.doPost({ parameter: candidato() });
  assert.match(erro.html, /Cabeçalho ausente/);
  assert.equal(semColuna.gravados.length, 0);
});
