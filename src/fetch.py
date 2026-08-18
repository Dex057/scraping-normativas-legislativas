"""Busca e limpeza de páginas.

Responsabilidade única deste módulo: dado um `Fonte`, devolver texto limpo
(sem <script>/<style>/nav/footer) pronto para ser enviado ao modelo de
extração. Não faz nenhuma interpretação de conteúdo — isso é trabalho do
`extract.py`.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

logger = logging.getLogger(__name__)

USER_AGENT = (
    "Mozilla/5.0 (compatible; AYIO-NormativasBot/1.0; +https://github.com/) "
    "coleta quinzenal de atos normativos para curadoria interna"
)

# Cabeçalhos adicionais para parecer mais próximo de um navegador real — vários
# sites de tribunais/associações (ex.: TJMG, TJES, Anoreg-BA) devolvem 403 a
# requisições sem esses headers, provavelmente por WAF/CDN filtrando tráfego
# de datacenter (o range de IP dos runners do GitHub Actions é conhecido).
# Isso não resolve todo bloqueio de WAF, mas reduz falsos positivos.
EXTRA_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
}

# Tamanho máximo de texto (em caracteres) enviado ao modelo por página.
# Evita páginas gigantes (ex.: bases de legislação completas) estourarem
# custo/tempo de extração. ~40k chars ~ 10k tokens, ainda barato no Haiku.
MAX_CHARS = 40_000

# Janela retroativa padrão para os modos api_json: quanto tempo olhar para trás
# a cada ciclo. O agendamento é quinzenal (dias 1 e 16 do mês — ver scrape.yml),
# 20 dias dá margem sem custo relevante (dedup por hash cuida do resto).
DEFAULT_DIAS_RETROATIVOS = 20


@dataclass
class ConteudoPagina:
    url: str
    texto: str
    truncado: bool


def _limpar_html(html: str, base_url: str) -> str:
    soup = BeautifulSoup(html, "lxml")

    for tag in soup(["script", "style", "noscript", "svg", "iframe"]):
        tag.decompose()

    # Remove blocos tipicamente irrelevantes para o conteúdo do achado.
    for seletor in ["nav", "footer", "header", "[role='navigation']", "[role='banner']"]:
        for el in soup.select(seletor):
            el.decompose()

    # get_text() descarta atributos — sem isso o href de cada link se perde,
    # e o link é um campo obrigatório do achado. Anota cada link inline antes
    # de extrair o texto puro, para o modelo de extração conseguir casar
    # título ↔ URL.
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if not href or href.startswith(("javascript:", "mailto:", "#")):
            continue
        url_absoluta = urljoin(base_url, href)
        a.append(f" [[LINK: {url_absoluta}]]")

    texto = soup.get_text(separator="\n", strip=True)
    # Colapsa linhas em branco repetidas.
    linhas = [l for l in (linha.strip() for linha in texto.splitlines()) if l]
    return "\n".join(linhas)


@retry(
    reraise=True,
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=20),
    retry=retry_if_exception_type((httpx.TransportError, httpx.HTTPStatusError)),
)
def _buscar_estatico(url: str, timeout: float = 30.0) -> str:
    headers = {"User-Agent": USER_AGENT, **EXTRA_HEADERS}
    with httpx.Client(headers=headers, timeout=timeout, follow_redirects=True, http2=True) as client:
        resp = client.get(url)
        resp.raise_for_status()
        return resp.text


def buscar_pagina(url: str, modo: str = "estatico") -> Optional[ConteudoPagina]:
    """Busca uma página e retorna texto limpo. Retorna None em falha (após retries)."""
    if modo == "js":
        return _buscar_pagina_js(url)
    if modo == "api_json":
        # Aqui `url` é o endpoint da API (fonte["endpoint"]), não a página HTML.
        return _buscar_api_wp(url)

    try:
        html = _buscar_estatico(url)
    except Exception as exc:  # noqa: BLE001 — queremos capturar e logar qualquer falha de rede
        logger.warning("Falha ao buscar %s: %s", url, exc)
        raise

    texto = _limpar_html(html, base_url=url)
    truncado = len(texto) > MAX_CHARS
    if truncado:
        texto = texto[:MAX_CHARS]

    return ConteudoPagina(url=url, texto=texto, truncado=truncado)


def _strip_tags(html: Optional[str]) -> str:
    """Remove tags HTML de um fragmento curto (ementa, excerpt) — não é
    limpeza de página inteira, por isso não reaproveita _limpar_html."""
    if not html:
        return ""
    texto = BeautifulSoup(html, "lxml").get_text(separator=" ", strip=True)
    return " ".join(texto.split())


def _cutoff_iso(dias_retroativos: int) -> str:
    cutoff = datetime.now(timezone.utc) - timedelta(days=dias_retroativos)
    return cutoff.strftime("%Y-%m-%dT%H:%M:%S")


@retry(
    reraise=True,
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=20),
    retry=retry_if_exception_type((httpx.TransportError, httpx.HTTPStatusError)),
)
def _get_json(url: str, params: dict, timeout: float = 30.0) -> object:
    headers = {"User-Agent": USER_AGENT, **EXTRA_HEADERS, "Accept": "application/json"}
    with httpx.Client(headers=headers, timeout=timeout, follow_redirects=True, http2=True) as client:
        resp = client.get(url, params=params)
        resp.raise_for_status()
        content_type = resp.headers.get("content-type", "")
        if "json" not in content_type:
            # Vários TJs respondem 200 em /wp-json/ (rota de descoberta) mas
            # servem HTML normal (fallback de tema) na rota de dados real —
            # tratar como falha para não mandar HTML de erro pro parser JSON.
            raise httpx.HTTPStatusError(
                f"Resposta não-JSON de {url} (content-type={content_type!r})",
                request=resp.request,
                response=resp,
            )
        return resp.json()


def _buscar_api_wp(endpoint: str, dias_retroativos: int = DEFAULT_DIAS_RETROATIVOS) -> Optional[ConteudoPagina]:
    """Busca uma coleção WordPress REST (wp/v2/posts ou um Custom Post Type
    como wp/v2/legislacao) e sintetiza um texto no mesmo formato que
    _limpar_html produz (com [[LINK: ...]] após cada item), para reaproveitar
    extract.py sem alterações — o modelo ainda decide relevância, só que a
    partir de JSON estruturado em vez de HTML cru.
    """
    params = {
        "per_page": 50,
        "orderby": "date",
        "order": "desc",
        "after": _cutoff_iso(dias_retroativos),
        "_fields": "id,date,link,title,excerpt",
    }
    try:
        itens = _get_json(endpoint, params)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Falha ao buscar API WP %s: %s", endpoint, exc)
        raise

    if not isinstance(itens, list):
        raise ValueError(f"Resposta inesperada da API WP {endpoint}: esperava lista, veio {type(itens)}")

    blocos = []
    for item in itens:
        titulo = _strip_tags((item.get("title") or {}).get("rendered"))
        resumo = _strip_tags((item.get("excerpt") or {}).get("rendered"))
        data = (item.get("date") or "")[:10]
        link = item.get("link") or ""
        if not titulo or not link:
            continue
        bloco = f"Título: {titulo}\nData: {data}\nResumo: {resumo} [[LINK: {link}]]"
        blocos.append(bloco)

    texto = "\n---\n".join(blocos)
    truncado = len(texto) > MAX_CHARS
    if truncado:
        texto = texto[:MAX_CHARS]
    return ConteudoPagina(url=endpoint, texto=texto, truncado=truncado)


def buscar_atos_cnj(endpoint: str, dias_retroativos: int = DEFAULT_DIAS_RETROATIVOS) -> list[dict]:
    """Busca atos recentes na API interna do CNJ (atos.cnj.jus.br/api/atos).

    Não documentada publicamente — é o backend da SPA de busca de atos
    normativos, não o DataJud (que é a API pública oficial, mas cobre
    movimentação processual, não atos administrativos). Pagina enquanto os
    itens ainda estiverem dentro da janela retroativa; a listagem já vem
    ordenada por data_publicacao decrescente, então basta parar no primeiro
    item mais antigo que o corte.

    Retorna dicts crus (id, tipo, numero, data_publicacao, situacao, ementa
    já sem HTML, link) — quem decide como virar Achado é o extract.py.
    """
    cutoff = _cutoff_iso(dias_retroativos)[:10]
    base = f"{urlparse(endpoint).scheme}://{urlparse(endpoint).netloc}"

    atos: list[dict] = []
    pagina = 1
    max_paginas = 15  # trava de segurança (~150 itens) — não é pra varrer o histórico inteiro
    while pagina <= max_paginas:
        try:
            corpo = _get_json(endpoint, {"page": pagina})
        except Exception as exc:  # noqa: BLE001
            logger.warning("Falha ao buscar API do CNJ (página %d): %s", pagina, exc)
            raise

        dados = corpo.get("data") if isinstance(corpo, dict) else None
        if not dados:
            break

        parou = False
        for item in dados:
            data_pub = item.get("data_publicacao") or ""
            if data_pub and data_pub < cutoff:
                parou = True
                break
            atos.append(
                {
                    "id": item.get("id"),
                    "tipo": item.get("tipo"),
                    "numero": item.get("numero"),
                    "data_publicacao": data_pub or None,
                    "situacao": item.get("situacao"),
                    "ementa": _strip_tags(item.get("ementa")),
                    "link": f"{base}/atos/detalhar/{item.get('id')}",
                }
            )
        if parou or corpo.get("current_page", pagina) >= corpo.get("last_page", pagina):
            break
        pagina += 1

    return atos


def _buscar_pagina_js(url: str) -> Optional[ConteudoPagina]:
    """Fallback para páginas que dependem de JavaScript (Playwright).

    Só importa playwright quando necessário — mantém a dependência opcional
    para quem não tem nenhuma fonte marcada como modo=js.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "Fonte configurada com modo=js requer 'playwright' instalado "
            "(pip install playwright && playwright install chromium)."
        ) from exc

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(user_agent=USER_AGENT)
        page.goto(url, wait_until="networkidle", timeout=30_000)
        html = page.content()
        browser.close()

    texto = _limpar_html(html, base_url=url)
    truncado = len(texto) > MAX_CHARS
    if truncado:
        texto = texto[:MAX_CHARS]
    return ConteudoPagina(url=url, texto=texto, truncado=truncado)
