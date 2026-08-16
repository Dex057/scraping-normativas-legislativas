"""Script auxiliar (uso único) para gerar config/sources.yaml a partir dos
dados coletados na pesquisa de fontes estaduais (ver TODO_FONTES_ESTADUAIS.md
para a metodologia). Não faz parte do pipeline de produção.
"""

from __future__ import annotations

import yaml
from pathlib import Path

NACIONAIS = [
    dict(id="cnj", nome="CNJ — Conselho Nacional de Justiça",
         categoria="nacional_extrajudicial", url="https://www.cnj.jus.br/category/noticias/",
         ativo=True, modo="estatico",
         nota=("Repositório oficial de atos normativos (atos.cnj.jus.br/atos) é uma SPA "
               "que carrega a tabela via JS/API sob demanda e não é resolvível com "
               "Playwright simples — usando a página de notícias como alternativa.")),
    dict(id="anoreg_br", nome="Anoreg-BR", categoria="nacional_extrajudicial",
         url="https://www.anoreg.org.br/site/category/noticias/", ativo=True, modo="estatico"),
    dict(id="irib", nome="IRIB — Instituto de Registro Imobiliário do Brasil",
         categoria="nacional_extrajudicial", url="https://irib.org.br/noticias", ativo=True, modo="estatico"),
    dict(id="arpen_brasil", nome="Arpen-Brasil", categoria="nacional_extrajudicial",
         url="https://www.arpenbrasil.org.br/noticias/", ativo=True, modo="estatico"),
    dict(id="colegio_notarial_brasil", nome="Colégio Notarial do Brasil - Conselho Federal",
         categoria="nacional_extrajudicial", url="https://www.notariado.org.br/noticias/",
         ativo=True, modo="estatico"),
    dict(id="planalto", nome="Portal do Planalto — Atos Normativos", categoria="legislativo",
         url="https://www.gov.br/planalto/pt-br/acesso-a-informacao/institucional/atos-normativos",
         ativo=True, modo="estatico"),
]

# (uf, anoreg_url|None, anoreg_nota, tj_url, tj_ok, corregedoria_url, corregedoria_ok, corregedoria_nota)
ESTADOS = [
    ("AC", None, "Não localizado site oficial — apenas página no Facebook (anoregacre).",
     "https://www.tjac.jus.br", True, "https://www.tjac.jus.br/corregedoria", True, None),
    ("AL", "https://www.anoreg-al.org.br", None,
     "https://www.tjal.jus.br", True, "https://www.tjal.jus.br/corregedoria", True, None),
    ("AM", "https://anoregam.org.br/", None,
     "https://www.tjam.jus.br", True,
     "https://www.tjam.jus.br/index.php/cgj-publicacoes/cgj-atos/provimentos", True, None),
    ("AP", None, "Não localizado site oficial ativo (CNPJ existe, sem site encontrado).",
     "https://www.tjap.jus.br", True, "https://www.tjap.jus.br/corregedoria", True, None),
    ("BA", "https://www.anoregba.org.br", None,
     "https://www.tjba.jus.br", True, "https://www.tjba.jus.br/corregedoria", True, None),
    ("CE", "https://www.anoregce.org.br", None,
     "https://www.tjce.jus.br", True, "https://www.tjce.jus.br/corregedoria", True, None),
    ("DF", "http://www.anoregdf.com.br", "Site só respondeu via HTTP (erro de certificado em HTTPS).",
     "https://www.tjdft.jus.br", True, "https://www.tjdft.jus.br/publicacoes/provimentos", True, None),
    ("ES", "https://www.sinoreg-es.org.br", None,
     "https://www.tjes.jus.br", True, "https://www.tjes.jus.br/corregedoria", True, None),
    ("GO", "https://www.anoreggo.com.br", None,
     "https://www.tjgo.jus.br", False,
     "https://www.tjgo.jus.br/index.php/91-corregedoria/publicacoes/356-provimentos-corregedoria", False,
     "Domínio bloqueou a checagem automatizada (HTTP 403 — provável proteção anti-bot); abrir manualmente no navegador para confirmar."),
    ("MA", "https://anoregma.org.br", None,
     "https://www.tjma.jus.br", True, "https://www.tjma.jus.br/corregedoria", True, None),
    ("MG", "https://serjus.com.br", None,
     "https://www.tjmg.jus.br", True,
     "https://www.tjmg.jus.br/portal-tjmg/institucional/corregedoria/", True, None),
    ("MS", "https://www.anoregms.org.br", None,
     "https://www.tjms.jus.br", True, "https://www.tjms.jus.br/corregedoria", True, None),
    ("MT", "https://www.anoregmt.org.br", None,
     "https://www.tjmt.jus.br", True, "https://www.tjmt.jus.br/corregedoria", True, None),
    ("PA", "https://cartoriosdopara.com.br", None,
     "https://www.tjpa.jus.br", True,
     "https://www.tjpa.jus.br/PortalExterno/institucional/Corregedoria-Geral-de-Justica/659290-provimentos.xhtml", False,
     "Página retornou erro 500 no momento do teste (aplicação JSF sensível a sessão); confirmar manualmente e, se persistir, usar a home do TJPA como ponto de partida."),
    ("PB", "https://www.anoregpb.org.br", None,
     "https://www.tjpb.jus.br", False,
     "https://corregedoria.tjpb.jus.br/provimentos-da-corregedoria/", False,
     "Domínio bloqueou a checagem automatizada (HTTP 403 — provável proteção anti-bot); abrir manualmente no navegador para confirmar."),
    ("PE", None, "Não localizado site oficial ativo (DNS não resolve; associação pode ter mudado de canal).",
     "https://www.tjpe.jus.br", True,
     "https://portal.tjpe.jus.br/web/corregedoria/atos-normativos/provimentos", True, None),
    ("PI", "https://anoregpi.org.br", "Site só respondeu sem o prefixo 'www' (certificado não cobre www.).",
     "https://www.tjpi.jus.br", True,
     "https://www.tjpi.jus.br/portaltjpi/corregedoria/provimentos/", True, None),
    ("PR", "https://www.anoregpr.org.br", None,
     "https://www.tjpr.jus.br", True, "https://www.tjpr.jus.br/corregedoria", True, None),
    ("RJ", "https://www.anoregrj.com.br", None,
     "https://www.tjrj.jus.br", True, "https://www.tjrj.jus.br/corregedoria", True,
     "Existe também um subdomínio dedicado: https://cgj.tjrj.jus.br/ — comparar as duas antes de ativar."),
    ("RN", "https://www.anoregrn.org.br", None,
     "https://www.tjrn.jus.br", False,
     "https://corregedoria.tjrn.jus.br/", False,
     "Domínio bloqueou a checagem automatizada (HTTP 403 — provável proteção anti-bot); abrir manualmente no navegador para confirmar."),
    ("RO", None, "Não localizado site oficial ativo (DNS não resolve; associação pode ter mudado de canal).",
     "https://www.tjro.jus.br", True, "https://www.tjro.jus.br/corregedoria", True, None),
    ("RR", None, "Não localizado site oficial.",
     "https://www.tjrr.jus.br", True,
     "https://www.tjrr.jus.br/index.php/correicoes-judiciais/109-corregedoria-geral", True, None),
    ("RS", "https://www.anoregrs.org.br", None,
     "https://www.tjrs.jus.br", True,
     "https://www.tjrs.jus.br/novo/institucional/administracao/corregedoria-geral-da-justica/", True, None),
    ("SC", "https://anoregsc.org.br", None,
     "https://www.tjsc.jus.br", True, "https://www.tjsc.jus.br/corregedoria", True, None),
    ("SE", "https://www.anoregse.org.br", None,
     "https://www.tjse.jus.br", True, "https://www.tjse.jus.br/corregedoria", True, None),
    ("SP", "https://www.anoregsp.org.br/", None,
     "https://www.tjsp.jus.br", True, "https://www.tjsp.jus.br/corregedoria", True, None),
    ("TO", "https://www.anoregto.com.br", None,
     "https://www.tjto.jus.br", True,
     "https://corregedoria.tjto.jus.br/cidadao/legislacao-e-normas/atos-normativos", True, None),
]


def montar_fontes_estaduais() -> list[dict]:
    fontes = []
    for uf, anoreg_url, anoreg_nota, tj_url, tj_ok, corr_url, corr_ok, corr_nota in ESTADOS:
        uf_lower = uf.lower()

        if anoreg_url:
            fontes.append(dict(
                id=f"{uf_lower}_anoreg", nome=f"Anoreg-{uf}", categoria="estadual_anoreg",
                estado=uf, url=anoreg_url, ativo=True, modo="estatico",
                **({"nota": anoreg_nota} if anoreg_nota else {}),
            ))
        else:
            fontes.append(dict(
                id=f"{uf_lower}_anoreg", nome=f"Anoreg-{uf}", categoria="estadual_anoreg",
                estado=uf, url=None, ativo=False, modo="estatico", nota=anoreg_nota,
            ))

        fontes.append(dict(
            id=f"{uf_lower}_tj", nome=f"TJ{uf} — página institucional", categoria="estadual_tj",
            estado=uf, url=tj_url, ativo=tj_ok, modo="estatico",
            **({} if tj_ok else {"nota": (
                "Domínio bloqueou a checagem automatizada (HTTP 403 — provável proteção "
                "anti-bot); abrir manualmente no navegador para confirmar.")}),
        ))

        fontes.append(dict(
            id=f"{uf_lower}_corregedoria", nome=f"Corregedoria Geral de Justiça — {uf}",
            categoria="estadual_corregedoria", estado=uf, url=corr_url, ativo=corr_ok,
            modo="estatico", **({"nota": corr_nota} if corr_nota else {}),
        ))
    return fontes


def main() -> None:
    fontes = NACIONAIS + montar_fontes_estaduais()
    doc = {"fontes": fontes}

    out_path = Path(__file__).resolve().parent.parent / "config" / "sources.yaml"
    header = (
        "# Configuração das fontes monitoradas pelo Pedido 01.\n"
        "#\n"
        "# Cada fonte é um dicionário com:\n"
        "#   id:          identificador único e estável (usado para dedup/histórico — não mudar depois de criado)\n"
        "#   nome:        nome legível da fonte\n"
        "#   categoria:   nacional_extrajudicial | legislativo | estadual_anoreg | estadual_tj | estadual_corregedoria\n"
        "#   estado:      sigla UF (só para categorias estaduais; ausente para nacionais)\n"
        "#   url:         página a ser varrida (null quando a fonte ainda não foi localizada)\n"
        "#   ativo:       true/false — false = pendente de confirmação manual antes de ativar\n"
        "#   modo:        \"estatico\" (requests/BeautifulSoup) | \"js\" (Playwright)\n"
        "#   nota:        observação da pesquisa automatizada (bloqueio, erro, ambiguidade) — ver\n"
        "#                também o documento de validação gerado para a equipe jurídica.\n"
        "#\n"
        "# Gerado por scripts/gerar_sources_yaml.py a partir da pesquisa registrada em\n"
        "# TODO_FONTES_ESTADUAIS.md. Todas as fontes com ativo:false precisam de confirmação\n"
        "# manual (ver doc de validação) antes de entrarem no ciclo de produção.\n\n"
    )
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(header)
        yaml.dump(doc, f, allow_unicode=True, sort_keys=False, default_flow_style=False, width=100)

    print(f"Gerado: {out_path}")
    print(f"Total de fontes: {len(fontes)} ({sum(1 for x in fontes if x['ativo'])} ativas)")


if __name__ == "__main__":
    main()
