# Pedido 01 — Monitoramento e Curadoria de Atualizações Normativas e Legislativas

Automação quinzenal que varre fontes nacionais, legislativas e estaduais em
busca de novos atos normativos, extrai os achados via IA (Claude Haiku 4.5) e
disponibiliza um painel de triagem para validação manual.

## Arquitetura

```
config/sources.yaml      → lista de fontes monitoradas (nacional + 27 UF + DF)
src/fetch.py              → busca a página e limpa o HTML (preserva links)
src/extract.py            → Claude Haiku 4.5 extrai achados estruturados (JSON Schema)
src/db.py                 → SQLite: achados, execuções, dedup, status de triagem
src/orchestrator.py       → roda o ciclo completo (chamado pelo GitHub Actions)
app.py                    → painel Streamlit de triagem (human-in-the-loop)
.github/workflows/scrape.yml → agenda a execução a cada 15 dias
```

**Por que IA em vez de um parser por site?** Escrever e manter um parser
CSS/XPath para cada uma das ~80+ fontes (Anoreg seccional, TJ e Corregedoria
de 27 estados + DF, mais as fontes nacionais) é o gargalo real do projeto —
não o custo de API. `fetch.py` cuida da parte mecânica (buscar e limpar a
página); `extract.py` manda o texto limpo para o Claude Haiku 4.5, que devolve
os achados já estruturados via *structured outputs*. Isso é resiliente a
mudanças de layout dos sites e elimina a necessidade de 80+ parsers
específicos. Custo estimado: **menos de US$ 3/mês** para o ciclo completo.

## Persistência e deploy

- O banco (`data/normativas.db`) é versionado no próprio repositório. O
  GitHub Actions atualiza e faz commit dele de volta a cada execução.
- O painel roda no **Streamlit Community Cloud**, apontando para este
  repositório — cada push (incluindo o commit automático do bot) dispara um
  redeploy automático, então o painel sempre reflete o último ciclo.

## Encadeamento com o Pedido 02

Ao final do ciclo, o workflow dispara um `repository_dispatch` para o
repositório do
[Pedido 02](https://github.com/Dex057/automacao-conteudo-scraping)
(inteligência de conteúdo para redes sociais), que lê os achados marcados
como `pertinente` aqui e gera sugestões de pauta para Instagram. Requer o
secret `PEDIDO02_DISPATCH_TOKEN` (PAT com permissão de disparar
`repository_dispatch` no repositório do Pedido 02) configurado aqui.

> 📋 **Guia passo a passo da configuração** (chave da Anthropic + tokens do
> GitHub + secrets nos dois repositórios):
> [`CONFIGURACAO_CREDENCIAIS.md`](https://github.com/Dex057/automacao-conteudo-scraping/blob/main/docs/CONFIGURACAO_CREDENCIAIS.md)
> no repositório do Pedido 02.

## Configuração necessária

1. **Secrets no GitHub**: `ANTHROPIC_API_KEY` e `PEDIDO02_DISPATCH_TOKEN`
   (Settings → Secrets → Actions).
2. **Streamlit Community Cloud**: conectar este repositório, apontar para
   `app.py`.
3. **Validação jurídica das fontes**: as 87 fontes (nacionais + estaduais)
   já estão mapeadas em `config/sources.yaml` — 75 confirmadas automaticamente,
   12 pendentes de confirmação manual. Ver `docs/validacao_fontes.html` (o
   documento gerado para revisão do time jurídico) e `TODO_FONTES_ESTADUAIS.md`
   para o detalhamento por estado.

## Rodando localmente

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-ant-...

# Roda um ciclo de coleta manualmente
python -m src.orchestrator

# Abre o painel de triagem
streamlit run app.py
```

## Status do escopo (Pedido 01)

- [x] Arquitetura de coleta + extração via IA
- [x] Persistência com deduplicação
- [x] Painel de triagem (Streamlit)
- [x] Agendamento quinzenal (GitHub Actions)
- [x] Fontes nacionais/legislativas mapeadas e testadas (CNJ, Anoreg-BR, IRIB,
      Arpen-Brasil, Colégio Notarial do Brasil, Planalto)
- [x] Fontes estaduais mapeadas — 26 estados + DF, 87 fontes no total (75
      confirmadas automaticamente, 12 pendentes de confirmação manual —
      ver `docs/validacao_fontes.html` e `TODO_FONTES_ESTADUAIS.md`)
- [ ] Validação jurídica das fontes pendentes de confirmação manual
- [ ] Validação em produção do primeiro ciclo real (depende de
      `ANTHROPIC_API_KEY` configurada)
