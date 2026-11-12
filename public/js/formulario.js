(function () {
  document.querySelectorAll("[data-formulario]").forEach(function (form) {
    var aviso = form.querySelector("[data-aviso]");
    var ok = form.parentElement.querySelector("[data-ok]");
    var frame = form.querySelector("iframe");

    function mostrarAviso(texto) {
      if (!aviso) return;
      aviso.hidden = false;
      aviso.textContent = texto;
    }

    window.addEventListener("message", function (evento) {
      if (evento.origin !== "https://script.google.com") return;
      var dados = evento.data || {};
      if (dados.fonte !== "vagas-do-buteco" || evento.source !== frame.contentWindow) return;
      form.dataset.confirmado = "sim";
      if (dados.ok) {
        form.hidden = true;
        if (ok) ok.hidden = false;
        if (aviso) aviso.hidden = true;
        return;
      }
      mostrarAviso(dados.mensagem || "Não foi possível enviar. Nada foi publicado.");
    });

    form.addEventListener("submit", function (eventoSubmit) {
      var pote = form.querySelector('[name="website"]');
      if (pote && pote.value.trim()) {
        eventoSubmit.preventDefault();
        return;
      }
      if (form.action.indexOf("PLACEHOLDER") !== -1) {
        eventoSubmit.preventDefault();
        mostrarAviso("Este formulário ainda aponta para o endereço de exemplo. Quem mantém o site precisa publicar o Apps Script e trocar a URL em data/forms.yaml.");
        return;
      }
      if (!form.checkValidity()) return;
      form.dataset.confirmado = "";
      form.target = frame.name;
      frame.addEventListener("load", function aoCarregar() {
        frame.removeEventListener("load", aoCarregar);
        window.setTimeout(function () {
          if (form.dataset.confirmado === "sim") return;
          mostrarAviso("Não conseguimos confirmar o envio. Se a mensagem de erro não aparecer, tente de novo.");
        }, 1500);
      });
    });
  });
})();
