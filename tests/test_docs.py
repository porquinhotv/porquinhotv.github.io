"""O que o publico le tem de ser o que o projeto faz.

- a Metodologia HTML corresponde ao Markdown;
- os textos satiricos no site correspondem ao YAML;
- sem travessoes nos textos versionados;
- o rodape completo em todas as paginas, e o sujeito escrito por extenso;
- o site nao pede nada a terceiros;
- nenhum nome de canal ou pessoa no codigo Python;
- sem metadados de editor nos SVG;
- a palavra "emissao" nao sobrevive em nada que o publico leia.
"""

import re
import unittest

import yaml

from tests.apoio import RAIZ

from ferramentas import gerar_metodologia, gerar_textos

TRAVESSOES = ("\u2014", "\u2013")
TEXTO_VERSIONADO = [RAIZ / "METODOLOGIA.md", RAIZ / "README.md"]
TEXTO_VERSIONADO += sorted((RAIZ / "config").glob("*.yml"))
TEXTO_VERSIONADO += sorted((RAIZ / "docs").glob("*.html")) + sorted((RAIZ / "docs").glob("*.js")) + sorted((RAIZ / "docs").glob("*.css"))
# Enderecos permitidos no que o browser vai buscar sozinho. O endereco
# do proprio site entra aqui porque o canonical e o cartao de partilha o
# escrevem por extenso, e um endereco proprio nao e um terceiro; vem do
# `config/seo.yml` para que mudar de sitio nao exija mexer no teste.
SEO = yaml.safe_load((RAIZ / "config" / "seo.yml").read_text(encoding="utf-8"))
URL_PERMITIDO = re.compile(
    r"https?://(www\.)?w3\.org/"                # espaco de nomes do SVG, nao e um pedido
    r"|^https://cloud\.umami\.is/script\.js$"    # estatisticas de visitas, ver o teste abaixo
    r"|^" + re.escape(SEO["base"])                # o proprio site
)

# O que se retira antes de procurar pedidos, e porque nao e um pedido:
# uma ligacao que o utilizador carrega, e as declaracoes dos dados
# estruturados. A pagina de Fontes existe precisamente para trazer as
# ligacoes das provas, que sao de dezenas de dominios; se o teste as
# lesse como pedidos, a unica forma de passar era esconde-las de quem le
# a pagina sem JavaScript.
NAO_SAO_PEDIDOS = re.compile(r"<a\b[^>]*>|<script type=\"application/ld\+json\">.*?</script>", re.DOTALL)
NOMES_PROIBIDOS_NO_CODIGO = re.compile(r"\b(ventura|chega|rtp\d?|sic|tvi|cnn|cmtv|milhazes|rogeiro)\b", re.IGNORECASE)


class TestArtefactosGerados(unittest.TestCase):
    def test_metodologia_html_em_dia(self):
        self.assertEqual(gerar_metodologia.ALVO.read_text(encoding="utf-8"), gerar_metodologia.construir(),
                         "correr: python -m ferramentas.gerar_metodologia")

    def test_textos_json_em_dia(self):
        self.assertEqual(gerar_textos.ALVO.read_text(encoding="utf-8"), gerar_textos.construir(),
                         "correr: python -m ferramentas.gerar_textos")

    def test_a_metodologia_tem_o_contacto_clicavel(self):
        """O conversor so trata o Markdown que o documento usa, por isso uma
        ligacao nova sai como texto com parenteses a vista. A seccao de
        correcoes precisa de um endereco que uma pessoa carregue, e no
        telemovel escrever um email a mao e o mesmo que nao haver contacto."""
        gerado = gerar_metodologia.construir()
        self.assertIn('<a href="mailto:', gerado)
        self.assertNotIn("](mailto:", gerado)

    def test_validacao_dos_textos_apanha_erros(self):
        mau = {"humores": [{"id": "a", "ate_dias": 3, "frases": ["{x}"]}, {"id": "b", "ate_dias": None, "frases": []}]}
        with self.assertRaises(ValueError):
            gerar_textos.validar(mau)
        desordem = {"humores": [{"id": "a", "ate_dias": 3, "frases": []}, {"id": "b", "ate_dias": 2, "frases": []}, {"id": "c", "ate_dias": None, "frases": []}]}
        with self.assertRaises(ValueError):
            gerar_textos.validar(desordem)

    def test_validacao_das_metricas_apanha_erros(self):
        """A camada satirica das metricas e escrita a mao no YAML. Um
        placeholder que o site nao preenche chega ao ecra com as chavetas a
        vista, e uma escada com limites fora de ordem deixa um numero sem
        frase nenhuma. As duas coisas tem de parar aqui."""
        base = {"humores": [{"id": "a", "ate_dias": None, "frases": []}]}
        with self.assertRaises(ValueError):
            gerar_textos.validar(dict(base, metricas={"total": [{"ate": None, "frases": ["{canal}"]}]}))
        with self.assertRaises(ValueError):
            gerar_textos.validar(dict(base, metricas={"total": [{"ate": 3, "frases": []}, {"ate": 1, "frases": []}, {"ate": None, "frases": []}]}))
        with self.assertRaises(ValueError):
            gerar_textos.validar(dict(base, metricas={"total": [{"ate": 3, "frases": []}]}))
        with self.assertRaises(ValueError):
            gerar_textos.validar(dict(base, metricas={"lider": "{periodo}"}))
        with self.assertRaises(ValueError):
            gerar_textos.validar(dict(base, metricas={"legendas": {"canais": "{n} canais"}}))
        gerar_textos.validar(base)  # sem metricas continua valido

    def test_validacao_do_ordinal_da_temporada_apanha_erros(self):
        """A frase da serie dizia "ja ia na terceira temporada" com um
        ordinal escrito a mao, e so era verdade entre as 21 e as 36
        entrevistas; com as 59 publicadas a 2026-09-12 estava errada, e o
        separador "Este ano" mostrava-a a partir das 11. O ordinal passou a
        sair da contagem, e estas sao as maneiras de partir esse calculo."""
        base = {"humores": [{"id": "a", "ate_dias": None, "frases": []}]}
        bom = {"episodios": 12, "ordinais": {2: "segunda"}}
        with self.assertRaises(ValueError):  # frase pede o ordinal, falta o bloco
            gerar_textos.validar(dict(base, metricas={"total": [{"ate": None, "frases": ["{temporada}"]}]}))
        with self.assertRaises(ValueError):  # sem episodios nao ha divisao
            gerar_textos.validar(dict(base, metricas={"temporada": {"episodios": 0, "ordinais": {2: "segunda"}}}))
        with self.assertRaises(ValueError):  # lista vazia nunca daria ordinal
            gerar_textos.validar(dict(base, metricas={"temporada": {"episodios": 12, "ordinais": {}}}))
        with self.assertRaises(ValueError):  # chave que nao e numero de temporada
            gerar_textos.validar(dict(base, metricas={"temporada": {"episodios": 12, "ordinais": {"duas": "segunda"}}}))
        with self.assertRaises(ValueError):  # ordinal por escrever
            gerar_textos.validar(dict(base, metricas={"temporada": {"episodios": 12, "ordinais": {2: " "}}}))
        gerar_textos.validar(dict(base, metricas={"temporada": bom}))
        gerar_textos.validar(dict(base, metricas={"total": [{"ate": None, "frases": ["{temporada}"]}], "temporada": bom}))

    def test_o_json_publicado_leva_os_ordinais_com_chave_de_texto(self):
        """No YAML as chaves sao numeros e em JSON sao texto. Se a conversao
        ficasse do lado do site, uma leitura por numero devolvia indefinido
        e a frase da serie desaparecia em silencio."""
        metricas = gerar_textos.normalizar_temporada({"temporada": {"episodios": 12, "ordinais": {5: "quinta"}}})
        self.assertEqual(metricas["temporada"]["ordinais"], {"5": "quinta"})

    def test_nenhuma_frase_do_humor_fica_por_mostrar(self):
        """A frase e escolhida por `valor % numero_de_frases`, por isso um
        degrau fechado com menos valores possiveis do que frases deixa
        frases que nunca aparecem no site. Eram tres a 2026-09-12, uma
        delas no degrau de dois dias, e ninguem daria por isso a ler o
        YAML."""
        humor = yaml.safe_load((RAIZ / "config" / "humor.yml").read_text(encoding="utf-8"))
        escadas = [("humores", humor["humores"], "ate_dias"),
                   ("metricas.total", humor["metricas"]["total"], "ate")]
        for onde, degraus, campo in escadas:
            inferior = 0
            for degrau in degraus:
                limite = degrau[campo]
                if limite is None:
                    break  # o degrau aberto tem valores que cheguem para qualquer lista
                frases = degrau["frases"]
                alcancados = {v % len(frases) for v in range(inferior, limite + 1)}
                with self.subTest(escada=onde, ate=limite):
                    self.assertEqual(len(alcancados), len(frases),
                                     f"{onde} ate {limite}: {len(frases)} frases para {limite - inferior + 1} valores")
                inferior = limite + 1

    def test_o_site_nao_le_campos_de_tempo(self):
        """A duracao saiu a 2026-09-10 e o resumo deixou de ter `tempo_s` e
        `sem_duracao`. Um JavaScript que ainda os lesse somava `undefined` e
        escrevia NaN no site sem nenhum teste dar por isso."""
        alvos = sorted((RAIZ / "docs").glob("*.js")) + sorted((RAIZ / "docs").glob("*.css")) + [RAIZ / "docs" / "textos.json"]
        alvos += [c for c in sorted((RAIZ / "docs").glob("*.html")) if c.name != "metodologia.html"]
        for caminho in alvos:
            texto = caminho.read_text(encoding="utf-8")
            with self.subTest(ficheiro=caminho.name):
                for marca in ("tempo_s", "sem_duracao", "duracao_s", "duracaoLegivel", "parciais", "comparacoes", "unidade_s"):
                    self.assertFalse(marca in texto, f"{caminho.name} ainda usa {marca!r}")

    def test_nada_do_que_o_publico_le_conta_emissoes(self):
        """A unidade passou a ser a entrevista exclusiva a 2026-09-11, e o
        conceito de emissao saiu do projeto. Uma suposicao que cai tem de
        cair em todas as suas copias: uma pagina que ainda dissesse
        "emissoes" apresentava ao leitor duas unidades para a mesma coisa,
        que e exactamente o que esta mudanca foi feita para acabar.

        Fora deste teste ficam o METODOLOGIA.md e a sua copia em HTML, que
        tem de poder dizer por palavras o que mudou e quando: um documento
        que explica uma correcao precisa de nomear o que corrigiu."""
        alvos = sorted((RAIZ / "docs").glob("*.js")) + sorted((RAIZ / "docs").glob("*.css"))
        alvos += [RAIZ / "docs" / "textos.json"]
        alvos += [c for c in sorted((RAIZ / "docs").glob("*.html")) if c.name != "metodologia.html"]
        alvos += sorted((RAIZ / "docs" / "dados").glob("*.json"))
        alvos += sorted((RAIZ / "config").glob("*.yml"))
        for caminho in alvos:
            if not caminho.exists():
                continue
            texto = caminho.read_text(encoding="utf-8").lower()
            with self.subTest(ficheiro=caminho.name):
                for marca in ("emissão", "emissões", "emissao", "emissoes", "entrevistas_distintas"):
                    self.assertNotIn(marca, texto, f"{caminho.name} ainda fala de {marca!r}")

    def test_o_site_nao_le_a_lista_de_dados_antiga(self):
        """`docs/dados/emissoes.json` deixou de existir a 2026-09-11. Uma
        pagina que ainda o pedisse falhava com um 404 silencioso e
        mostrava o painel de erro em vez dos dados."""
        for caminho in sorted((RAIZ / "docs").glob("*.html")) + sorted((RAIZ / "docs").glob("*.js")):
            with self.subTest(ficheiro=caminho.name):
                self.assertNotIn("emissoes.json", caminho.read_text(encoding="utf-8"), caminho.name)

    def test_o_repor_apaga_o_ficheiro_de_dados_que_existe(self):
        """O `repor` do workflow de historico apaga `docs/dados` antes de
        reconstruir. O ficheiro publicado mudou de nome a 2026-09-11: a
        apagar o antigo, a caixa `repor` deixava de ter efeito nenhum e
        nao dava erro, e a corrida seguinte somava duas geracoes de
        regras sobre o dataset velho."""
        workflow = (RAIZ / ".github" / "workflows" / "historico.yml").read_text(encoding="utf-8")
        self.assertIn("rm -f docs/dados/entrevistas.json", workflow)
        self.assertNotIn("emissoes.json", workflow)

    def test_nenhum_documento_versionado_promete_tempo(self):
        """Uma suposicao que cai tem de cair em todas as suas copias. As
        frases que o site e a Metodologia usavam para prometer tempo nao
        podem sobreviver em documento nenhum, e os campos de configuracao
        que a duracao exigia nao podem voltar a ser declarados."""
        marcas = ("quanto tempo ocuparam", "duração não apurada", "duracao_opcional:", "assumir_parcial:", "tempo no ar", "sem duração apurada")
        for caminho in TEXTO_VERSIONADO + sorted((RAIZ / "recolha").rglob("*.py")):
            texto = caminho.read_text(encoding="utf-8")
            with self.subTest(ficheiro=caminho.name):
                for marca in marcas:
                    self.assertFalse(marca in texto, f"{caminho.name} ainda diz {marca!r}")


class TestConvencoes(unittest.TestCase):
    def test_sem_travessoes(self):
        for caminho in TEXTO_VERSIONADO:
            with self.subTest(ficheiro=caminho.name):
                for n, linha in enumerate(caminho.read_text(encoding="utf-8").splitlines(), 1):
                    for t in TRAVESSOES:
                        self.assertNotIn(t, linha, f"{caminho.name}:{n}")

    def test_todas_as_paginas_tem_a_marca_e_o_menu(self):
        """A Metodologia era a unica pagina sem a marca nem o menu: tinha um
        link "voltar" e mais nada. Quem chegava la por uma pesquisa nao via
        de que site se tratava nem tinha como ir as outras paginas. O topo
        da Metodologia e gerado por ferramentas/gerar_metodologia.py, por
        isso este teste le o ficheiro publicado como os outros."""
        for caminho in sorted((RAIZ / "docs").glob("*.html")):
            texto = caminho.read_text(encoding="utf-8")
            with self.subTest(ficheiro=caminho.name):
                self.assertIn('class="marca"', texto, f"{caminho.name} nao tem a marca")
                for pagina in ("index.html", "calendario.html", "fontes.html"):
                    self.assertIn(f'<a href="{pagina}"', texto, f"{caminho.name} nao liga a {pagina}")

    def test_o_rodape_completo_esta_em_todas_as_paginas(self):
        """O Calendario e as Fontes tinham um rodape reduzido a dois links,
        sem contacto e sem a explicacao do que o site conta. Quem chega a
        uma dessas paginas por um motor de busca nao tinha, dali, forma de
        reportar uma linha errada. O rodape e o mesmo nas tres."""
        for nome in ("index.html", "calendario.html", "fontes.html"):
            caminho = RAIZ / "docs" / nome
            texto = caminho.read_text(encoding="utf-8")
            with self.subTest(ficheiro=nome):
                self.assertIn("mailto:", texto, f"{nome} nao tem contacto no rodape")
                self.assertIn('href="metodologia.html"', texto, f"{nome} nao liga a Metodologia")
                self.assertIn('id="gerado"', texto, f"{nome} nao diz a data da ultima recolha")

    def test_nenhuma_pagina_oferece_um_descarregamento_dos_dados(self):
        """Decisao do autor a 2026-09-15: a ligacao "Descarregar os dados"
        saiu do rodape das tres paginas, porque a de Fontes ja mostra
        todas as linhas com a prova de cada uma e nao ha nada a acrescentar.
        A Metodologia afirmava que os dados podiam ser descarregados dali:
        uma afirmacao removida do HTML e mantida no documento publicado
        continua a ser uma afirmacao falsa. O teste guarda os dois lados,
        porque foi por eles se corrigirem em sitios diferentes que ja
        falhou antes. Nao proibe o `DataDownload` dos dados estruturados
        nem o `<link rel="alternate">`: esses nao sao ligacoes oferecidas
        a quem le, e o que saiu foi a ligacao visivel."""
        ancora_com_download = re.compile(r"<a\b[^>]*\bdownload\b")
        for caminho in sorted((RAIZ / "docs").glob("*.html")):
            texto = caminho.read_text(encoding="utf-8")
            with self.subTest(ficheiro=caminho.name):
                self.assertIsNone(ancora_com_download.search(texto), f"{caminho.name} volta a oferecer o ficheiro")
        for caminho in (RAIZ / "METODOLOGIA.md", RAIZ / "docs" / "metodologia.html"):
            texto = caminho.read_text(encoding="utf-8")
            with self.subTest(ficheiro=caminho.name):
                self.assertNotIn("descarregad", texto, f"{caminho.name} promete um descarregamento que o site nao tem")

    def test_as_frases_do_site_nao_tratam_o_sujeito_por_pronome(self):
        """Decisao do autor a 2026-09-11: as frases falam sempre do
        porquinho e nunca dizem "ele". Um pronome solto deixa de ser satira
        sobre a mascote e passa a apontar a uma pessoa, que e exatamente o
        que este site nao faz. A legenda dos canais dizia "onde e que ele
        apareceu mais vezes"."""
        texto = (RAIZ / "docs" / "textos.json").read_text(encoding="utf-8")
        for n, linha in enumerate(texto.splitlines(), 1):
            with self.subTest(linha=n):
                self.assertIsNone(re.search(r"\b[Ee]le\b", linha), f"textos.json:{n}")

    def test_o_site_nao_pede_nada_a_terceiros(self):
        """Um pedido e o que o browser vai buscar sozinho: um script, uma
        folha de estilo, um tipo de letra, uma imagem. A lista de
        permitidos tem tres entradas e mais nenhuma: o espaco de nomes do
        SVG, que nao chega a ser um pedido, o script de estatisticas de
        visitas, fixado ate ao caminho, e o endereco do proprio site.
        Ficam de fora da varredura as ligacoes `<a>` e os dados
        estruturados, que sao declaracoes e nao pedidos, e sem os quais a
        pagina de Fontes nao poderia mostrar as provas sem JavaScript.
        Sem este teste voltam CDN, tipos de letra remotos e tudo o resto
        que este site nao serve a partir de terceiros."""
        for caminho in sorted((RAIZ / "docs").glob("*.html")) + sorted((RAIZ / "docs").glob("*.js")) + sorted((RAIZ / "docs").glob("*.css")):
            with self.subTest(ficheiro=caminho.name):
                texto = NAO_SAO_PEDIDOS.sub(" ", caminho.read_text(encoding="utf-8"))
                for url in re.findall(r"https?://[^\s\"'<>)]+", texto):
                    self.assertRegex(url, URL_PERMITIDO, f"pedido externo em {caminho.name}: {url}")

    def test_as_estatisticas_de_visitas_estao_em_todas_as_paginas(self):
        """A metodologia.html e gerada: um snippet colado a mao nela
        desaparecia na geracao seguinte, sem erro e sem se dar por isso, e
        a pagina deixava de ser contada. Tem de vir do gerador, e este
        teste falha se alguma pagina do site ficar de fora."""
        for caminho in sorted((RAIZ / "docs").glob("*.html")):
            with self.subTest(ficheiro=caminho.name):
                self.assertIn("cloud.umami.is/script.js", caminho.read_text(encoding="utf-8"),
                              f"{caminho.name} nao conta as visitas")

    def test_o_contacto_do_site_e_um_mailto_e_nao_um_formulario(self):
        """Um formulario que envia precisa de um receptor, e o receptor e
        sempre um terceiro com conta e chave: quebra as duas propriedades
        que este projeto nao negoceia. O contacto e um endereco em
        `mailto:`, que nao e um pedido e nao exige conta a ninguem."""
        for caminho in sorted((RAIZ / "docs").glob("*.html")):
            texto = caminho.read_text(encoding="utf-8").lower()
            with self.subTest(ficheiro=caminho.name):
                self.assertNotIn("<form", texto, f"{caminho.name} tem um formulario")

    def test_sem_google_no_site(self):
        for caminho in sorted((RAIZ / "docs").glob("*.html")) + sorted((RAIZ / "docs").glob("*.css")):
            self.assertNotIn("google", caminho.read_text(encoding="utf-8").lower(), caminho.name)

    def test_nenhum_nome_no_codigo_python(self):
        for caminho in sorted((RAIZ / "recolha").rglob("*.py")) + sorted((RAIZ / "ferramentas").glob("*.py")):
            with self.subTest(ficheiro=caminho.name):
                texto = caminho.read_text(encoding="utf-8")
                self.assertIsNone(NOMES_PROIBIDOS_NO_CODIGO.search(texto), f"nome editorial em {caminho}")

    def test_svg_sem_metadados_de_editor(self):
        for caminho in sorted((RAIZ / "docs").glob("*.svg")):
            texto = caminho.read_text(encoding="utf-8").lower()
            for marca in ("inkscape", "sodipodi", "illustrator", "adobe", "sketch", "figma"):
                self.assertNotIn(marca, texto, f"{caminho.name} tem metadados de {marca}")

    def test_nenhum_documento_afirma_uma_duracao_minima(self):
        """A duracao minima foi removida. Uma suposicao que cai tem de cair
        em todas as suas copias, senao o documento publico continua a
        afirmar uma regra que o codigo ja nao aplica."""
        for caminho in TEXTO_VERSIONADO + sorted((RAIZ / "recolha").rglob("*.py")):
            texto = caminho.read_text(encoding="utf-8")
            with self.subTest(ficheiro=caminho.name):
                self.assertNotIn("duracao_minima", texto, caminho.name)
                self.assertNotIn("duração mínima de", texto, caminho.name)

    def test_ficheiros_em_lf(self):
        """Inclui os ficheiros de dados: gerados em CRLF, o diff do git
        mostraria o ficheiro inteiro alterado a cada corrida e a trilha de
        auditoria deixaria de servir para o que existe."""
        alvos = TEXTO_VERSIONADO + sorted((RAIZ / "recolha").rglob("*.py"))
        alvos += sorted((RAIZ / "docs" / "dados").glob("*.json"))
        alvos += [RAIZ / "docs" / "textos.json"]
        for caminho in alvos:
            if not caminho.exists():
                continue
            with self.subTest(ficheiro=caminho.name):
                self.assertNotIn(b"\r\n", caminho.read_bytes(), f"CRLF em {caminho.name}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
