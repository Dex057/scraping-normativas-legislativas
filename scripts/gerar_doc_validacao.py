"""Gera o documento de validação de fontes (HTML autocontido) para revisão
jurídica, a partir de config/sources.yaml. Uso único / manutenção manual —
não faz parte do pipeline de produção.
"""

from __future__ import annotations

import html
from collections import defaultdict
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
SOURCES_PATH = ROOT / "config" / "sources.yaml"
OUT_PATH = ROOT / "docs" / "validacao_fontes.html"

CATEGORIA_LABEL = {
    "nacional_extrajudicial": "Nacional — Extrajudicial",
    "legislativo": "Legislativo",
    "estadual_anoreg": "Anoreg seccional",
    "estadual_tj": "Tribunal de Justiça",
    "estadual_corregedoria": "Corregedoria Geral de Justiça",
}

UF_NOME = {
    "AC": "Acre", "AL": "Alagoas", "AM": "Amazonas", "AP": "Amapá", "BA": "Bahia",
    "CE": "Ceará", "DF": "Distrito Federal", "ES": "Espírito Santo", "GO": "Goiás",
    "MA": "Maranhão", "MG": "Minas Gerais", "MS": "Mato Grosso do Sul", "MT": "Mato Grosso",
    "PA": "Pará", "PB": "Paraíba", "PE": "Pernambuco", "PI": "Piauí", "PR": "Paraná",
    "RJ": "Rio de Janeiro", "RN": "Rio Grande do Norte", "RO": "Rondônia", "RR": "Roraima",
    "RS": "Rio Grande do Sul", "SC": "Santa Catarina", "SE": "Sergipe", "SP": "São Paulo",
    "TO": "Tocantins",
}


def esc(s: str | None) -> str:
    return html.escape(s) if s else ""


def status_pill(fonte: dict) -> str:
    if fonte.get("url") is None:
        return '<span class="pill pill-critical">Não localizada</span>'
    if fonte.get("ativo"):
        return '<span class="pill pill-success">Confirmada</span>'
    return '<span class="pill pill-warning">Confirmar manualmente</span>'


def fonte_row(fonte: dict) -> str:
    url = fonte.get("url")
    nota = fonte.get("nota")
    label = CATEGORIA_LABEL.get(fonte["categoria"], fonte["categoria"])
    if url:
        link_html = f'<a href="{esc(url)}" target="_blank" rel="noopener">{esc(url)}</a>'
    else:
        link_html = '<span class="sem-url">— sem URL candidata —</span>'
    nota_html = f'<p class="nota">{esc(nota)}</p>' if nota else ""
    return f"""
      <div class="fonte-row">
        <div class="fonte-row-main">
          <span class="fonte-tipo">{esc(label)}</span>
          {status_pill(fonte)}
        </div>
        <div class="fonte-url">{link_html}</div>
        {nota_html}
      </div>"""


def build() -> str:
    with open(SOURCES_PATH, encoding="utf-8") as f:
        fontes = yaml.safe_load(f)["fontes"]

    nacionais = [f for f in fontes if not f.get("estado")]
    estaduais = [f for f in fontes if f.get("estado")]

    por_estado: dict[str, list[dict]] = defaultdict(list)
    for f in estaduais:
        por_estado[f["estado"]].append(f)

    total = len(fontes)
    confirmadas = sum(1 for f in fontes if f.get("ativo"))
    pendentes = sum(1 for f in fontes if not f.get("ativo") and f.get("url"))
    nao_localizadas = sum(1 for f in fontes if f.get("url") is None)

    nacionais_html = "\n".join(
        f'<div class="card card-nacional">'
        f'<h3>{esc(f["nome"])}</h3>'
        f"{fonte_row(f)}"
        f"</div>"
        for f in nacionais
    )

    estados_html_parts = []
    for uf in sorted(por_estado.keys()):
        entradas = sorted(
            por_estado[uf],
            key=lambda f: ["estadual_anoreg", "estadual_tj", "estadual_corregedoria"].index(f["categoria"]),
        )
        linhas = "\n".join(fonte_row(f) for f in entradas)
        n_confirmadas = sum(1 for f in entradas if f.get("ativo"))
        estados_html_parts.append(f"""
      <article class="card card-estado" data-uf="{uf}" data-nome="{esc(UF_NOME.get(uf, uf)).lower()}">
        <header class="card-estado-header">
          <h3>{uf} <span class="uf-nome">— {esc(UF_NOME.get(uf, uf))}</span></h3>
          <span class="uf-contagem">{n_confirmadas}/{len(entradas)} confirmadas</span>
        </header>
        {linhas}
      </article>""")
    estados_html = "\n".join(estados_html_parts)

    return TEMPLATE.format(
        total=total,
        confirmadas=confirmadas,
        pendentes=pendentes,
        nao_localizadas=nao_localizadas,
        nacionais_html=nacionais_html,
        estados_html=estados_html,
    )


TEMPLATE = """<title>Validação de Fontes — Monitoramento de Normativas</title>
<style>
  :root {{
    --bg: #F4F5F8;
    --surface: #FFFFFF;
    --surface-alt: #EBEDF3;
    --ink: #1C2333;
    --ink-muted: #5B6478;
    --border: #DADFE8;
    --accent: #2B3E6B;
    --accent-soft: #E4E9F5;
    --success: #1F7A4D;
    --success-soft: #E3F3EA;
    --warning: #A6650C;
    --warning-soft: #FBF0DC;
    --critical: #B23A3A;
    --critical-soft: #FBE7E7;
    --font-display: Georgia, "Iowan Old Style", "Times New Roman", serif;
    --font-body: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
    --font-mono: ui-monospace, "SF Mono", "Cascadia Code", "Roboto Mono", Consolas, monospace;
  }}
  @media (prefers-color-scheme: dark) {{
    :root:not([data-theme="light"]) {{
      --bg: #10141F;
      --surface: #171D2C;
      --surface-alt: #1F2637;
      --ink: #E7EAF2;
      --ink-muted: #9AA3B8;
      --border: #2B3247;
      --accent: #8CA0DC;
      --accent-soft: #22304F;
      --success: #4FBE84;
      --success-soft: #163726;
      --warning: #E0A73B;
      --warning-soft: #3A2C10;
      --critical: #E27272;
      --critical-soft: #3A1E1E;
    }}
  }}
  :root[data-theme="dark"] {{
    --bg: #10141F;
    --surface: #171D2C;
    --surface-alt: #1F2637;
    --ink: #E7EAF2;
    --ink-muted: #9AA3B8;
    --border: #2B3247;
    --accent: #8CA0DC;
    --accent-soft: #22304F;
    --success: #4FBE84;
    --success-soft: #163726;
    --warning: #E0A73B;
    --warning-soft: #3A2C10;
    --critical: #E27272;
    --critical-soft: #3A1E1E;
  }}

  * {{ box-sizing: border-box; }}
  body {{
    margin: 0;
    background: var(--bg);
    color: var(--ink);
    font-family: var(--font-body);
    line-height: 1.5;
    -webkit-font-smoothing: antialiased;
  }}
  a {{ color: var(--accent); }}

  .wrap {{ max-width: 1100px; margin: 0 auto; padding: 0 24px 96px; }}

  header.masthead {{
    background: linear-gradient(180deg, var(--accent-soft), transparent);
    border-bottom: 1px solid var(--border);
    padding: 56px 24px 32px;
    margin-bottom: 40px;
  }}
  header.masthead .wrap {{ padding: 0; }}
  .eyebrow {{
    font-family: var(--font-mono);
    font-size: 0.78rem;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: var(--accent);
    margin: 0 0 12px;
  }}
  h1 {{
    font-family: var(--font-display);
    font-size: clamp(1.7rem, 3.2vw, 2.4rem);
    font-weight: 400;
    margin: 0 0 14px;
    text-wrap: balance;
    color: var(--ink);
  }}
  .lede {{
    max-width: 68ch;
    color: var(--ink-muted);
    font-size: 1.02rem;
    margin: 0 0 28px;
  }}

  .stat-bar {{
    display: flex;
    flex-wrap: wrap;
    gap: 12px;
  }}
  .stat {{
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 14px 18px;
    min-width: 150px;
  }}
  .stat .n {{
    font-family: var(--font-mono);
    font-variant-numeric: tabular-nums;
    font-size: 1.6rem;
    font-weight: 600;
    line-height: 1;
  }}
  .stat .label {{
    font-size: 0.82rem;
    color: var(--ink-muted);
    margin-top: 4px;
  }}
  .stat.stat-success .n {{ color: var(--success); }}
  .stat.stat-warning .n {{ color: var(--warning); }}
  .stat.stat-critical .n {{ color: var(--critical); }}

  section {{ margin-bottom: 48px; }}
  h2 {{
    font-family: var(--font-display);
    font-weight: 400;
    font-size: 1.35rem;
    border-bottom: 1px solid var(--border);
    padding-bottom: 10px;
    margin: 0 0 20px;
  }}

  .legend {{
    display: flex;
    gap: 18px;
    flex-wrap: wrap;
    font-size: 0.86rem;
    color: var(--ink-muted);
    margin-bottom: 24px;
  }}
  .legend span {{ display: inline-flex; align-items: center; gap: 6px; }}

  #busca {{
    width: 100%;
    max-width: 360px;
    padding: 10px 14px;
    border-radius: 8px;
    border: 1px solid var(--border);
    background: var(--surface);
    color: var(--ink);
    font-family: var(--font-body);
    font-size: 0.95rem;
    margin-bottom: 20px;
  }}
  #busca:focus {{ outline: 2px solid var(--accent); outline-offset: 1px; }}

  .cards-nacionais {{
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
    gap: 14px;
  }}
  .cards-estaduais {{
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
    gap: 16px;
  }}

  .card {{
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 18px 20px;
  }}
  .card h3 {{
    font-family: var(--font-body);
    font-size: 1rem;
    font-weight: 650;
    margin: 0 0 4px;
  }}
  .card-estado-header {{
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    gap: 8px;
    margin-bottom: 10px;
  }}
  .uf-nome {{ font-weight: 400; color: var(--ink-muted); font-size: 0.88em; }}
  .uf-contagem {{
    font-family: var(--font-mono);
    font-variant-numeric: tabular-nums;
    font-size: 0.78rem;
    color: var(--ink-muted);
    white-space: nowrap;
  }}

  .fonte-row {{
    padding: 10px 0;
    border-top: 1px solid var(--border);
  }}
  .fonte-row:first-of-type {{ border-top: none; padding-top: 6px; }}
  .fonte-row-main {{
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 8px;
    margin-bottom: 4px;
  }}
  .fonte-tipo {{ font-size: 0.86rem; color: var(--ink-muted); }}
  .fonte-url {{
    font-family: var(--font-mono);
    font-size: 0.82rem;
    word-break: break-all;
  }}
  .fonte-url a {{ text-decoration: none; }}
  .fonte-url a:hover {{ text-decoration: underline; }}
  .sem-url {{ color: var(--ink-muted); font-style: italic; font-size: 0.86rem; }}
  .nota {{
    font-size: 0.82rem;
    color: var(--ink-muted);
    margin: 6px 0 0;
    padding: 8px 10px;
    background: var(--surface-alt);
    border-radius: 6px;
  }}

  .pill {{
    font-family: var(--font-mono);
    font-size: 0.72rem;
    font-weight: 600;
    letter-spacing: 0.02em;
    padding: 3px 9px;
    border-radius: 999px;
    white-space: nowrap;
  }}
  .pill-success {{ background: var(--success-soft); color: var(--success); }}
  .pill-warning {{ background: var(--warning-soft); color: var(--warning); }}
  .pill-critical {{ background: var(--critical-soft); color: var(--critical); }}

  footer {{
    max-width: 1100px;
    margin: 0 auto;
    padding: 0 24px;
    color: var(--ink-muted);
    font-size: 0.86rem;
  }}
  footer a {{ color: var(--accent); }}

  .card-estado.hidden {{ display: none; }}

  @media (prefers-reduced-motion: no-preference) {{
    .card {{ transition: border-color 0.15s ease; }}
  }}
</style>

<header class="masthead">
  <div class="wrap">
    <p class="eyebrow">Pedido 01 — Corpo Técnico AYIO</p>
    <h1>Validação das fontes de monitoramento de atualizações normativas e legislativas</h1>
    <p class="lede">
      Lista de todos os portais que a automação quinzenal vai varrer em busca de atos
      normativos, provimentos e publicações legislativas — Anoreg seccional, Tribunal de
      Justiça e Corregedoria Geral de Justiça de cada estado, além das fontes nacionais.
      As URLs foram levantadas e testadas automaticamente; pedimos a validação do jurídico
      antes de ativar o ciclo de produção, especialmente nos itens marcados como
      <strong>"Confirmar manualmente"</strong> ou <strong>"Não localizada"</strong>.
    </p>
    <div class="stat-bar">
      <div class="stat"><div class="n">{total}</div><div class="label">fontes mapeadas</div></div>
      <div class="stat stat-success"><div class="n">{confirmadas}</div><div class="label">confirmadas automaticamente</div></div>
      <div class="stat stat-warning"><div class="n">{pendentes}</div><div class="label">pendentes de confirmação manual</div></div>
      <div class="stat stat-critical"><div class="n">{nao_localizadas}</div><div class="label">não localizadas</div></div>
    </div>
  </div>
</header>

<div class="wrap">
  <section>
    <h2>Nacional e Legislativo</h2>
    <div class="legend">
      <span><span class="pill pill-success">Confirmada</span> testada automaticamente, respondeu OK</span>
      <span><span class="pill pill-warning">Confirmar manualmente</span> bloqueio ou erro na checagem automática</span>
      <span><span class="pill pill-critical">Não localizada</span> nenhuma URL candidata encontrada</span>
    </div>
    <div class="cards-nacionais">
      {nacionais_html}
    </div>
  </section>

  <section>
    <h2>Fontes estaduais — Anoreg seccional, Tribunal de Justiça e Corregedoria</h2>
    <input type="search" id="busca" placeholder="Buscar por UF ou nome do estado…" autocomplete="off">
    <div class="cards-estaduais" id="grade-estados">
      {estados_html}
    </div>
  </section>
</div>

<footer>
  <p>
    Gerado automaticamente a partir de <code>config/sources.yaml</code> no repositório
    do projeto. Para sugerir correções, edite o arquivo diretamente ou avise o time
    técnico com a UF e a URL correta.
  </p>
</footer>

<script>
  const busca = document.getElementById('busca');
  const cards = Array.from(document.querySelectorAll('.card-estado'));
  busca.addEventListener('input', () => {{
    const termo = busca.value.trim().toLowerCase();
    for (const card of cards) {{
      const uf = card.dataset.uf.toLowerCase();
      const nome = card.dataset.nome;
      const visivel = !termo || uf.includes(termo) || nome.includes(termo);
      card.classList.toggle('hidden', !visivel);
    }}
  }});
</script>
"""

if __name__ == "__main__":
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(build(), encoding="utf-8")
    print(f"Gerado: {OUT_PATH}")
