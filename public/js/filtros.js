(function () {
  var raiz = document.querySelector("[data-filtros]");
  var lista = document.querySelector("[data-lista]");
  if (!raiz || !lista) return;
  var vazio = document.querySelector("[data-vazio]");
  var modalidade = raiz.querySelector("[data-filtro-modalidade]");
  var stack = raiz.querySelector("[data-filtro-stack]");

  function normaliza(valor) {
    return (valor || "")
      .toLowerCase()
      .normalize("NFD")
      .replace(/[\u0300-\u036f]/g, "");
  }

  function aplicar() {
    var modo = normaliza(modalidade.value);
    var termos = normaliza(stack.value).split(/\s+/).filter(Boolean);
    var visiveis = 0;
    lista.querySelectorAll("[data-cartao]").forEach(function (cartao) {
      var modoOk = !modo || normaliza(cartao.getAttribute("data-modalidade")) === modo;
      var busca = normaliza(cartao.getAttribute("data-busca"));
      var stackOk = termos.every(function (termo) {
        return busca.indexOf(termo) !== -1;
      });
      var mostra = modoOk && stackOk;
      cartao.hidden = !mostra;
      if (mostra) visiveis += 1;
    });
    if (vazio) vazio.hidden = visiveis !== 0;
  }

  modalidade.addEventListener("change", aplicar);
  stack.addEventListener("input", aplicar);
})();
