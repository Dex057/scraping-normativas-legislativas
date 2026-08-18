# Relatórios de execução — Pedido 01 (scraper de normativas)

Base única de relatórios sobre execuções do workflow `scrape.yml` (Actions).
Cada validação/rodada analisada vira uma entrada nova abaixo, mais recente
no topo. Não editar entradas antigas — só adicionar.

---

## 2026-08-18 — Validação do fix de timeout/headers (run 2 vs run 1)

**Runs analisados:**
- Run 1 (antes do fix): [`32058447137`](https://github.com/Dex057/scraping-normativas-legislativas/actions/runs/32058447137) — 2026-08-17 19:05 UTC, 19m46s
- Run 2 (depois do fix): [`32089399381`](https://github.com/Dex057/scraping-normativas-legislativas/actions/runs/32089399381) — 2026-08-18 01:46 UTC, 13m17s

**Fix aplicado entre as duas rodadas:** commit `f075c86` — timeout de 20s → 30s
e adição de headers `Accept` / `Accept-Language: pt-BR` nas requisições, para
reduzir timeouts de sites lentos e falsos-positivos de bloqueio por WAF.

### Resultado

| | Run 1 | Run 2 |
|---|---|---|
| Total de fontes | 75 | 75 |
| Sucesso | 47 | **54** |
| Falha | 28 | **21** |
| Duração | 19m46s | **13m17s** |

**Fontes recuperadas pelo fix (falhavam no run 1, OK no run 2):**
`ac_corregedoria`, `ac_tj`, `al_corregedoria`, `al_tj`, `pe_tj` (timeout →
resolvido pelo timeout maior), `pa_tj` (erro de DNS transitório → resolvido),
`rj_anoreg` (timeout de leitura → resolvido).

**Nenhuma fonte nova quebrou** (zero regressões entre run 1 e run 2).

**Fontes que ainda falham nos dois runs (21, sem mudança):**
- **403 Forbidden** (16): `anoreg_br`, `arpen_brasil`, `ap_tj`, `ap_corregedoria`,
  `ba_anoreg`, `es_anoreg`, `es_corregedoria`, `es_tj`, `ma_anoreg`, `mg_anoreg`,
  `mg_corregedoria`, `mg_tj`, `ms_anoreg`, `mt_anoreg`, `pb_anoreg`
- **Timeout persistente** (4): `ms_corregedoria`, `ms_tj`, `rs_corregedoria`, `rs_tj`
- **Servidor derruba conexão** (2): `pi_corregedoria`, `pi_tj`

### Diagnóstico

O fix resolveu 100% dos casos de timeout "de margem" (sites lentos que
respondiam perto do limite de 20s). Não resolveu os 403 — esses são bloqueios
ativos de WAF/anti-bot que não cedem a ajuste de timeout ou header de idioma;
exigiriam algo como rotação de user-agent de navegador real, rendering
headless (Playwright) ou proxy residencial para contornar. Vale priorizar
isso só se as 21 fontes pendentes (concentradas em MG e ES) forem relevantes
juridicamente para o cliente — ver `TODO_FONTES_ESTADUAIS.md`.

Dados de ambos os runs já persistidos e commitados em `data/normativas.db`
pelo próprio workflow (não requer nova execução para aparecer no painel
quando ele for conectado ao Streamlit Community Cloud).
