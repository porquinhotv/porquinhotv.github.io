/* Utilitarios de pagina partilhados pelas tres paginas. So DOM e
   carregamento de ficheiros locais. A logica vive em logica.js. */

var PTVDOM = (function () {
  "use strict";

  function el(tag, attrs, filhos) {
    var no = document.createElement(tag);
    Object.keys(attrs || {}).forEach(function (k) {
      if (k === "text") { no.textContent = attrs[k]; }
      else if (k === "html") { no.innerHTML = attrs[k]; }
      else { no.setAttribute(k, attrs[k]); }
    });
    (filhos || []).forEach(function (f) { no.appendChild(f); });
    return no;
  }

  function escapar(texto) {
    return String(texto).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
  }

  function carregar(caminho) {
    return fetch(caminho, { cache: "no-cache" }).then(function (r) {
      if (!r.ok) { throw new Error("HTTP " + r.status + " em " + caminho); }
      return r.json();
    });
  }

  /* A cor de um canal e uma variavel CSS com o id do canal. Um canal sem
     variavel fica cinzento, nunca uma cor de outro canal. */
  function corDoCanal(id) {
    var nome = "--canal-" + id;
    var v = getComputedStyle(document.documentElement).getPropertyValue(nome).trim();
    return v ? "var(" + nome + ")" : "var(--canal-outro)";
  }

  /* "Ultima recolha" no rodape. Vive aqui, e nao na pagina principal,
     porque o rodape passou a ser o mesmo nas tres paginas a 2026-09-11:
     escrito num sitio so, nao ha forma de se desencontrar entre elas. */
  function marcarGerado(resumo) {
    marcarPronto();
    var no = document.getElementById("gerado");
    if (!no || !resumo || !resumo.gerado_em) { return; }
    no.textContent = "Última recolha: " + String(resumo.gerado_em).replace("T", " ").replace("+00:00", " UTC");
  }

  /* O botao de partilha (partilha.js) so fica ativo depois disto, para
     nunca fotografar um "A carregar". Marca-se tambem no erro: o painel
     de erro e o estado final da pagina, e o botao nao pode ficar preso. */
  function marcarPronto() {
    document.documentElement.setAttribute("data-pronto", "");
  }

  function mostrarErro(mensagem) {
    marcarPronto();
    var painel = document.getElementById("painel");
    if (!painel) { return; }
    painel.innerHTML = "";
    painel.appendChild(el("div", { class: "cartao vazio" }, [
      el("h2", { text: "Dados indisponíveis" }),
      el("p", { text: mensagem })
    ]));
  }

  return { el: el, escapar: escapar, carregar: carregar, corDoCanal: corDoCanal, marcarGerado: marcarGerado, mostrarErro: mostrarErro };
})();
