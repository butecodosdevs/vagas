/**
 * Web app do mural Vagas do Buteco.
 * Grava nas abas Candidatos e Vagas pelo nome da coluna, não pela posição.
 *
 * Propriedades do script (opcionais):
 *   MODERATION_ENABLED  "true" grava status pendente; senão, publicado
 *   SHEET_ID            id da planilha, se o script não estiver vinculado a ela
 *   SITE_URL            link de volta no comprovante
 */
var PLANILHA_PADRAO = '1mMjsxHBRritkBUIEz4-TsNLBofVC7crG8WNrSwtegsQ';
var SITE_PADRAO = 'https://butecodosdevs.github.io/vagas';

var CABECALHOS = {
  candidato: ['id', 'criado_em', 'status', 'nome', 'cargo_senioridade', 'stack', 'resumo_experiencia', 'links', 'pretensao', 'modalidade', 'consentimento'],
  vaga: ['id', 'criado_em', 'status', 'empresa', 'cargo_senioridade', 'requisitos_obrigatorios', 'experiencia_desejavel', 'link_vaga', 'modalidade', 'contato', 'consentimento']
};

var LIMITES = {
  nome: 80,
  cargo_senioridade: 120,
  stack: 300,
  resumo_experiencia: 2000,
  links: 500,
  pretensao: 120,
  empresa: 120,
  requisitos_obrigatorios: 2000,
  experiencia_desejavel: 2000,
  link_vaga: 500,
  contato: 200,
  modalidade: 40
};

var ABAS = { candidato: 'Candidatos', vaga: 'Vagas' };

function doGet() {
  return HtmlService.createHtmlOutput(pagina(
    'Endpoint do mural',
    '<p>Este endereço recebe os formulários de Vagas do Buteco.</p>',
    false,
    ''
  ));
}

function doPost(e) {
  var trava = LockService.getScriptLock();
  try {
    trava.waitLock(15000);
    var dados = (e && e.parameter) || {};
    if (texto(dados.website).length) {
      return htmlOk();
    }
    var tipo = texto(dados.tipo);
    if (!CABECALHOS[tipo]) {
      return htmlErro('Tipo de envio desconhecido.');
    }
    var valores = validar(tipo, dados);
    acrescentar(ABAS[tipo], CABECALHOS[tipo], valores);
    return htmlOk();
  } catch (erro) {
    return htmlErro(erro && erro.message ? erro.message : 'Não foi possível gravar o envio.');
  } finally {
    trava.releaseLock();
  }
}

function validar(tipo, dados) {
  if (texto(dados.consentimento).toLowerCase() !== 'sim') {
    throw new Error('É preciso autorizar a publicação pública dos dados.');
  }
  var modalidade = normalizarModalidade(dados.modalidade);
  if (!modalidade) {
    throw new Error('Escolha a modalidade: remoto, presencial ou híbrido.');
  }
  var comum = {
    id: (tipo === 'candidato' ? 'c-' : 'v-') + Utilities.getUuid(),
    criado_em: Utilities.formatDate(new Date(), 'America/Sao_Paulo', "yyyy-MM-dd'T'HH:mm:ssXXX"),
    status: statusInicial(),
    cargo_senioridade: campo(dados.cargo_senioridade, 'cargo_senioridade', true),
    modalidade: modalidade,
    consentimento: 'sim'
  };
  if (tipo === 'candidato') {
    comum.nome = campo(dados.nome, 'nome', true);
    comum.stack = campo(dados.stack, 'stack', true);
    comum.resumo_experiencia = campo(dados.resumo_experiencia, 'resumo_experiencia', true);
    comum.links = urls(dados.links, true);
    comum.pretensao = campo(dados.pretensao, 'pretensao', false);
  } else {
    comum.empresa = campo(dados.empresa, 'empresa', true);
    comum.requisitos_obrigatorios = campo(dados.requisitos_obrigatorios, 'requisitos_obrigatorios', true);
    comum.experiencia_desejavel = campo(dados.experiencia_desejavel, 'experiencia_desejavel', false);
    comum.link_vaga = dados.link_vaga ? urls(dados.link_vaga, true) : '';
    comum.contato = campo(dados.contato, 'contato', true);
  }
  return comum;
}

function statusInicial() {
  var flag = texto(PropertiesService.getScriptProperties().getProperty('MODERATION_ENABLED')).toLowerCase();
  if (flag === 'true' || flag === '1' || flag === 'sim') return 'pendente';
  return 'publicado';
}

function campo(valor, nome, obrigatorio) {
  var limpo = texto(valor);
  if (!limpo && obrigatorio) throw new Error('Preencha o campo ' + nome + '.');
  var limite = LIMITES[nome] || 200;
  if (limpo.length > limite) throw new Error('O campo ' + nome + ' passou de ' + limite + ' caracteres.');
  return limpo;
}

function urls(valor, obrigatorio) {
  var bruto = campo(valor, 'links', false);
  if (!bruto) {
    if (obrigatorio) throw new Error('Informe um link http(s).');
    return '';
  }
  if (bruto.length > (LIMITES.links || 500) && bruto.length > (LIMITES.link_vaga || 500)) {
    throw new Error('O link passou do limite de caracteres.');
  }
  var partes = bruto.split(/[\s,;]+/);
  var saida = [];
  partes.forEach(function (parte) {
    var url = parte.replace(/[),.\]]+$/, '');
    if (!url) return;
    if (!/^https?:\/\//i.test(url)) throw new Error('Use apenas links http ou https.');
    saida.push(url);
  });
  if (!saida.length && obrigatorio) throw new Error('Informe um link http(s).');
  return saida.join(', ');
}

function normalizarModalidade(valor) {
  var chave = texto(valor).toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '');
  if (chave === 'remoto') return 'remoto';
  if (chave === 'presencial') return 'presencial';
  if (chave === 'hibrido' || chave === 'hibrida') return 'híbrido';
  return '';
}

function acrescentar(aba, cabecalhos, valores) {
  var planilha = SpreadsheetApp.openById(
    texto(PropertiesService.getScriptProperties().getProperty('SHEET_ID')) || PLANILHA_PADRAO
  );
  var sheet = planilha.getSheetByName(aba);
  if (!sheet) throw new Error('Aba não encontrada: ' + aba);
  var ultimaColuna = Math.max(sheet.getLastColumn(), cabecalhos.length);
  var header = sheet.getRange(1, 1, 1, ultimaColuna).getValues()[0].map(function (item) {
    return texto(item);
  });
  cabecalhos.forEach(function (nome) {
    if (header.indexOf(nome) === -1) throw new Error('Cabeçalho ausente na aba ' + aba + ': ' + nome);
  });
  var linha = header.map(function (nome) {
    return Object.prototype.hasOwnProperty.call(valores, nome) ? valores[nome] : '';
  });
  var destino = sheet.getRange(sheet.getLastRow() + 1, 1, 1, linha.length);
  destino.setNumberFormat('@');
  destino.setValues([linha]);
}

function texto(valor) {
  return valor === null || valor === undefined ? '' : String(valor).trim();
}

function siteUrl() {
  return texto(PropertiesService.getScriptProperties().getProperty('SITE_URL')) || SITE_PADRAO;
}

function htmlOk() {
  return HtmlService.createHtmlOutput(pagina(
    'Envio recebido',
    '<p>Recebemos os dados. O mural atualiza sozinho a cada 6 horas.</p><p><a href="' + siteUrl() + '">Voltar ao mural</a></p>',
    true,
    ''
  ));
}

function htmlErro(mensagem) {
  return HtmlService.createHtmlOutput(pagina(
    'Não deu para enviar',
    '<p>' + escapar(mensagem) + '</p><p><a href="' + siteUrl() + '">Voltar ao mural</a></p>',
    false,
    mensagem
  ));
}

function sinalParaOSite(ok, mensagem) {
  var json = JSON.stringify({
    fonte: 'vagas-do-buteco',
    ok: ok === true,
    mensagem: texto(mensagem)
  }).replace(/</g, '\\u003c');
  return '<script>parent.postMessage(' + json + ',"*");</script>';
}

function pagina(titulo, corpo, ok, mensagem) {
  return '<!DOCTYPE html><html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>' +
    escapar(titulo) + '</title></head><body style="margin:0;font-family:Inter,system-ui,sans-serif;background:#3B2218;color:#F5F0E8">' +
    sinalParaOSite(ok, mensagem) +
    '<main style="max-width:36rem;margin:4rem auto;padding:1.5rem"><h1 style="font-family:Space Grotesk,sans-serif">' +
    escapar(titulo) + '</h1>' + corpo + '</main></body></html>';
}

function escapar(valor) {
  return texto(valor)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}
