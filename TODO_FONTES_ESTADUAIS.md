# Checklist de mapeamento das fontes estaduais

Para cada UF, encontrar e validar manualmente (abrir a URL, confirmar que
lista atos/notícias recentes) 3 páginas:

1. **Anoreg seccional** — página de notícias/atos da associação estadual dos
   notários e registradores.
2. **TJ (Tribunal de Justiça)** — página de comunicados, provimentos ou atos
   normativos do tribunal.
3. **Corregedoria Geral de Justiça** — página de provimentos/atos da CGJ do
   estado (às vezes é uma seção dentro do site do próprio TJ).

Depois de validar cada URL, adicionar a entrada correspondente em
`config/sources.yaml` (copiar o formato do bloco `sp_*` já preenchido) com
`ativo: true`.

## Status por UF

| UF | Anoreg seccional | TJ | Corregedoria | Observações |
|----|:---:|:---:|:---:|---|
| AC | ⬜ | ⬜ | ⬜ | |
| AL | ⬜ | ⬜ | ⬜ | |
| AM | ⬜ | ⬜ | ⬜ | |
| AP | ⬜ | ⬜ | ⬜ | |
| BA | ⬜ | ⬜ | ⬜ | |
| CE | ⬜ | ⬜ | ⬜ | |
| DF | ⬜ | ⬜ | ⬜ | |
| ES | ⬜ | ⬜ | ⬜ | |
| GO | ⬜ | ⬜ | ⬜ | |
| MA | ⬜ | ⬜ | ⬜ | |
| MG | ⬜ | ⬜ | ⬜ | |
| MS | ⬜ | ⬜ | ⬜ | |
| MT | ⬜ | ⬜ | ⬜ | |
| PA | ⬜ | ⬜ | ⬜ | |
| PB | ⬜ | ⬜ | ⬜ | |
| PE | ⬜ | ⬜ | ⬜ | |
| PI | ⬜ | ⬜ | ⬜ | |
| PR | ⬜ | ⬜ | ⬜ | |
| RJ | ⬜ | ⬜ | ⬜ | |
| RN | ⬜ | ⬜ | ⬜ | |
| RO | ⬜ | ⬜ | ⬜ | |
| RR | ⬜ | ⬜ | ⬜ | |
| RS | ⬜ | ⬜ | ⬜ | |
| SC | ⬜ | ⬜ | ⬜ | |
| SE | ⬜ | ⬜ | ⬜ | |
| SP | ✅ | ⬜ | ⬜ | Anoreg-SP preenchida em `sources.yaml`; TJ e Corregedoria ainda como placeholder |
| TO | ⬜ | ⬜ | ⬜ | |

**Sugestão de próximo passo:** delegar esse mapeamento a uma pesquisa
dedicada (ex.: agente com acesso a busca na web), validando cada URL antes de
ativá-la — evita quebrar o ciclo de produção com links errados.
