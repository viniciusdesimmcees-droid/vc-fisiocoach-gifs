// Encaminhamento de PDF: usa a API nativa de compartilhamento (WhatsApp,
// e-mail, etc.) quando disponível; senão, cai para um link do WhatsApp.
(function () {
  async function vfShare(url, title) {
    if (!url) return;
    var abs = new URL(url, location.href).href;
    var msg = title + " — " + abs;
    try {
      // 1) tenta compartilhar o próprio arquivo PDF (melhor no celular)
      if (navigator.canShare) {
        var resp = await fetch(abs);
        var blob = await resp.blob();
        var file = new File([blob], "laudo.pdf", { type: "application/pdf" });
        if (navigator.canShare({ files: [file] })) {
          await navigator.share({ files: [file], title: title, text: title });
          return;
        }
      }
      // 2) compartilha o link
      if (navigator.share) {
        await navigator.share({ title: title, text: title, url: abs });
        return;
      }
    } catch (e) {
      if (e && e.name === "AbortError") return; // usuário cancelou
    }
    // 3) fallback: abre o WhatsApp com o link
    window.open("https://wa.me/?text=" + encodeURIComponent(msg), "_blank");
  }

  document.addEventListener("click", function (e) {
    var b = e.target.closest(".share-pdf");
    if (!b) return;
    e.preventDefault();
    vfShare(b.getAttribute("data-url"), b.getAttribute("data-title") || "Laudo VF Tênis Scanner");
  });
})();
