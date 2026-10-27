/* Botao de partilha. Fotografa a pagina tal como esta no ecra, abre um
   editor onde se escolhe o enquadramento, e entrega uma imagem para as
   stories (1080x1920) ou para o feed (1080x1350), sempre com a marca do
   site no rodape.

   Porque a fotografia e feita por uma biblioteca: o browser nao tem
   forma de tirar uma captura do ecra sem pedir permissao, e a unica API
   que o faz (getDisplayMedia) nao existe no telemovel. A biblioteca
   (docs/vendor/modern-screenshot.js, MIT, licenca ao lado) redesenha o
   DOM num canvas. Escolhida a 2026-10-27 por medicao contra a captura
   nativa do Chromium, nas quatro paginas, em mobile e desktop: no pior
   caso diferiam 2,8% dos pixeis, e era antialias do texto. A outra
   candidata (html2canvas-pro) perdia o icone do porquinho no topo, em
   mobile, e pesava sete vezes mais.

   E servida daqui e so carrega quando se carrega no botao: o site nao
   pede nada a terceiros, e quem nunca partilha nao paga os 29 KB.

   A logica de enquadramento, que tem contas, vive em enquadramento.js e
   tem testes em Node. Aqui fica so o que precisa de DOM. */

(function () {
  "use strict";

  var E = window.PTVEnquadramento;
  if (!E || !document.body) { return; }

  var BIBLIOTECA = "vendor/modern-screenshot.js";
  // Tudo o que tem esta classe fica fora da fotografia: o proprio botao
  // e o editor. Sem isto, a imagem partilhada mostrava o botao de
  // partilhar no canto.
  var IGNORAR = "ptv-partilha-ignorar";
  var NOME = "Porquinho TV";

  var estado = {
    formato: "historia",
    foto: null, escalaFoto: 1, pagina: null, visivel: null, coluna: null,
    enq: null, lim: null,
    versao: 0, ficheiro: null, ficheiroVersao: -1, temporizador: null,
    icone: null, aberto: false, ocupado: false, sessao: 0
  };
  var ui = {};

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

  function cor(nome, reserva) {
    var v = getComputedStyle(document.documentElement).getPropertyValue(nome).trim();
    return v || reserva;
  }

  /* As cores e o tipo de letra saem do estilo.css: escritos aqui de novo,
     a imagem de partilha desencontrava-se do site na primeira mudanca de
     paleta. As reservas so servem se a variavel faltar. */
  function paleta() {
    return {
      ceu: cor("--ceu", "#CFEAF7"), ceuClaro: cor("--ceu-claro", "#EAF6FB"),
      erva: cor("--erva", "#7CB85C"), ervaEscura: cor("--erva-escura", "#5E9A45"),
      tinta: cor("--tinta", "#2B2118"), tintaSuave: cor("--tinta-suave", "#6B5E52"),
      fonte: cor("--fonte", "Fredoka, sans-serif")
    };
  }

  /* O endereco do rodape da imagem vem do canonical da pagina, que o
     gerador de SEO escreve a partir do config/seo.yml. Assim nao ha uma
     segunda copia do endereco do site para envelhecer. */
  function endereco() {
    var c = document.querySelector('link[rel="canonical"]');
    try { return new URL(c ? c.href : location.href).host; } catch (e) { return location.host; }
  }

  /* Estatisticas: so contam se o contador de visitas ja carregou, e uma
     falha dele nunca pode partir a partilha. Decidido pelo autor a
     2026-10-27; nao acrescenta nenhum pedido a terceiros alem do script
     que todas as paginas ja carregam. */
  function contar(acao) {
    try {
      if (window.umami && typeof window.umami.track === "function") {
        var pagina = location.pathname.replace(/^.*\//, "") || "index.html";
        window.umami.track("partilha", { acao: acao, formato: estado.formato, pagina: pagina });
      }
    } catch (e) { /* o contador e um enfeite, a partilha nao */ }
  }

  /* ---- prontidao ---------------------------------------------------- */

  /* Nas paginas com dados, o botao so fica ativo quando os dados chegam
     (o comum.js marca data-pronto), para nunca partilhar um "A carregar".
     A Metodologia nao tem dados nem o rodape com id="gerado", e esta
     pronta desde o inicio. */
  function pronto() {
    return !document.getElementById("gerado") || document.documentElement.hasAttribute("data-pronto");
  }

  function atualizarBotao() {
    if (pronto()) { ui.botao.removeAttribute("aria-disabled"); }
    else { ui.botao.setAttribute("aria-disabled", "true"); }
  }

  /* ---- recursos ----------------------------------------------------- */

  var promessaBiblioteca = null;
  function carregarBiblioteca() {
    if (window.modernScreenshot) { return Promise.resolve(); }
    if (!promessaBiblioteca) {
      promessaBiblioteca = new Promise(function (ok, falha) {
        var s = el("script", { src: BIBLIOTECA });
        s.onload = function () { ok(); };
        s.onerror = function () { promessaBiblioteca = null; falha(new Error("não carregou " + BIBLIOTECA)); };
        document.head.appendChild(s);
      });
    }
    return promessaBiblioteca;
  }

  /* O favicon.svg so declara viewBox. O Safari recusa desenhar num canvas
     um SVG sem largura e altura, e a marca e obrigatoria em todas as
     imagens: por isso o icone carrega com as dimensoes acrescentadas, e
     uma falha aqui impede a exportacao em vez de sair uma imagem sem
     marca. Vai como data: e nao como blob:, que e o mesmo caminho que a
     biblioteca usa e que o Safari aceita sem sujar o canvas. */
  var promessaIcone = null;
  function carregarIcone() {
    if (!promessaIcone) {
      promessaIcone = fetch("favicon.svg").then(function (r) {
        if (!r.ok) { throw new Error("HTTP " + r.status + " em favicon.svg"); }
        return r.text();
      }).then(function (svg) {
        var comTamanho = svg.replace(/<svg\b/, '<svg width="256" height="256"');
        return new Promise(function (ok, falha) {
          var img = new Image();
          img.onload = function () { ok(img); };
          img.onerror = function () { falha(new Error("o ícone não abriu")); };
          img.src = "data:image/svg+xml;charset=utf-8," + encodeURIComponent(comTamanho);
        });
      });
      promessaIcone.catch(function () { promessaIcone = null; });
    }
    return promessaIcone;
  }

  function carregarTipos() {
    if (!document.fonts || !document.fonts.load) { return Promise.resolve(); }
    var f = paleta().fonte;
    return Promise.all([document.fonts.load("700 76px " + f), document.fonts.load("500 36px " + f)])
      .catch(function () { /* sem o tipo, o texto sai no tipo de reserva, mas sai */ });
  }

  /* ---- o que esta no ecra ------------------------------------------- */

  /* visualViewport da o retangulo que se ve de facto, incluindo quando a
     pessoa aproximou com dois dedos. Sem ele, cai-se no scroll e na
     largura do documento sem a barra de deslocamento. Le-se no instante
     do toque, antes de qualquer coisa mexer no ecra. */
  function medirVisivel() {
    var vv = window.visualViewport;
    if (vv && vv.width > 0) { return { x: vv.pageLeft, y: vv.pageTop, w: vv.width, h: vv.height }; }
    var d = document.documentElement;
    return { x: window.pageXOffset, y: window.pageYOffset, w: d.clientWidth, h: window.innerHeight };
  }

  function medirColuna() {
    var esq = Infinity, dir = -Infinity;
    document.querySelectorAll(".topo, .palco, main, .rodape").forEach(function (n) {
      var r = n.getBoundingClientRect();
      if (r.width > 0) { esq = Math.min(esq, r.left); dir = Math.max(dir, r.right); }
    });
    if (!isFinite(esq)) { return null; }
    return { x: esq + window.pageXOffset, w: dir - esq };
  }

  function fotografar(sessao) {
    var d = document.documentElement;
    var escala = E.escalaDeCaptura({ w: d.scrollWidth, h: d.scrollHeight }, window.devicePixelRatio || 1);
    return window.modernScreenshot.domToCanvas(d, {
      scale: escala,
      filter: function (no) { return !(no.classList && no.classList.contains(IGNORAR)); }
    }).then(function (canvas) {
      if (sessao !== estado.sessao || !estado.aberto) { return; }
      // As dimensoes da pagina saem da propria fotografia: se a pagina
      // mudou de tamanho entre a medicao e a captura, e esta que manda.
      estado.foto = canvas;
      estado.escalaFoto = escala;
      estado.pagina = { w: canvas.width / escala, h: canvas.height / escala };
    });
  }

  /* ---- composicao --------------------------------------------------- */

  function caminho(ctx, x, y, w, h, r) {
    ctx.beginPath();
    ctx.moveTo(x + r, y);
    ctx.arcTo(x + w, y, x + w, y + h, r);
    ctx.arcTo(x + w, y + h, x, y + h, r);
    ctx.arcTo(x, y + h, x, y, r);
    ctx.arcTo(x, y, x + w, y, r);
    ctx.closePath();
  }

  /* Desenha a imagem inteira em pixeis de saida; k converte para o canvas
     de destino (1 na exportacao, menos na pre-visualizacao). A
     pre-visualizacao e a exportacao passam pela mesma funcao: o que se ve
     no editor e exatamente o que sai. */
  function compor(ctx, k) {
    var f = E.FORMATOS[estado.formato];
    var j = f.janela, m = f.marca, p = paleta();
    ctx.setTransform(k, 0, 0, k, 0, 0);
    ctx.imageSmoothingEnabled = true;
    ctx.imageSmoothingQuality = "high";

    var fundo = ctx.createLinearGradient(0, 0, 0, f.altura * 0.45);
    fundo.addColorStop(0, p.ceu);
    fundo.addColorStop(1, p.ceuClaro);
    ctx.fillStyle = fundo;
    ctx.fillRect(0, 0, f.largura, f.altura);

    ctx.fillStyle = p.erva;
    ctx.fillRect(0, f.erva, f.largura, f.altura - f.erva);
    ctx.fillStyle = p.ervaEscura;
    ctx.fillRect(0, f.altura - 14, f.largura, 14);

    ctx.fillStyle = p.tinta;
    caminho(ctx, j.x + j.sombra, j.y + j.sombra, j.w, j.h, j.raio);
    ctx.fill();

    ctx.save();
    caminho(ctx, j.x, j.y, j.w, j.h, j.raio);
    ctx.clip();
    ctx.fillStyle = p.ceuClaro;
    ctx.fillRect(j.x, j.y, j.w, j.h);
    var r = E.recorte(estado.enq, estado.pagina, j);
    if (r) {
      var ef = estado.escalaFoto;
      var sx = r.sx * ef, sy = r.sy * ef;
      var sw = Math.min(r.sw * ef, estado.foto.width - sx);
      var sh = Math.min(r.sh * ef, estado.foto.height - sy);
      if (sw > 0 && sh > 0) { ctx.drawImage(estado.foto, sx, sy, sw, sh, j.x + r.dx, j.y + r.dy, r.dw, r.dh); }
    }
    ctx.restore();
    ctx.lineWidth = j.borda;
    ctx.strokeStyle = p.tinta;
    caminho(ctx, j.x, j.y, j.w, j.h, j.raio);
    ctx.stroke();

    // A marca: porquinho, nome e endereco, centrados como um bloco so.
    var site = endereco();
    ctx.font = "700 " + m.nome + "px " + p.fonte;
    var wNome = ctx.measureText(NOME).width;
    ctx.font = "500 " + m.endereco + "px " + p.fonte;
    var wEnd = ctx.measureText(site).width;
    var total = m.icone + m.intervalo + Math.max(wNome, wEnd);
    var x0 = (f.largura - total) / 2;
    ctx.drawImage(estado.icone, x0, m.cy - m.icone / 2, m.icone, m.icone);
    var xt = x0 + m.icone + m.intervalo;
    ctx.textBaseline = "alphabetic";
    ctx.textAlign = "left";
    ctx.fillStyle = p.tinta;
    ctx.font = "700 " + m.nome + "px " + p.fonte;
    // O nome inclinado dois graus, como no topo do site.
    ctx.save();
    ctx.translate(xt, m.cy - m.endereco * 0.25);
    ctx.rotate(-2 * Math.PI / 180);
    ctx.fillText(NOME, 0, 0);
    ctx.restore();
    ctx.fillStyle = p.tintaSuave;
    ctx.font = "500 " + m.endereco + "px " + p.fonte;
    ctx.fillText(site, xt + 2, m.cy + m.endereco * 1.15);
    ctx.setTransform(1, 0, 0, 1, 0, 0);
  }

  function exportar() {
    var f = E.FORMATOS[estado.formato];
    var c = document.createElement("canvas");
    c.width = f.largura;
    c.height = f.altura;
    compor(c.getContext("2d"), 1);
    return new Promise(function (ok, falha) {
      c.toBlob(function (b) { if (b) { ok(b); } else { falha(new Error("a imagem não se gerou")); } }, "image/png");
    });
  }

  /* O ficheiro prepara-se logo que o enquadramento para de mexer. O
     Safari so deixa abrir a folha de partilha dentro do proprio toque, e
     gerar um PNG de 1080x1920 e assincrono: se a geracao ficasse para o
     toque em "Partilhar", o Safari recusava a partilha. */
  function prepararFicheiro() {
    estado.versao += 1;
    var v = estado.versao;
    clearTimeout(estado.temporizador);
    estado.temporizador = setTimeout(function () { obterFicheiro(v); }, 250);
  }

  function obterFicheiro(v) {
    var versao = v === undefined ? estado.versao : v;
    if (estado.ficheiroVersao === versao && estado.ficheiro) { return Promise.resolve(estado.ficheiro); }
    return exportar().then(function (blob) {
      var f = new File([blob], E.nomeDoFicheiro(new Date(), estado.formato), { type: "image/png" });
      if (versao === estado.versao) { estado.ficheiro = f; estado.ficheiroVersao = versao; }
      return f;
    });
  }

  /* ---- editor ------------------------------------------------------- */

  function janela() { return E.FORMATOS[estado.formato].janela; }

  function recalcularLimites() {
    var j = janela();
    estado.lim = E.limites(estado.pagina, j, E.inicial(estado.pagina, estado.visivel, estado.coluna, j).s);
  }

  function repor() {
    estado.enq = E.inicial(estado.pagina, estado.visivel, estado.coluna, janela());
    recalcularLimites();
    mudou();
  }

  function aplicar(enq) {
    estado.enq = E.limitar(enq, estado.pagina, janela(), estado.lim);
    mudou();
  }

  function mudou() {
    ui.zoom.value = String(E.controloDaEscala(estado.enq.s, estado.lim));
    desenharPrevia();
    prepararFicheiro();
  }

  function ajustarPrevia() {
    if (!estado.foto) { return; }
    var f = E.FORMATOS[estado.formato];
    var caixaW = ui.palco.clientWidth, caixaH = ui.palco.clientHeight;
    if (!caixaW || !caixaH) { return; }
    var cssH = Math.min(caixaH, caixaW * f.altura / f.largura);
    var cssW = cssH * f.largura / f.altura;
    var dpr = window.devicePixelRatio || 1;
    ui.previa.style.width = cssW + "px";
    ui.previa.style.height = cssH + "px";
    ui.previa.width = Math.round(cssW * dpr);
    ui.previa.height = Math.round(cssH * dpr);
    desenharPrevia();
  }

  var pedidoDesenho = 0;
  function desenharPrevia() {
    if (!estado.foto || pedidoDesenho) { return; }
    pedidoDesenho = requestAnimationFrame(function () {
      pedidoDesenho = 0;
      if (!estado.foto) { return; }
      compor(ui.previa.getContext("2d"), ui.previa.width / E.FORMATOS[estado.formato].largura);
    });
  }

  /* Ponto do gesto em pixeis de saida, relativo ao canto da janela. */
  function pontoNaJanela(ev) {
    var r = ui.previa.getBoundingClientRect();
    var f = E.FORMATOS[estado.formato];
    var k = f.largura / r.width;
    return { x: (ev.clientX - r.left) * k - f.janela.x, y: (ev.clientY - r.top) * k - f.janela.y, k: k };
  }

  function centroDaJanela() { var j = janela(); return { x: j.w / 2, y: j.h / 2 }; }

  var dedos = {};
  function ligarGestos() {
    var c = ui.previa;
    c.addEventListener("pointerdown", function (ev) {
      if (!estado.foto) { return; }
      c.setPointerCapture(ev.pointerId);
      dedos[ev.pointerId] = pontoNaJanela(ev);
    });
    c.addEventListener("pointermove", function (ev) {
      if (!dedos[ev.pointerId] || !estado.foto) { return; }
      var ids = Object.keys(dedos);
      var novo = pontoNaJanela(ev);
      if (ids.length === 1) {
        var antes = dedos[ev.pointerId];
        dedos[ev.pointerId] = novo;
        aplicar(E.mover(estado.enq, novo.x - antes.x, novo.y - antes.y));
        return;
      }
      // Dois dedos: o meio desloca, a distancia aproxima, em torno do meio.
      var outro = dedos[ids[0] === String(ev.pointerId) ? ids[1] : ids[0]];
      var velho = dedos[ev.pointerId];
      var meioAntes = { x: (velho.x + outro.x) / 2, y: (velho.y + outro.y) / 2 };
      var meioDepois = { x: (novo.x + outro.x) / 2, y: (novo.y + outro.y) / 2 };
      var dAntes = Math.hypot(velho.x - outro.x, velho.y - outro.y);
      var dDepois = Math.hypot(novo.x - outro.x, novo.y - outro.y);
      dedos[ev.pointerId] = novo;
      var enq = E.mover(estado.enq, meioDepois.x - meioAntes.x, meioDepois.y - meioAntes.y);
      if (dAntes > 0) { enq = E.aproximar(enq, enq.s * dDepois / dAntes, meioDepois); }
      aplicar(enq);
    });
    function largar(ev) { delete dedos[ev.pointerId]; }
    c.addEventListener("pointerup", largar);
    c.addEventListener("pointercancel", largar);
    c.addEventListener("wheel", function (ev) {
      if (!estado.foto) { return; }
      ev.preventDefault();
      var dy = ev.deltaMode === 1 ? ev.deltaY * 16 : ev.deltaY;
      aplicar(E.aproximar(estado.enq, estado.enq.s * Math.exp(-dy * 0.0015), pontoNaJanela(ev)));
    }, { passive: false });
    c.addEventListener("keydown", function (ev) {
      if (!estado.foto) { return; }
      var passo = 40, enq = null;
      if (ev.key === "ArrowLeft") { enq = E.mover(estado.enq, passo, 0); }
      else if (ev.key === "ArrowRight") { enq = E.mover(estado.enq, -passo, 0); }
      else if (ev.key === "ArrowUp") { enq = E.mover(estado.enq, 0, passo); }
      else if (ev.key === "ArrowDown") { enq = E.mover(estado.enq, 0, -passo); }
      else if (ev.key === "+" || ev.key === "=") { enq = E.aproximar(estado.enq, estado.enq.s * 1.15, centroDaJanela()); }
      else if (ev.key === "-") { enq = E.aproximar(estado.enq, estado.enq.s / 1.15, centroDaJanela()); }
      if (enq) { ev.preventDefault(); aplicar(enq); }
    });
  }

  function passoDeZoom(fator) {
    if (estado.foto) { aplicar(E.aproximar(estado.enq, estado.enq.s * fator, centroDaJanela())); }
  }

  function escolherFormato(id) {
    if (id === estado.formato) { return; }
    var antes = janela();
    estado.formato = id;
    ui.formatos.forEach(function (b) { b.setAttribute("aria-pressed", String(b.getAttribute("data-formato") === id)); });
    if (!estado.foto) { return; }
    var enq = E.trocarJanela(estado.enq, antes, janela());
    recalcularLimites();
    ajustarPrevia();
    aplicar(enq);
  }

  function mensagem(texto) { ui.estado.textContent = texto || ""; }

  function aOcupar(sim) {
    estado.ocupado = sim;
    ui.dialogo.classList.toggle("pp-a-fotografar", sim);
    [ui.partilhar, ui.guardar, ui.repor, ui.mais, ui.menos, ui.zoom].concat(ui.formatos).forEach(function (b) { b.disabled = sim; });
  }

  function podePartilharFicheiros() {
    try {
      var teste = new File([new Blob([""], { type: "image/png" })], "teste.png", { type: "image/png" });
      return !!(navigator.share && navigator.canShare && navigator.canShare({ files: [teste] }));
    } catch (e) { return false; }
  }

  function enviar(ficheiro) {
    return navigator.share({ files: [ficheiro], title: NOME }).then(function () {
      mensagem("Partilhado. Mais lama no mundo.");
    }).catch(function (e) {
      if (e && e.name === "AbortError") { return; }
      if (e && e.name === "NotAllowedError") {
        mensagem("O browser pediu mais um toque. Carrega outra vez em Partilhar.");
        return;
      }
      mensagem("Não deu para partilhar daqui. Guarda a imagem e partilha-a a partir da galeria.");
    });
  }

  function partilhar() {
    contar("partilhar");
    mensagem("");
    // Com o ficheiro ja pronto, a partilha abre dentro do proprio toque.
    if (estado.ficheiro && estado.ficheiroVersao === estado.versao) { enviar(estado.ficheiro); return; }
    obterFicheiro().then(enviar).catch(function (e) { mensagem("A imagem não se gerou: " + e.message); });
  }

  function guardar() {
    contar("guardar");
    mensagem("");
    obterFicheiro().then(function (ficheiro) {
      var url = URL.createObjectURL(ficheiro);
      var a = el("a", { href: url, download: ficheiro.name, class: IGNORAR });
      document.body.appendChild(a);
      a.click();
      a.remove();
      setTimeout(function () { URL.revokeObjectURL(url); }, 60000);
      mensagem("Imagem guardada: " + ficheiro.name);
    }).catch(function (e) { mensagem("A imagem não se gerou: " + e.message); });
  }

  function construirEditor() {
    var botaoEditor = function (attrs, texto) {
      attrs.type = "button";
      attrs.class = "pp-botao" + (attrs.class ? " " + attrs.class : "");
      return el("button", Object.assign(attrs, { text: texto }));
    };
    ui.titulo = el("h2", { id: "pp-titulo", text: "Partilhar o chiqueiro" });
    ui.fechar = botaoEditor({ class: "pp-fechar", "aria-label": "Fechar" }, "×");
    ui.previa = el("canvas", { class: "pp-previa", tabindex: "0", role: "img",
      "aria-label": "Pré-visualização da imagem. Arrasta ou usa as setas para mover, e as teclas mais e menos para aproximar." });
    ui.aguarde = el("p", { class: "pp-aguarde", text: "A fotografar o chiqueiro." });
    ui.palco = el("div", { class: "pp-palco" }, [ui.previa, ui.aguarde]);
    ui.dica = el("p", { class: "pp-dica", text: "Arrasta para escolher o que entra. Para aproximar, usa dois dedos, a roda do rato ou o controlo." });
    ui.formatos = E.ORDEM.map(function (id) {
      return el("button", { type: "button", "data-formato": id, "aria-pressed": String(id === estado.formato), text: E.FORMATOS[id].rotulo });
    });
    var grupoFormatos = el("div", { class: "seletor pp-formatos", role: "group", "aria-label": "Formato da imagem" }, ui.formatos);
    ui.menos = botaoEditor({ class: "pp-redondo", "aria-label": "Afastar" }, "−");
    ui.zoom = el("input", { type: "range", min: "0", max: String(E.PASSOS), step: "1", value: "0", "aria-label": "Aproximação" });
    ui.mais = botaoEditor({ class: "pp-redondo", "aria-label": "Aproximar" }, "+");
    ui.repor = botaoEditor({}, "Repor");
    var linhaZoom = el("div", { class: "pp-zoom" }, [ui.menos, ui.zoom, ui.mais, ui.repor]);
    ui.partilhar = botaoEditor({ class: "pp-principal" }, "Partilhar");
    ui.guardar = botaoEditor({}, "Guardar imagem");
    var acoes = el("div", { class: "pp-acoes" }, [ui.partilhar, ui.guardar]);
    ui.estado = el("p", { class: "pp-estado", "aria-live": "polite" });
    ui.dialogo = el("dialog", { class: "ptv-partilha-dialogo " + IGNORAR, "aria-labelledby": "pp-titulo" }, [
      el("div", { class: "pp-cabeca" }, [ui.titulo, ui.fechar]),
      ui.palco, ui.dica, grupoFormatos, linhaZoom, acoes, ui.estado
    ]);
    document.body.appendChild(ui.dialogo);

    ui.fechar.addEventListener("click", fechar);
    ui.dialogo.addEventListener("close", aoFechar);
    ui.dialogo.addEventListener("cancel", function (ev) { ev.preventDefault(); fechar(); });
    ui.dialogo.addEventListener("keydown", function (ev) {
      // Sem showModal (browsers antigos), o Esc tem de fechar a mao.
      if (ev.key === "Escape" && typeof ui.dialogo.showModal !== "function") { fechar(); }
    });
    ui.formatos.forEach(function (b) { b.addEventListener("click", function () { escolherFormato(b.getAttribute("data-formato")); }); });
    ui.menos.addEventListener("click", function () { passoDeZoom(1 / 1.25); });
    ui.mais.addEventListener("click", function () { passoDeZoom(1.25); });
    ui.zoom.addEventListener("input", function () {
      if (estado.foto) { aplicar(E.aproximar(estado.enq, E.escalaDoControlo(Number(ui.zoom.value), estado.lim), centroDaJanela())); }
    });
    ui.repor.addEventListener("click", function () { if (estado.foto) { repor(); } });
    ui.partilhar.addEventListener("click", partilhar);
    ui.guardar.addEventListener("click", guardar);
    ligarGestos();
    if (window.ResizeObserver) { new ResizeObserver(ajustarPrevia).observe(ui.palco); }
    else { window.addEventListener("resize", ajustarPrevia); }
  }

  function abrir() {
    if (!pronto() || estado.aberto) { return; }
    // Medido antes de tudo o resto: abrir o editor ja e mexer no ecra.
    estado.visivel = medirVisivel();
    estado.coluna = medirColuna();
    estado.aberto = true;
    // Uma fotografia que acaba depois de o editor fechar e reabrir
    // pertence a abertura anterior e nao pode substituir a nova.
    var sessao = ++estado.sessao;
    contar("abrir");
    if (!ui.dialogo) { construirEditor(); }
    ui.partilhar.hidden = !podePartilharFicheiros();
    ui.guardar.classList.toggle("pp-principal", ui.partilhar.hidden);
    mensagem("");
    aOcupar(true);
    if (typeof ui.dialogo.showModal === "function") { ui.dialogo.showModal(); }
    else { ui.dialogo.setAttribute("open", ""); }
    Promise.all([carregarBiblioteca(), carregarIcone(), carregarTipos()]).then(function (r) {
      estado.icone = r[1];
      return fotografar(sessao);
    }).then(function () {
      if (!estado.aberto || sessao !== estado.sessao) { return; }
      aOcupar(false);
      repor();
      ajustarPrevia();
      ui.previa.focus({ preventScroll: true });
    }).catch(function (e) {
      if (sessao !== estado.sessao) { return; }
      ui.aguarde.textContent = "Não foi possível fotografar a página.";
      mensagem(e && e.message ? e.message : "");
    });
  }

  function fechar() {
    if (typeof ui.dialogo.close === "function" && ui.dialogo.open) { ui.dialogo.close(); }
    else { ui.dialogo.removeAttribute("open"); aoFechar(); }
  }

  /* A fotografia da pagina ocupa dezenas de megabytes de memoria num
     telemovel. Larga-se ao fechar: na partilha seguinte a pagina pode ja
     nao ser a mesma, e o enquadramento recomeca do que estiver no ecra. */
  function aoFechar() {
    if (!estado.aberto) { return; }
    estado.aberto = false;
    estado.foto = null;
    estado.ficheiro = null;
    estado.ficheiroVersao = -1;
    clearTimeout(estado.temporizador);
    dedos = {};
    ui.aguarde.textContent = "A fotografar o chiqueiro.";
    ui.previa.width = 0;
    ui.previa.height = 0;
    ui.botao.focus({ preventScroll: true });
  }

  /* ---- botao -------------------------------------------------------- */

  ui.botao = el("button", {
    type: "button",
    class: "ptv-partilhar " + IGNORAR,
    "aria-label": "Partilhar o que está no ecrã",
    title: "Partilhar o que está no ecrã",
    html: '<svg viewBox="0 0 24 24" width="26" height="26" aria-hidden="true" focusable="false" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"><path d="M12 14.5V3.5"/><path d="M7.5 8L12 3.5 16.5 8"/><path d="M5 12.5v6a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-6"/></svg>'
  });
  ui.botao.addEventListener("click", abrir);
  document.body.appendChild(ui.botao);
  atualizarBotao();

  /* "position: fixed" ancora-se ao viewport de layout, e nao ao que se ve.
     Os dois separam-se quando a pessoa aproxima com dois dedos, e quando
     a pagina e mais larga do que o ecra: a 2026-10-27, a tabela das
     Fontes punha a pagina com 500 pixeis num telemovel de 390, e o botao
     ficava fora do ecra, a direita. Quando se separam, o botao desloca-se
     para o canto do que se ve e mantem o tamanho a vista. Usa as
     propriedades translate e scale, e nao transform, para nao apagar o
     efeito de carregar; onde nao existem, o botao fica onde o CSS o pos,
     que e o comportamento de sempre. */
  var pedidoPosicao = 0;
  function posicionar() {
    pedidoPosicao = 0;
    var vv = window.visualViewport, b = ui.botao;
    if (!vv || !("translate" in b.style)) { return; }
    b.style.translate = "";
    b.style.scale = "";
    var cs = getComputedStyle(b);
    var c = E.correcaoDoBotao(b.getBoundingClientRect(), vv,
      { direita: parseFloat(cs.right), baixo: parseFloat(cs.bottom) });
    if (!c) { return; }
    b.style.transformOrigin = "100% 100%";
    b.style.translate = c.dx + "px " + c.dy + "px";
    b.style.scale = String(c.k);
  }
  function pedirPosicao() { if (!pedidoPosicao) { pedidoPosicao = requestAnimationFrame(posicionar); } }
  if (window.visualViewport) {
    window.visualViewport.addEventListener("resize", pedirPosicao);
    window.visualViewport.addEventListener("scroll", pedirPosicao);
  }
  window.addEventListener("scroll", pedirPosicao, { passive: true });
  window.addEventListener("resize", pedirPosicao);
  // O viewport de layout cresce quando a pagina insere a tabela, e isso
  // nao dispara resize nenhum: medido a 2026-10-27 nas Fontes, o botao
  // ficava fora do ecra ate ao primeiro scroll. O body cresce na mesma
  // altura, e e isso que se vigia.
  if (window.ResizeObserver) { new ResizeObserver(pedirPosicao).observe(document.body); }
  pedirPosicao();
  if (!pronto() && window.MutationObserver) {
    var vigia = new MutationObserver(function () {
      atualizarBotao();
      if (pronto()) { vigia.disconnect(); }
    });
    vigia.observe(document.documentElement, { attributes: true, attributeFilter: ["data-pronto"] });
  }
})();
