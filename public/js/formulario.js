(function () {
  document.querySelectorAll("[data-formulario]").forEach(function (form) {
    var aviso = form.querySelector("[data-aviso]");
    var ok = form.parentElement.querySelector("[data-ok]");
    var frame = form.querySelector("iframe");
    form.addEventListener("submit", function (evento) {
      var pote = form.querySelector('[name="website"]');
      if (pote && pote.value.trim()) {
        evento.preventDefault();
        return;
      }
      if (form.action.indexOf("PLACEHOLDER") !== -1) {
        evento.preventDefault();
        if (aviso) {
          aviso.hidden = false;
          aviso.textContent = "Este formulário ainda aponta para o endereço de exemplo. Quem mantém o site precisa publicar o Apps Script e trocar a URL em data/forms.yaml.";
        }
        return;
      }
      if (!form.checkValidity()) return;
      form.target = frame.name;
      frame.addEventListener("load", function aoCarregar() {
        frame.removeEventListener("load", aoCarregar);
        form.hidden = true;
        if (ok) ok.hidden = false;
      });
    });
  });
})();
