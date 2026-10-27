/* Enquadramento da imagem de partilha. Logica pura, sem DOM: carrega no
   browser como PTVEnquadramento e no Node como modulo, para que os testes
   em tests/frontend corram sem browser, no mesmo molde da logica.js.

   Unidades, para nao se misturarem: a pagina mede-se em pixeis CSS do
   documento; a imagem de saida mede-se em pixeis da imagem (1080 de
   largura). Um enquadramento e { s, x, y }: s pixeis de saida por pixel
   CSS, e (x, y) o ponto da pagina que fica no canto superior esquerdo da
   janela. */

(function (raiz, fabrica) {
  if (typeof module === "object" && module.exports) { module.exports = fabrica(); }
  else { raiz.PTVEnquadramento = fabrica(); }
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  /* Dois formatos, decididos pelo autor a 2026-10-27: stories por
     omissao, e 4:5 para o feed do Facebook, do X e do Instagram.

     A pagina ocupa a imagem de ponta a ponta, sem moldura, e a marca fica
     numa faixa em baixo. Decisao do autor a 2026-10-27, depois de ver a
     primeira versao numa story: a moldura preta, as margens e a erva em
     baixo eram confusao visual e tiravam largura a pagina.

     A marca desce ate onde a interface do Instagram a deixa. Medido na
     captura do autor do editor de stories, a 2026-10-27: a caixa "Add a
     caption" comeca por volta dos 1815 pixeis da imagem. O fundo do icone
     fica nos 1786. O topo da imagem fica por baixo dos botoes do editor,
     como em qualquer story; e a pagina que la esta, nao a marca.

     O esbatido e a passagem da pagina para a faixa da marca: sem moldura,
     um corte seco a meio de um cartao parecia um erro. No 4:5 nao ha
     interface por cima. */
  var FORMATOS = {
    historia: {
      id: "historia", rotulo: "Stories 9:16", sufixo: "stories",
      largura: 1080, altura: 1920,
      janela: { x: 0, y: 0, w: 1080, h: 1630, esbatido: 40 },
      marca: { cy: 1730, icone: 112, nome: 76, endereco: 36, intervalo: 26 }
    },
    publicacao: {
      id: "publicacao", rotulo: "Publicação 4:5", sufixo: "4x5",
      largura: 1080, altura: 1350,
      janela: { x: 0, y: 0, w: 1080, h: 1160, esbatido: 32 },
      marca: { cy: 1258, icone: 92, nome: 62, endereco: 30, intervalo: 22 }
    }
  };
  var ORDEM = ["historia", "publicacao"];

  /* Limites do canvas em que a pagina e fotografada. O Safari do iPhone
     recusa canvas acima de 16 777 216 pixeis de area e devolve uma
     imagem em branco sem erro; fica-se abaixo com folga. 16000 por lado
     cobre o Firefox, que para nos 32767. Acima de 2 nao se ganha nada
     visivel numa saida de 1080 de largura e paga-se em memoria. */
  var AREA_MAXIMA = 16000000;
  var LADO_MAXIMO = 16000;
  var ESCALA_MAXIMA = 2;

  function escalaDeCaptura(pagina, dpr) {
    var s = Math.min(dpr > 0 ? dpr : 1, ESCALA_MAXIMA);
    s = Math.min(s, Math.sqrt(AREA_MAXIMA / (pagina.w * pagina.h)));
    s = Math.min(s, LADO_MAXIMO / pagina.w, LADO_MAXIMO / pagina.h);
    return s;
  }

  /* A zona do ecra que conta. Quando o ecra e mais largo do que a coluna
     de conteudo (no desktop sao 860 pixeis num ecra de 1366), a largura
     que conta e a da coluna: os lados sao ceu liso, e contar com eles
     poria o texto a um terco do tamanho sem mostrar nada a mais. */
  function regiao(visivel, coluna) {
    var r = { x: visivel.x, y: visivel.y, w: visivel.w, h: visivel.h };
    if (coluna && coluna.w > 0 && coluna.w < r.w) {
      var esq = Math.max(r.x, coluna.x);
      var dir = Math.min(r.x + r.w, coluna.x + coluna.w);
      if (dir > esq) { r.x = esq; r.w = dir - esq; }
    }
    return r;
  }

  /* O enquadramento inicial enche a largura da janela com a largura do
     que se via, a comecar no topo do ecra, porque e por ai que quem le
     comeca; o que nao cabe em altura fica de fora em baixo. Decisao do
     autor a 2026-10-27: a primeira versao fazia caber o ecra inteiro, e
     num telemovel (390x844 numa janela de 984x1320) isso deixava duas
     faixas de ceu de 120 pixeis da pagina de cada lado e o texto a 62% do
     tamanho. O autor prefere perder altura e encher a imagem. No desktop
     nao muda nada: ai a coluna ja enchia a largura antes de faltar altura. */
  function inicial(pagina, visivel, coluna, janela) {
    var r = regiao(visivel, coluna);
    var s = janela.w / r.w;
    return limitar({ s: s, x: r.x, y: r.y }, pagina, janela, limites(pagina, janela, s, escalaQueContem(visivel, coluna, janela)));
  }

  /* A escala a que o ecra inteiro cabe na janela, com as faixas de ceu
     que isso traz. Ja nao e o inicial, mas continua a ser um sitio onde a
     pessoa pode querer chegar a afastar. */
  function escalaQueContem(visivel, coluna, janela) {
    var r = regiao(visivel, coluna);
    return Math.min(janela.w / r.w, janela.h / r.h);
  }

  /* Afastar ate caber a largura toda da pagina, ou ate caber o ecra
     inteiro, o que for mais longe, e nunca menos do que o inicial;
     aproximar ate quatro vezes. Mais longe so acrescenta ceu dos lados,
     mais perto e um pixel ampliado. */
  function limites(pagina, janela, sInicial, sContem) {
    var largura = janela.w / pagina.w;
    var sMin = Math.min(largura, sInicial, sContem > 0 ? sContem : sInicial);
    return { sMin: sMin, sMax: Math.max(largura, sInicial) * 4 };
  }

  /* A janela nunca sai da pagina num eixo em que a pagina a enche; num
     eixo em que nao enche, a pagina fica centrada. Sem isto, um gesto
     largo deixava a imagem toda em ceu. */
  function limitarEixo(pos, tamPagina, tamVisto) {
    if (tamPagina <= tamVisto) { return (tamPagina - tamVisto) / 2; }
    return Math.min(Math.max(pos, 0), tamPagina - tamVisto);
  }

  function limitar(enq, pagina, janela, lim) {
    var s = Math.min(Math.max(enq.s, lim.sMin), lim.sMax);
    return {
      s: s,
      x: limitarEixo(enq.x, pagina.w, janela.w / s),
      y: limitarEixo(enq.y, pagina.h, janela.h / s)
    };
  }

  function mover(enq, dx, dy) {
    return { s: enq.s, x: enq.x - dx / enq.s, y: enq.y - dy / enq.s };
  }

  /* Aproximar mantendo parado o ponto da pagina que esta debaixo do dedo
     ou do cursor, como em qualquer mapa: aproximar para o centro obrigava
     a corrigir com um arrasto a seguir a cada gesto. */
  function aproximar(enq, novaS, ponto) {
    var px = enq.x + ponto.x / enq.s;
    var py = enq.y + ponto.y / enq.s;
    return { s: novaS, x: px - ponto.x / novaS, y: py - ponto.y / novaS };
  }

  /* Trocar de formato mantem a escala e o centro do que se escolheu: as
     duas janelas tem a mesma largura, por isso o que se ve de lado a lado
     nao muda, so a altura. */
  function trocarJanela(enq, janelaAntes, janelaDepois) {
    var cx = enq.x + janelaAntes.w / (2 * enq.s);
    var cy = enq.y + janelaAntes.h / (2 * enq.s);
    return { s: enq.s, x: cx - janelaDepois.w / (2 * enq.s), y: cy - janelaDepois.h / (2 * enq.s) };
  }

  /* O retangulo a copiar da fotografia da pagina e onde cai na janela.
     Calculado a mao, e nao deixado ao drawImage, porque um retangulo de
     origem que sai da imagem e tratado de forma diferente entre browsers,
     e versoes antigas do Safari nao desenham nada. Devolve null quando
     nao ha interseccao. Origem em pixeis CSS, destino em pixeis de saida
     relativos ao canto da janela. */
  function recorte(enq, pagina, janela) {
    var x0 = Math.max(enq.x, 0);
    var y0 = Math.max(enq.y, 0);
    var x1 = Math.min(enq.x + janela.w / enq.s, pagina.w);
    var y1 = Math.min(enq.y + janela.h / enq.s, pagina.h);
    if (x1 <= x0 || y1 <= y0) { return null; }
    return {
      sx: x0, sy: y0, sw: x1 - x0, sh: y1 - y0,
      dx: (x0 - enq.x) * enq.s, dy: (y0 - enq.y) * enq.s,
      dw: (x1 - x0) * enq.s, dh: (y1 - y0) * enq.s
    };
  }

  /* O controlo de aproximacao anda em escala logaritmica: em linear, a
     metade de cima do curso fazia quase tudo e a de baixo quase nada. */
  var PASSOS = 1000;
  function escalaDoControlo(v, lim) {
    return lim.sMin * Math.pow(lim.sMax / lim.sMin, v / PASSOS);
  }
  function controloDaEscala(s, lim) {
    if (lim.sMax <= lim.sMin) { return 0; }
    return Math.round(PASSOS * Math.log(s / lim.sMin) / Math.log(lim.sMax / lim.sMin));
  }

  /* Quanto deslocar e escalar o botao fixo para que fique no canto do
     que se ve. "position: fixed" ancora-se ao viewport de layout, e os
     dois separam-se quando a pagina e mais larga do que o ecra ou quando
     se aproxima com dois dedos. botao e o retangulo do botao sem
     correcao, vv o visualViewport, margem o right e o bottom do CSS.
     Devolve null quando nao ha nada a corrigir. */
  function correcaoDoBotao(botao, vv, margem) {
    var k = 1 / vv.scale;
    var dx = vv.offsetLeft + vv.width - margem.direita * k - botao.right;
    var dy = vv.offsetTop + vv.height - margem.baixo * k - botao.bottom;
    if (Math.abs(dx) < 0.5 && Math.abs(dy) < 0.5 && Math.abs(k - 1) < 0.01) { return null; }
    return { dx: dx, dy: dy, k: k };
  }

  function nomeDoFicheiro(data, formato) {
    function dois(n) { return (n < 10 ? "0" : "") + n; }
    var dia = data.getFullYear() + "-" + dois(data.getMonth() + 1) + "-" + dois(data.getDate());
    return "porquinho-tv-" + dia + "-" + FORMATOS[formato].sufixo + ".png";
  }

  return {
    FORMATOS: FORMATOS,
    ORDEM: ORDEM,
    PASSOS: PASSOS,
    escalaDeCaptura: escalaDeCaptura,
    inicial: inicial,
    escalaQueContem: escalaQueContem,
    limites: limites,
    limitar: limitar,
    mover: mover,
    aproximar: aproximar,
    trocarJanela: trocarJanela,
    recorte: recorte,
    escalaDoControlo: escalaDoControlo,
    controloDaEscala: controloDaEscala,
    correcaoDoBotao: correcaoDoBotao,
    nomeDoFicheiro: nomeDoFicheiro
  };
});
