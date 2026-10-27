// Testes do enquadramento da imagem de partilha. Correr: node --test tests/frontend
// Sem browser. Os numeros das paginas sao os medidos no Chromium a
// 2026-10-27 (largura e altura do documento, e o que se via no ecra).
const test = require("node:test");
const assert = require("node:assert/strict");

const E = require("../../docs/enquadramento.js");

const HISTORIA = E.FORMATOS.historia;
const PUBLICACAO = E.FORMATOS.publicacao;

function quase(a, b, msg) { assert.ok(Math.abs(a - b) < 1e-6, `${msg}: ${a} != ${b}`); }

// O que a janela mostra da pagina, em pixeis CSS.
function vista(enq, janela) {
  return { x0: enq.x, y0: enq.y, x1: enq.x + janela.w / enq.s, y1: enq.y + janela.h / enq.s };
}

test("no telemovel a imagem enche a largura, sem faixas de ceu, e comeca onde o ecra comecava", () => {
  // Decisao do autor a 2026-10-27, depois de ver a primeira versao: fazer
  // caber o ecra inteiro deixava 120 pixeis de ceu de cada lado. Prefere
  // perder altura. Pagina principal num ecra de 390x844, depois de descer
  // 500 pixeis, medida no Chromium.
  const pagina = { w: 390, h: 3174 };
  const visivel = { x: 0, y: 500, w: 390, h: 844 };
  const j = HISTORIA.janela;
  const enq = E.inicial(pagina, visivel, { x: 0, w: 390 }, j);
  const r = E.recorte(enq, pagina, j);
  quase(r.dx, 0, "nada de ceu a esquerda");
  quase(r.dw, j.w, "nada de ceu a direita");
  quase(r.sx, 0, "a largura do ecra inteira");
  quase(r.sw, 390, "e so ela");
  quase(r.sy, 500, "a imagem comeca no topo do ecra");
  quase(r.dh, j.h, "a janela enche em altura");
  assert.ok(r.sy + r.sh < 500 + 844, "o que nao cabe fica de fora em baixo");
});

test("nas Fontes em mobile a largura que conta e a do ecra, nao a da pagina alargada", () => {
  // A tabela poe a pagina com 500 pixeis num ecra de 390. Encher com 500
  // mostrava o que nao estava no ecra; encher com 390 e o que se via.
  const pagina = { w: 500, h: 6272 };
  const enq = E.inicial(pagina, { x: 0, y: 1200, w: 390, h: 844 }, { x: 0, w: 390 }, HISTORIA.janela);
  const v = vista(enq, HISTORIA.janela);
  quase(v.x0, 0, "comeca na esquerda do ecra");
  quase(v.x1, 390, "acaba na direita do ecra");
});

test("afastar continua a chegar ao ecra inteiro, se a pessoa o quiser", () => {
  // As faixas deixaram de ser o inicial, mas nao foram proibidas: quem
  // quiser a altura toda do ecra afasta e tem-na.
  const pagina = { w: 390, h: 3174 };
  const visivel = { x: 0, y: 500, w: 390, h: 844 };
  const j = HISTORIA.janela;
  const s0 = E.inicial(pagina, visivel, null, j).s;
  const sContem = E.escalaQueContem(visivel, null, j);
  const lim = E.limites(pagina, j, s0, sContem);
  assert.ok(lim.sMin <= sContem, "o afastamento chega ao ecra inteiro");
  const v = vista(E.limitar({ s: sContem, x: 0, y: 500 }, pagina, j, lim), j);
  assert.ok(v.y1 >= 500 + 844 - 1e-6, "e o fundo do ecra cabe");
});

test("no desktop conta a coluna de conteudo, e nao o ceu dos lados", () => {
  // 1366 de ecra e 860 de coluna: contar com os lados punha o texto a um
  // terco do tamanho sem mostrar nada que se lesse.
  const pagina = { w: 1366, h: 2306 };
  const visivel = { x: 0, y: 0, w: 1366, h: 768 };
  const enq = E.inicial(pagina, visivel, { x: 253, w: 860 }, HISTORIA.janela);
  quase(enq.s, HISTORIA.janela.w / 860, "a coluna enche a largura da janela");
  quase(enq.x, 253, "a janela comeca na coluna");
  quase(enq.y, 0, "e no topo do ecra");
});

test("a janela nunca sai de uma pagina que a enche, e centra uma que nao enche", () => {
  const pagina = { w: 390, h: 3174 };
  const j = HISTORIA.janela;
  const lim = E.limites(pagina, j, 2.5);
  const fora = E.limitar({ s: 2.5, x: -200, y: 99999 }, pagina, j, lim);
  const v = vista(fora, j);
  quase(v.y1, 3174, "nao passa do fim da pagina");
  quase(fora.x, (390 - j.w / 2.5) / 2, "pagina mais estreita do que a janela fica ao centro");
  const cima = E.limitar({ s: 2.5, x: 0, y: -50 }, pagina, j, lim);
  quase(cima.y, 0, "nao passa do topo");
});

test("os limites da aproximacao incluem sempre o enquadramento inicial", () => {
  // Um limite que cortasse o inicial obrigava o editor a abrir com outra
  // coisa que nao o ecra.
  for (const [pagina, s0] of [[{ w: 390, h: 3174 }, 1.56], [{ w: 1366, h: 2306 }, 1.14], [{ w: 500, h: 6272 }, 1.56]]) {
    const lim = E.limites(pagina, HISTORIA.janela, s0);
    assert.ok(lim.sMin <= s0 && s0 <= lim.sMax, JSON.stringify(pagina));
    quase(E.limitar({ s: s0, x: 0, y: 0 }, pagina, HISTORIA.janela, lim).s, s0, "nao mexe na escala inicial");
  }
});

test("aproximar deixa parado o ponto debaixo do dedo", () => {
  const antes = { s: 2, x: 10, y: 400 };
  const ponto = { x: 300, y: 500 };
  const depois = E.aproximar(antes, 3, ponto);
  quase(antes.x + ponto.x / antes.s, depois.x + ponto.x / depois.s, "x");
  quase(antes.y + ponto.y / antes.s, depois.y + ponto.y / depois.s, "y");
});

test("arrastar para cima mostra o que esta mais abaixo na pagina", () => {
  const enq = E.mover({ s: 2, x: 0, y: 100 }, 0, -80);
  quase(enq.y, 140, "80 pixeis de saida a escala 2 sao 40 da pagina");
});

test("trocar de formato mantem a escala e o centro do que se escolheu", () => {
  // As duas janelas tem a mesma largura; e isso que faz a troca nao mexer
  // no que se ve de lado a lado. Se uma delas mudar, este teste avisa.
  assert.equal(HISTORIA.janela.w, PUBLICACAO.janela.w);
  const antes = { s: 1.7, x: 20, y: 300 };
  const depois = E.trocarJanela(antes, HISTORIA.janela, PUBLICACAO.janela);
  quase(depois.s, antes.s, "escala");
  quase(depois.x + PUBLICACAO.janela.w / (2 * depois.s), antes.x + HISTORIA.janela.w / (2 * antes.s), "centro x");
  quase(depois.y + PUBLICACAO.janela.h / (2 * depois.s), antes.y + HISTORIA.janela.h / (2 * antes.s), "centro y");
});

test("o recorte nunca pede a fotografia fora da pagina", () => {
  // Versoes antigas do Safari nao desenham nada quando o retangulo de
  // origem sai da imagem. Pagina de 390 numa janela que mostra 629.
  const j = HISTORIA.janela;
  const s = j.h / 844;
  const enq = { s: s, x: (390 - j.w / s) / 2, y: 3174 - j.h / s + 100 };
  const r = E.recorte(enq, { w: 390, h: 3174 }, j);
  assert.ok(r.sx >= 0 && r.sy >= 0, "origem dentro");
  assert.ok(r.sx + r.sw <= 390 + 1e-9 && r.sy + r.sh <= 3174 + 1e-9, "fim dentro");
  quase(r.dw, r.sw * s, "o destino tem a mesma proporcao");
  assert.ok(r.dx > 0, "a pagina comeca depois da margem de ceu");
  assert.equal(E.recorte({ s: 1, x: 5000, y: 0 }, { w: 390, h: 3174 }, j), null);
});

test("a fotografia da pagina mais comprida fica abaixo do limite do Safari do iPhone", () => {
  // Acima de 16 777 216 pixeis de area, o Safari devolve um canvas em
  // branco sem erro. As Fontes, medidas a 2026-10-27, tem 500x6272.
  const fontes = { w: 500, h: 6272 };
  const s = E.escalaDeCaptura(fontes, 3);
  assert.ok(fontes.w * fontes.h * s * s <= 16000000, "area");
  assert.equal(s, 2, "a escala maxima cabe");
  // Uma pagina tres vezes mais comprida ainda tem de caber.
  const longa = { w: 390, h: 20000 };
  const sl = E.escalaDeCaptura(longa, 3);
  assert.ok(longa.w * longa.h * sl * sl <= 16000000, "area da pagina longa");
  assert.ok(longa.h * sl <= 16000, "lado da pagina longa");
});

test("o controlo de aproximacao vai e volta sem perder a escala", () => {
  const lim = { sMin: 0.7, sMax: 10 };
  for (const s of [0.7, 1.56, 4, 10]) {
    const v = E.controloDaEscala(s, lim);
    assert.ok(v >= 0 && v <= E.PASSOS);
    assert.ok(Math.abs(E.escalaDoControlo(v, lim) / s - 1) < 0.003, `s=${s}`);
  }
  assert.equal(E.controloDaEscala(2, { sMin: 2, sMax: 2 }), 0, "limites iguais nao dividem por zero");
});

test("a imagem vai de ponta a ponta, sem moldura, e a marca fica acima da caixa de legenda", () => {
  // Decisao do autor a 2026-10-27, depois de ver a primeira versao numa
  // story: sem moldura, sem margens, sem erva em baixo, e a marca mais
  // abaixo. Medido na captura dele do editor de stories: a caixa "Add a
  // caption" comeca por volta dos 1815 pixeis. A marca tem de acabar antes.
  const m = HISTORIA.marca;
  assert.ok(m.cy + m.icone / 2 <= 1800, "marca acima da caixa de legenda");
  assert.ok(m.cy > 1622, "mais abaixo do que na primeira versao");
  for (const f of [HISTORIA, PUBLICACAO]) {
    assert.equal(f.janela.x, 0, `${f.id}: sem margem a esquerda`);
    assert.equal(f.janela.y, 0, `${f.id}: sem margem em cima`);
    assert.equal(f.janela.w, f.largura, `${f.id}: a pagina ocupa a largura toda`);
    for (const campo of ["borda", "sombra", "raio"]) {
      assert.equal(f.janela[campo], undefined, `${f.id}: a moldura voltou (${campo})`);
    }
    assert.equal(f.erva, undefined, `${f.id}: a erva voltou`);
    assert.ok(f.janela.y + f.janela.h < f.marca.cy - f.marca.icone / 2, `${f.id}: a pagina nao toca na marca`);
    assert.ok(f.marca.cy + f.marca.icone / 2 < f.altura, `${f.id}: a marca cabe na imagem`);
    assert.equal(f.largura, 1080, `${f.id}: largura das redes`);
  }
  assert.equal(HISTORIA.altura / HISTORIA.largura, 16 / 9);
  assert.equal(PUBLICACAO.altura / PUBLICACAO.largura, 5 / 4);
});

test("o botao fora do ecra nas Fontes em mobile volta ao canto do que se ve", () => {
  // Defeito real, 2026-10-27: a tabela das Fontes punha o viewport de
  // layout em 500x1080 num telemovel de 390x844, e o botao fixo ficava em
  // (426, 1006), abaixo e a direita do ecra. Numeros medidos no Chromium.
  const c = E.correcaoDoBotao({ right: 484, bottom: 1064 },
    { offsetLeft: 0, offsetTop: 0, width: 390, height: 844, scale: 1 }, { direita: 16, baixo: 16 });
  assert.deepEqual(c, { dx: -110, dy: -236, k: 1 });
});

test("com dois dedos a aproximar, o botao segue o canto e mantem o tamanho a vista", () => {
  // Nao verificado num browser: o gesto sintetico do Chromium sem ecra
  // nao muda a escala. A conta e a mesma do caso das Fontes.
  const c = E.correcaoDoBotao({ right: 374, bottom: 828 },
    { offsetLeft: 100, offsetTop: 200, width: 195, height: 422, scale: 2 }, { direita: 16, baixo: 16 });
  quase(c.k, 0.5, "metade do tamanho na pagina e o mesmo tamanho no ecra");
  quase(374 + c.dx, 100 + 195 - 8, "canto direito do que se ve, menos a margem a escala");
  quase(828 + c.dy, 200 + 422 - 8, "canto de baixo");
});

test("sem separacao entre os dois viewports, o botao fica onde o CSS o pos", () => {
  assert.equal(E.correcaoDoBotao({ right: 374, bottom: 828 },
    { offsetLeft: 0, offsetTop: 0, width: 390, height: 844, scale: 1 }, { direita: 16, baixo: 16 }), null);
});

test("o nome do ficheiro diz o dia e o formato", () => {
  assert.equal(E.nomeDoFicheiro(new Date(2026, 9, 7), "historia"), "porquinho-tv-2026-10-07-stories.png");
  assert.equal(E.nomeDoFicheiro(new Date(2026, 0, 31), "publicacao"), "porquinho-tv-2026-01-31-4x5.png");
});
