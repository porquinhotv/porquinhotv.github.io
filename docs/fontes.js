/* Lista todas as entrevistas exclusivas com as respetivas provas, por
   ano, da mais recente para a mais antiga. Le dados/entrevistas.json e o
   resumo para os nomes dos canais. Nao calcula nada.

   Uma entrevista pode ter passado em mais do que um canal. Quando isso
   acontece a linha diz em qual ficou contada e em que outro passou, e a
   coluna da prova traz uma ligacao por canal: quem contesta a atribuicao
   abre as duas paginas a partir daqui. */

(function () {
  "use strict";
  var el = PTVDOM.el;

  /* "também na TVI", "também na TVI e na CNN Portugal". O primeiro canal
     da lista e aquele a que a entrevista esta atribuida, e nao entra. */
  function notaDosOutrosCanais(canais, nomeDe) {
    var outros = (canais || []).slice(1).map(function (id) { return nomeDe[id] || id; });
    if (!outros.length) { return null; }
    var texto = outros.length === 1
      ? outros[0]
      : outros.slice(0, -1).join(", ") + " e na " + outros[outros.length - 1];
    return el("span", { class: "parcial", text: " (também na " + texto + ")" });
  }

  /* Uma ligacao por transmissao. Com um canal so, o rotulo diz o tipo de
     prova, como sempre disse; com mais do que um, diz o canal, porque e
     essa a pergunta que a linha levanta. */
  function provas(entrevista, nomeDe) {
    var lista = entrevista.transmissoes || [entrevista];
    var varias = lista.length > 1;
    var celula = el("td", {});
    lista.forEach(function (t, i) {
      if (i > 0) { celula.appendChild(document.createTextNode(", ")); }
      var rotulo = varias ? (nomeDe[t.canal] || t.canal) : (t.origem === "imprensa" ? "notícia" : "ver");
      celula.appendChild(el("a", { href: t.prova_url, rel: "noopener noreferrer", target: "_blank", text: rotulo }));
      if (t.origem === "imprensa") { celula.appendChild(el("span", { class: "parcial", text: " (imprensa)" })); }
    });
    return celula;
  }

  /* Sem coluna de programa desde 2026-10-21: o que se conta e o canal, e o
     programa e o titulo eram texto copiado das paginas de prova, muitas
     vezes vazio ou "nao apurado" (54 das 79 linhas visiveis em
     2026-10-21). Os campos continuam nos dados; so deixam de ser
     mostrados. As colunas tem de ser as mesmas do bloco pre-renderizado
     em `ferramentas/seo.py`, e ha um teste que o verifica. */
  function tabela(linhas, nomeDe) {
    var t = el("table", { class: "tabela" });
    t.appendChild(el("thead", {}, [el("tr", {}, ["Data", "Canal", "Prova"].map(function (h) { return el("th", { text: h }); }))]));
    var corpo = el("tbody");
    linhas.forEach(function (l) {
      var canal = el("td", { class: "canal", text: nomeDe[l.canal] || l.canal });
      canal.style.setProperty("--cor", PTVDOM.corDoCanal(l.canal));
      var nota = notaDosOutrosCanais(l.canais, nomeDe);
      if (nota) { canal.appendChild(nota); }
      var data = el("td", { text: l.data });
      if (l.data_origem !== "declarada") { data.appendChild(el("span", { class: "parcial", text: " (publicação)" })); }
      corpo.appendChild(el("tr", {}, [data, canal, provas(l, nomeDe)]));
    });
    t.appendChild(corpo);
    return t;
  }

  Promise.all([PTVDOM.carregar("dados/entrevistas.json"), PTVDOM.carregar("dados/resumo.json")])
    .then(function (r) {
      var resumo = r[1];
      PTVDOM.marcarGerado(resumo);
      /* Ambito visivel: o dataset guarda tudo desde 2019, o site mostra e
         conta a partir do corte que o resumo declara. Um resumo gerado
         antes de 2026-09-11 ainda nao traz `ambito`; nesse caso mostra-se
         tudo, como dantes. */
      var ambito = resumo.ambito || { visivel_desde: (resumo.tema && resumo.tema.desde) || "" };
      var todas = r[0].entrevistas || [];
      var entrevistas = todas.filter(function (e) { return e.data >= ambito.visivel_desde; });
      var nomeDe = {};
      resumo.por_canal.forEach(function (c) { nomeDe[c.canal] = c.nome; });
      var alvo = document.getElementById("conteudo");
      alvo.innerHTML = "";
      if (!entrevistas.length) {
        alvo.appendChild(el("div", { class: "cartao vazio" }, [el("h2", { text: "Ainda sem dados" }), el("p", { text: "Ainda não há entrevistas registadas." })]));
        return;
      }
      var porAno = {};
      entrevistas.forEach(function (e) { (porAno[e.data.slice(0, 4)] = porAno[e.data.slice(0, 4)] || []).push(e); });
      Object.keys(porAno).sort().reverse().forEach(function (ano) {
        var linhas = porAno[ano].sort(function (a, b) { return b.data.localeCompare(a.data) || a.canal.localeCompare(b.canal); });
        var s = el("section", {}, [el("h2", { text: ano + ": " + linhas.length + (linhas.length === 1 ? " entrevista exclusiva" : " entrevistas exclusivas") })]);
        s.appendChild(tabela(linhas, nomeDe));
        alvo.appendChild(s);
      });
    })
    .catch(function (e) { document.getElementById("conteudo").innerHTML = ""; PTVDOM.mostrarErro("Não foi possível carregar os dados. " + e.message); });
})();
