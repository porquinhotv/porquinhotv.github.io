/* Pagina de comparacao. O conteudo vem inteiro no HTML, escrito pelo
   gerador (`ferramentas/comparacao.py`, dentro do `gerar_seo`) a partir
   do `config/comparacao.yml` e dos dados publicados. Aqui nao se calcula
   nada: os numeros tem uma origem so, e ha um teste que falha se o HTML
   publicado ficar atras dos dados.

   So se faz o que as outras paginas fazem no fim do carregamento: a data
   da ultima recolha no rodape, e libertar o botao de partilha. Se o
   resumo nao carregar, o botao liberta-se na mesma, porque a pagina ja
   esta completa e nao vai mudar; o painel de erro das outras paginas
   apagaria aqui um conteudo que esta certo. */

(function () {
  "use strict";
  PTVDOM.carregar("dados/resumo.json")
    .then(PTVDOM.marcarGerado)
    .catch(function () { PTVDOM.marcarPronto(); });
})();
