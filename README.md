# Porquinho TV

Quantas entrevistas exclusivas deu André Ventura na televisão portuguesa. Um site estático, uma contagem pública, uma fonte por linha.

O site publica, por período (semana, mês, ano, desde sempre), um número só: entrevistas exclusivas. Uma entrevista que passou em mais do que um canal conta uma vez, fica atribuída a um deles, e o site escreve ao lado que passou também no outro. Não conta tempo: desde 2026-09-10 conta só a existência de cada entrevista. Mostra a repartição pelos nove canais generalistas e de informação, a evolução por semana, mês e ano, um calendário dia a dia e a lista completa de fontes. A mascote reage ao número de dias desde a última entrevista.

## Como funciona

- `config/entrevistas.yml` é o registo do canal: uma linha por transmissão, com data, canal, programa e URL de prova. É a fonte principal. Uma transmissão é o facto de a entrevista ter passado naquele canal; a unidade que o site conta é a entrevista.
- `config/clipping.yml` são as entrevistas provadas por peças de imprensa: a peça nomeia o canal, diz entrevista e fixa o dia, relatando a entrevista ou anunciando-a. Provam que a entrevista existiu e quando, que é tudo o que se conta, e valem o mesmo que a página do canal. Entram identificadas como tal e nunca deslocam um registo do canal.
- `config/fontes.yml` declara as fontes automáticas. A principal é a pesquisa do próprio site de cada canal: pede a pesquisa do canal por cada forma do nome, recolhe os endereços de artigo desse domínio e lê de cada página o que ela publica em schema.org e OpenGraph. Não há seletores de HTML de nenhum site, e por isso a leitura sobrevive a uma remodelação em vez de passar a devolver zero em silêncio.
- Uma transmissão vinda de fonte automática não entra na primeira vez que é vista: só entra depois de o mesmo bloco aparecer em rondas distintas. O registo de avistamentos está em `docs/dados/candidatos.json`, e ao lado de cada linha ficam as rondas e o número de fontes distintas que a viram. Ver a Metodologia para o que isto protege e o que não protege.
- `recolha/` aplica o critério em `config/porquinho.yml`, dobra as transmissões em entrevistas (`recolha/entrevistas.py`) e escreve `docs/dados/entrevistas.json` (uma entrada por entrevista, com as transmissões dentro; append-only ao nível da transmissão), `docs/dados/quarentena.json` (tudo o que ficou de fora, com motivo) e `docs/dados/resumo.json` (os agregados).
- `docs/` é o site. Sem CDN e sem fontes remotas. A fonte tipográfica é servida localmente, licença OFL ao lado.
- Uma GitHub Action corre a recolha todos os dias e publica as alterações.

A [Metodologia](METODOLOGIA.md) diz o que conta, o que não conta e onde o método falha.

## Correr localmente

```bash
pip install -r requirements.txt
python -m unittest discover -s tests -t .      # 68 testes, offline
node --test tests/frontend/*.test.js           # 13 testes a logica do site, sem browser
python -m recolha.principal --dry-run          # nao escreve nada
python -m recolha.principal                    # escreve docs/dados
python -m recolha.principal --paginas 15       # mais fundo no tempo (historico)
python -m ferramentas.gerar_seo                # metadados, sitemap e o conteudo servido sem JavaScript
python -m http.server -d docs 8000
```

O site constrói as páginas com JavaScript a partir de `docs/dados`, e os agentes de recolha dos modelos de linguagem não executam JavaScript. Por isso `ferramentas/gerar_seo.py` escreve dentro do HTML, entre marcadores, o mesmo que o JavaScript escreveria: o total, a repartição por canal e a lista completa das provas. Corre sozinho no workflow `recolha`; à mão, correr sempre depois de mexer em `config/seo.yml`, e a seguir também `python -m ferramentas.gerar_metodologia`.

Antes de ativar uma fonte nova, `python -m ferramentas.descobrir <url>` mostra o que a página anuncia e o que o feed contém.

`python -m ferramentas.levantamento` (ou o workflow `levantamento`, a pedido) sonda as páginas dos nove canais declaradas em `config/levantamento.yml`, resolve os canais de YouTube e conta no arquivo.pt o que existe por domínio e por ano. Escreve `levantamento/`, que não faz parte do site. É o passo antes de qualquer adaptador novo.

## Contribuir com uma entrevista

**Para acrescentar entrevistas, o caminho normal é o formulário:** Actions, `adicionar`, "Run workflow". Cada entrada é o dia, o canal e a ligação, por qualquer ordem (o canal aceita o id, o nome ou um dos `sinonimos` de `config/porquinho.yml`, como RTPN); várias entradas separam-se por `;`, porque a caixa é de uma linha e o browser apaga as mudanças de linha de um texto colado. O workflow corre `python -m ferramentas.adicionar`, que recusa uma prova repetida, vetada ou já publicada (também quando a ligação vem do telemóvel com parâmetros), avisa se o dia não bate com a hora da publicação ou se o canal já tem uma entrevista a um dia de distância, e escreve as linhas em `config/curadoria.yml` sem tocar no resto do ficheiro. **Tudo ou nada:** se uma entrada falha, nenhuma é escrita. A data é sempre a escrita por quem leu: a hora da publicação serve só para avisar.

**Para retirar provas, o formulário `remover`:** uma ou várias ligações e um motivo, que fica publicado na quarentena da página de Fontes. Cada ligação entra na lista `remover` da curadoria; desfazer é apagar a linha do veto. Uma ligação que não está no site trava o lote inteiro. Retira-se uma prova e não uma entrevista: uma entrevista que passou em dois canais continua contada pela outra prova, e o resumo da corrida diz qual.

Os dois formulários correm os testes, publicam só a curadoria (`--fonte curadoria`, sem rede) e regeneram o HTML. A `--fonte` substitui apenas a quarentena dessa fonte; as outras ficam como a última recolha completa as deixou.

Para acrescentar ou retirar uma entrevista à mão, usar `config/curadoria.yml`: a lista `entrevistas` precisa apenas de `data`, `canal` e `prova` (mais `origem: imprensa` se a prova for uma notícia), e a lista `remover` leva a `prova` e o `motivo`. Uma linha removida passa a aparecer na quarentena com o motivo, em vez de desaparecer.

Quando a mesma entrevista passou em dois canais, as duas linhas ficam como estão e junta-se uma entrada à lista `mesma_entrevista` do mesmo ficheiro, com a `chave` do grupo, o `canal` a que a entrevista fica atribuída, o `motivo` e as `provas`. O canal escreve-se sempre: não há regra que o deduza, e deduzi-lo do domínio já custou oito linhas erradas em oito.

Para uma linha do registo principal, acrescentar a `config/entrevistas.yml` com os campos obrigatórios (`data`, `canal`, `prova`). Não há campo de duração: uma linha que traga `duracao_s` ou `parcial` é recusada pelo coletor. Se a prova for uma peça de imprensa e não o canal, a linha vai para `config/clipping.yml`. Sem URL de prova a linha é rejeitada pela suite de testes.

## Licenças

A fonte Fredoka em `docs/tipos` está sob a SIL Open Font License, incluída ao lado do ficheiro. A licença do código e dos dados está em `LICENSE`.
