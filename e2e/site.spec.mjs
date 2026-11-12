import fs from "node:fs";
import { expect, test } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

const ARTEFATOS = "/opt/cursor/artifacts";
const MOCK = "https://script.google.com/macros/s/mock-endpoint/exec";

test.beforeAll(() => {
  fs.mkdirSync(ARTEFATOS, { recursive: true });
});

async function semViolacao(page) {
  const resultado = await new AxeBuilder({ page }).exclude(".gradiente").analyze();
  expect(resultado.violations, JSON.stringify(resultado.violations, null, 2)).toEqual([]);
}

async function conferirMarca(page) {
  const estilos = await page.evaluate(() => {
    const body = getComputedStyle(document.body);
    const titulo = getComputedStyle(document.querySelector("h1"));
    const botao = getComputedStyle(document.querySelector("main .botao-ambar"));
    return {
      fundo: body.backgroundColor,
      texto: body.color,
      titulo: titulo.fontFamily,
      botaoFundo: botao.backgroundColor,
      botaoTexto: botao.color,
    };
  });
  expect(estilos.fundo).toBe("rgb(59, 34, 24)");
  expect(estilos.texto).toBe("rgb(245, 240, 232)");
  expect(estilos.titulo.toLowerCase()).toContain("space grotesk");
  expect(estilos.botaoFundo).toBe("rgb(245, 166, 35)");
  expect(estilos.botaoTexto).toBe("rgb(30, 36, 50)");
}

test("home, vagas e candidatos renderizam com a marca do Buteco", async ({ page }) => {
  await page.goto("");
  await expect(page.getByRole("heading", { level: 1 })).toContainText("código");
  await expect(page.getByRole("heading", { level: 1 })).toContainText("cerveja");
  await expect(page.getByRole("link", { name: "Quero me apresentar" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Entrar no Discord" }).first()).toBeVisible();
  await conferirMarca(page);
  await semViolacao(page);
  await page.screenshot({ path: `${ARTEFATOS}/home.png`, fullPage: true });

  await page.goto("vagas/");
  await expect(page.getByRole("heading", { level: 1, name: "Vagas" })).toBeVisible();
  await expect(page.getByRole("link", { name: /engenheira de software/ }).first()).toBeVisible();
  await conferirMarca(page);
  await semViolacao(page);
  await page.screenshot({ path: `${ARTEFATOS}/vagas.png`, fullPage: true });

  await page.goto("candidatos/");
  await expect(page.getByRole("heading", { level: 1, name: "Candidatos" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Ana Souza (exemplo)" })).toBeVisible();
  await semViolacao(page);
  await page.screenshot({ path: `${ARTEFATOS}/candidatos.png`, fullPage: true });

  await page.goto("candidatos/exemplo-candidato-ana/");
  const link = page.locator('a[href="https://example.com/ana-souza"]');
  await expect(link).toBeVisible();
  await expect(link).toHaveAttribute("rel", /noopener/);
  await expect(link).not.toContainText("<script>");
});

test("formulários têm rótulos, contraste e foco por teclado", async ({ page }) => {
  for (const caminho of ["cadastro/candidato/", "cadastro/vaga/"]) {
    await page.goto(caminho);
    await expect(page.locator("form[data-formulario]")).toBeVisible();
    await expect(page.locator(".pote-de-mel")).toHaveAttribute("aria-hidden", "true");
    await expect(page.locator(".pote-de-mel")).not.toBeInViewport();

    const campos = page.locator("form input:not([type=hidden]), form select, form textarea");
    const total = await campos.count();
    for (let indice = 0; indice < total; indice += 1) {
      const campo = campos.nth(indice);
      const nome = await campo.getAttribute("name");
      if (nome === "website") continue;
      const temRotulo = await campo.evaluate((elemento) => {
        const rotulo = elemento.closest("label");
        return Boolean(rotulo && rotulo.textContent.trim().length > 1);
      });
      expect(temRotulo, nome).toBe(true);
    }

    await semViolacao(page);
    await page.screenshot({
      path: `${ARTEFATOS}/${caminho.includes("vaga") ? "form-vaga" : "form-candidato"}.png`,
      fullPage: true,
    });
    for (let passo = 0; passo < 20; passo += 1) {
      await page.keyboard.press("Tab");
      const ativo = await page.evaluate(() => document.activeElement?.getAttribute("name"));
      expect(ativo).not.toBe("website");
      if (ativo === "nome" || ativo === "empresa") break;
    }
    const foco = await page.evaluate(() => document.activeElement?.getAttribute("name"));
    expect(["nome", "empresa"]).toContain(foco);
  }
});

test("atalho de teclado e menu no celular", async ({ page }) => {
  await page.goto("");
  await page.keyboard.press("Tab");
  await expect(page.locator("a.pular")).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(page.locator("#conteudo")).toBeInViewport();

  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("cadastro/candidato/");
  await expect(page.locator(".menu-largo")).toBeHidden();
  await expect(page.locator(".menu-curto")).toBeVisible();
  await page.locator(".menu-curto summary").focus();
  await page.keyboard.press("Enter");
  await expect(page.locator(".menu-curto").getByRole("link", { name: "Vagas" })).toBeVisible();
  await page.screenshot({ path: `${ARTEFATOS}/form-candidato-mobile.png`, fullPage: true });
});

test("candidato valida obrigatórios, url, consentimento, honeypot e envia ao endpoint", async ({ page }) => {
  let posts = 0;
  await page.route("**/*", async (route) => {
    if (route.request().method() === "POST") posts += 1;
    await route.continue();
  });

  await page.goto("cadastro/candidato/");
  await expect(page.locator("form")).toHaveAttribute("action", /PLACEHOLDER/);
  await page.getByRole("button", { name: "Publicar minha apresentação" }).click();
  await expect.poll(() => page.locator('input[name="nome"]').evaluate((el) => el.validity.valueMissing)).toBe(true);
  expect(posts).toBe(0);

  await preencherCandidato(page, { link: "nao-e-url", consent: true });
  await page.getByRole("button", { name: "Publicar minha apresentação" }).click();
  await expect.poll(() => page.locator('input[name="links"]').evaluate((el) => el.validity.typeMismatch)).toBe(true);
  expect(posts).toBe(0);

  await page.locator('input[name="links"]').fill("ftp://example.com/cv");
  await page.getByRole("button", { name: "Publicar minha apresentação" }).click();
  await expect.poll(() => page.locator('input[name="links"]').evaluate((el) => el.validity.patternMismatch)).toBe(true);
  expect(posts).toBe(0);

  await page.locator('input[name="links"]').fill("javascript:alert(1)");
  await page.getByRole("button", { name: "Publicar minha apresentação" }).click();
  await expect.poll(() => page.locator('input[name="links"]').evaluate((el) => !el.validity.valid)).toBe(true);
  expect(posts).toBe(0);

  await page.locator('input[name="links"]').fill("https://example.com/ana");
  await page.locator('input[name="consentimento"]').uncheck();
  await page.getByRole("button", { name: "Publicar minha apresentação" }).click();
  await expect.poll(() => page.locator('input[name="consentimento"]').evaluate((el) => el.validity.valueMissing)).toBe(true);
  expect(posts).toBe(0);

  await page.locator('input[name="consentimento"]').check();
  await page.getByRole("button", { name: "Publicar minha apresentação" }).click();
  await expect(page.locator("[data-aviso]")).toContainText("data/forms.yaml");
  await expect(page.locator("form")).toBeVisible();
  expect(posts).toBe(0);

  await page.unroute("**/*");
  posts = 0;
  await page.route(MOCK, async (route) => {
    posts += 1;
    await route.fulfill({ status: 200, contentType: "text/html", body: "<p>ok</p>" });
  });
  await page.locator("form").evaluate((form, url) => {
    form.action = url;
  }, MOCK);
  await page.locator('input[name="website"]').fill("http://bot.example", { force: true });
  await page.getByRole("button", { name: "Publicar minha apresentação" }).click();
  await page.waitForTimeout(300);
  expect(posts).toBe(0);
  await expect(page.locator("[data-ok]")).toBeHidden();

  await page.locator('input[name="website"]').fill("", { force: true });
  const pedido = page.waitForRequest((req) => req.method() === "POST" && req.url() === MOCK);
  await page.getByRole("button", { name: "Publicar minha apresentação" }).click();
  const enviado = await pedido;
  const corpo = enviado.postData() || "";
  expect(corpo).toContain("tipo=candidato");
  expect(corpo).toContain("nome=Ana");
  expect(corpo).toContain("consentimento=sim");
  expect(corpo).toContain("links=https%3A%2F%2Fexample.com%2Fana");
  expect(corpo).not.toContain("website=http");
  await expect(page.locator("[data-ok]")).toBeVisible();
  expect(posts).toBe(1);
});

test("vaga valida obrigatórios, url, consentimento, honeypot e envia ao endpoint", async ({ page }) => {
  await page.goto("cadastro/vaga/");
  await page.getByRole("button", { name: "Publicar vaga" }).click();
  await expect.poll(() => page.locator('input[name="empresa"]').evaluate((el) => el.validity.valueMissing)).toBe(true);

  await preencherVaga(page, { link: "ftp://example.com/vaga" });
  await page.getByRole("button", { name: "Publicar vaga" }).click();
  await expect.poll(() => page.locator('input[name="link_vaga"]').evaluate((el) => el.validity.patternMismatch)).toBe(true);

  await page.locator('input[name="link_vaga"]').fill("");
  await page.locator('input[name="consentimento"]').uncheck();
  await page.getByRole("button", { name: "Publicar vaga" }).click();
  await expect.poll(() => page.locator('input[name="consentimento"]').evaluate((el) => el.validity.valueMissing)).toBe(true);

  let posts = 0;
  await page.route(MOCK, async (route) => {
    posts += 1;
    await route.fulfill({ status: 200, contentType: "text/html", body: "<p>ok</p>" });
  });
  await page.locator("form").evaluate((form, url) => {
    form.action = url;
  }, MOCK);
  await page.locator('input[name="consentimento"]').check();
  await page.locator('input[name="website"]').fill("http://bot.example", { force: true });
  await page.getByRole("button", { name: "Publicar vaga" }).click();
  await page.waitForTimeout(300);
  expect(posts).toBe(0);

  await page.locator('input[name="website"]').fill("", { force: true });
  const pedido = page.waitForRequest((req) => req.method() === "POST" && req.url() === MOCK);
  await page.getByRole("button", { name: "Publicar vaga" }).click();
  const corpo = (await pedido).postData() || "";
  expect(corpo).toContain("tipo=vaga");
  expect(corpo).toContain("empresa=Padaria");
  expect(corpo).toContain("consentimento=sim");
  expect(corpo).not.toContain("link_vaga=ftp");
  await expect(page.locator("[data-ok]")).toBeVisible();
});

async function preencherCandidato(page, { link, consent }) {
  await page.locator('input[name="nome"]').fill("Ana Souza");
  await page.locator('input[name="cargo_senioridade"]').fill("Dev backend pleno");
  await page.locator('input[name="stack"]').fill("Java, Quarkus");
  await page.locator('textarea[name="resumo_experiencia"]').fill("Constrói APIs.");
  await page.locator('input[name="links"]').fill(link);
  await page.locator('input[name="pretensao"]').fill("A combinar");
  await page.locator('select[name="modalidade"]').selectOption("remoto");
  if (consent) await page.locator('input[name="consentimento"]').check();
}

async function preencherVaga(page, { link }) {
  await page.locator('input[name="empresa"]').fill("Padaria Digital");
  await page.locator('input[name="cargo_senioridade"]').fill("Pessoa engenheira pleno");
  await page.locator('textarea[name="requisitos_obrigatorios"]').fill("Java e testes.");
  await page.locator('input[name="link_vaga"]').fill(link);
  await page.locator('select[name="modalidade"]').selectOption("híbrido");
  await page.locator('input[name="contato"]').fill("vagas@example.com");
  await page.locator('input[name="consentimento"]').check();
}
