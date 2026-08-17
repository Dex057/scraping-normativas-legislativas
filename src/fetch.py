"""Busca e limpeza de páginas.

Responsabilidade única deste módulo: dado um `Fonte`, devolver texto limpo
(sem <script>/<style>/nav/footer) pronto para ser enviado ao modelo de
extração. Não faz nenhuma interpretação de conteúdo — isso é trabalho do
`extract.py`.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urljoin

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
