# Status do mapeamento das fontes estaduais

Pesquisa concluída para os 26 estados + DF. Resultado completo em
`config/sources.yaml` (gerado por `scripts/gerar_sources_yaml.py`) e no
**documento de validação para o jurídico**: `docs/validacao_fontes.html`
(também publicado como artifact — link compartilhado na conversa).

## Metodologia

1. Diretório oficial da Anoreg-BR (`anoreg.org.br/site/anoregs-estaduais/`)
   para localizar as seccionais estaduais.
2. Padrão de domínio `tj<uf>.jus.br` para os Tribunais de Justiça (validado
   individualmente).
3. Busca dedicada por "Corregedoria Geral de Justiça [estado] provimentos"
   para localizar a página específica de atos normativos de cada CGJ —
   como não existe um padrão único, cada uma foi pesquisada e confirmada.
4. Cada URL candidata foi testada com uma requisição HTTP real (não é
   suposição) e o resultado (200 OK / erro / bloqueio) está registrado como
   `nota` na fonte, quando relevante.

## Resultado

| Estado | Anoreg seccional | TJ | Corregedoria | Observação |
|----|:---:|:---:|:---:|---|
| AC | ⚠️ não localizada | ✅ | ✅ | Anoreg-AC só tem página no Facebook |
| AL | ✅ | ✅ | ✅ | |
| AM | ✅ | ✅ | ✅ | |
| AP | ⚠️ não localizada | ✅ | ✅ | Anoreg-AP sem site ativo localizado |
| BA | ✅ | ✅ | ✅ | |
| CE | ✅ | ✅ | ✅ | |
| DF | ✅ | ✅ | ✅ | Anoreg-DF só responde via HTTP (não HTTPS) |
| ES | ✅ | ✅ | ✅ | |
| GO | ✅ | ⚠️ confirmar | ⚠️ confirmar | TJGO bloqueou checagem automática (403) |
| MA | ✅ | ✅ | ✅ | |
| MG | ✅ | ✅ | ✅ | |
| MS | ✅ | ✅ | ✅ | |
| MT | ✅ | ✅ | ✅ | |
| PA | ✅ | ✅ | ⚠️ confirmar | Página de provimentos do TJPA deu erro 500 no teste |
| PB | ✅ | ⚠️ confirmar | ⚠️ confirmar | TJPB bloqueou checagem automática (403) |
| PE | ⚠️ não localizada | ✅ | ✅ | Anoreg-PE sem site ativo localizado |
| PI | ✅ | ✅ | ✅ | |
| PR | ✅ | ✅ | ✅ | |
| RJ | ✅ | ✅ | ✅ | Existe também `cgj.tjrj.jus.br` — comparar antes de ativar |
| RN | ✅ | ⚠️ confirmar | ⚠️ confirmar | TJRN bloqueou checagem automática (403) |
| RO | ⚠️ não localizada | ✅ | ✅ | Anoreg-RO sem site ativo localizado |
| RR | ⚠️ não localizada | ✅ | ✅ | Anoreg-RR sem site localizado |
| RS | ✅ | ✅ | ✅ | |
| SC | ✅ | ✅ | ✅ | |
| SE | ✅ | ✅ | ✅ | |
| SP | ✅ | ✅ | ✅ | |
| TO | ✅ | ✅ | ✅ | |

**Resumo:** 75 de 87 fontes confirmadas automaticamente (respondem HTTP 200).
12 pendentes de confirmação manual — 6 por bloqueio anti-bot dos sites
(prováveis corretas, só não puderam ser validadas por requisição automática)
e 6 por associação estadual sem site oficial localizado (Anoreg de AC, AP,
PE, RO, RR — precisam de contato direto ou canal alternativo).

## Próximos passos

1. Enviar `docs/validacao_fontes.html` (ou o link do artifact) para a pessoa
   do jurídico validar cada fonte, com atenção especial aos itens marcados
   como "Confirmar manualmente" e "Não localizada".
2. Para os bloqueios anti-bot (GO, PB, RN): abrir manualmente no navegador
   para confirmar que a URL é a correta antes de ativar (`ativo: true` em
   `config/sources.yaml`).
3. Para as Anoregs não localizadas (AC, AP, PE, RO, RR): confirmar com a
   Anoreg-BR ou contato direto se há um canal alternativo (Instagram,
   Facebook) que valha a pena monitorar, ou se a fonte fica de fora do
   escopo por ora.
