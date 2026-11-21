"""
Baixa as edições visíveis dos novatos e acha a primeira edição em artigo.

Entrada:
    dados/usuarios.csv (só as contas com incluir=1)
Saídas:
    dados/brutos/edicoes/lote_0001.json, ...  edições brutas por lote
    dados/edicoes.csv                          uma linha por edição visível
    dados/novatos.csv                          uma linha por novato, com a primeira edição em artigo
"""

import csv
import json
from collections import defaultdict
from pathlib import Path

from wiki_api import consultar_tudo

INICIO = "2025-03-01T00:00:00Z"
TAMANHO_LOTE = 50  # máximo de contas por chamada

RAIZ = Path(__file__).resolve().parent.parent
ARQUIVO_USUARIOS = RAIZ / "dados" / "usuarios.csv"
PASTA_BRUTOS = RAIZ / "dados" / "brutos" / "edicoes"
ARQUIVO_EDICOES = RAIZ / "dados" / "edicoes.csv"
ARQUIVO_NOVATOS = RAIZ / "dados" / "novatos.csv"


def ler_contas():
    with ARQUIVO_USUARIOS.open(encoding="utf-8") as f:
        return [c for c in csv.DictReader(f) if c["incluir"] == "1"]


def baixar_lote(numero, ids):
    arquivo = PASTA_BRUTOS / f"lote_{numero:04d}.json"
    if arquivo.exists():
        return json.loads(arquivo.read_text(encoding="utf-8"))
    params = {
        "action": "query",
        "list": "usercontribs",
        "ucuserids": "|".join(ids),
        "ucstart": INICIO,
        "ucdir": "newer",
        "uclimit": "max",
        "ucprop": "ids|title|timestamp|comment|size|sizediff|tags|flags",
    }
    contribs = []
    for pagina in consultar_tudo(params):
        contribs.extend(pagina["query"]["usercontribs"])
    # Só grava quando o lote termina, para uma interrupção não deixar lote pela metade.
    arquivo.write_text(json.dumps(contribs, ensure_ascii=False), encoding="utf-8")
    return contribs


def coletar(contas):
    PASTA_BRUTOS.mkdir(parents=True, exist_ok=True)
    ids = [c["id_usuario"] for c in contas]
    lotes = [ids[i : i + TAMANHO_LOTE] for i in range(0, len(ids), TAMANHO_LOTE)]
    todas = {}
    for n, lote in enumerate(lotes, start=1):
        for e in baixar_lote(n, lote):
            todas[e["revid"]] = (
                e  # chave pelo ID da revisão: evita contar uma edição duas vezes
            )
        if n % 10 == 0 or n == len(lotes):
            print(f"  lote {n} de {len(lotes)} ({len(todas)} edições até agora)")
    return list(todas.values())


def salvar_edicoes(edicoes):
    campos = [
        "id_usuario",
        "usuario",
        "revid",
        "parentid",
        "ns",
        "titulo",
        "timestamp",
        "tamanho",
        "diferenca",
        "pagina_nova",
        "menor",
        "etiquetas",
        "sumario",
    ]
    with ARQUIVO_EDICOES.open("w", newline="", encoding="utf-8") as f:
        escritor = csv.DictWriter(f, fieldnames=campos)
        escritor.writeheader()
        for e in edicoes:
            escritor.writerow(
                {
                    "id_usuario": e["userid"],
                    "usuario": e["user"],
                    "revid": e["revid"],
                    "parentid": e.get("parentid", ""),
                    "ns": e["ns"],
                    "titulo": e["title"],
                    "timestamp": e["timestamp"],
                    "tamanho": e.get("size", ""),
                    "diferenca": e.get("sizediff", ""),
                    "pagina_nova": int(bool(e.get("new"))),
                    "menor": int(bool(e.get("minor"))),
                    "etiquetas": ";".join(e.get("tags", [])),
                    "sumario": e.get("comment", ""),
                }
            )


def salvar_novatos(contas, edicoes):
    por_conta = defaultdict(list)
    for e in edicoes:
        por_conta[str(e["userid"])].append(e)

    linhas = []
    for c in contas:
        minhas = sorted(
            por_conta.get(c["id_usuario"], []),
            key=lambda e: (e["timestamp"], e["revid"]),
        )
        em_artigos = [e for e in minhas if e["ns"] == 0]
        primeira = em_artigos[0] if em_artigos else {}
        total = int(c["edicoes_total"])
        linhas.append(
            {
                "id_usuario": c["id_usuario"],
                "usuario": c["usuario"],
                "criada_em": c["criada_em"],
                "edicoes_total": total,
                "edicoes_visiveis": len(minhas),
                "edicoes_apagadas_estimadas": max(0, total - len(minhas)),
                "edicoes_visiveis_artigos": len(em_artigos),
                "primeira_revid": primeira.get("revid", ""),
                "primeira_parentid": primeira.get("parentid", ""),
                "primeira_titulo": primeira.get("title", ""),
                "primeira_timestamp": primeira.get("timestamp", ""),
                "primeira_pagina_nova": int(bool(primeira.get("new")))
                if primeira
                else "",
                "primeira_etiquetas": ";".join(primeira.get("tags", [])),
                "incluir_final": int(bool(em_artigos)),
            }
        )

    with ARQUIVO_NOVATOS.open("w", newline="", encoding="utf-8") as f:
        escritor = csv.DictWriter(f, fieldnames=list(linhas[0]))
        escritor.writeheader()
        escritor.writerows(linhas)
    return linhas


def resumir(edicoes, linhas):
    total = len(linhas)
    sem_visiveis = sum(1 for l in linhas if l["edicoes_visiveis"] == 0)
    fora_artigos = sum(
        1
        for l in linhas
        if l["edicoes_visiveis"] > 0 and l["edicoes_visiveis_artigos"] == 0
    )
    finais = [l for l in linhas if l["incluir_final"]]
    com_apagadas = sum(1 for l in linhas if l["edicoes_apagadas_estimadas"] > 0)
    criaram = sum(1 for l in finais if l["primeira_pagina_nova"] == 1)
    revertidas_tag = sum(
        1 for l in finais if "mw-reverted" in l["primeira_etiquetas"].split(";")
    )

    def pct(n, base):
        return f"{n} ({100 * n / base:.1f}%)" if base else str(n)

    print("\nResumo (guarde para a metodologia):")
    print(f"  contas consultadas (incluir=1 no filtro): {total}")
    print(f"  edições visíveis baixadas: {len(edicoes)}")
    print(
        f"  contas sem nenhuma edição visível (tudo apagado): {pct(sem_visiveis, total)}"
    )
    print(
        f"  contas com edições visíveis, mas nenhuma em artigo: {pct(fora_artigos, total)}"
    )
    print(f"  contas com edições apagadas (estimativa): {pct(com_apagadas, total)}")
    print(
        f"  NOVATOS NO ESTUDO (ao menos uma edição visível em artigo): {pct(len(finais), total)}"
    )
    print(f"    primeira edição criou um artigo novo: {pct(criaram, len(finais))}")
    print(
        f"    primeira edição com a etiqueta mw-reverted: {pct(revertidas_tag, len(finais))}"
    )
    print(
        f"  arquivos salvos: {ARQUIVO_EDICOES.relative_to(RAIZ)}, {ARQUIVO_NOVATOS.relative_to(RAIZ)}"
    )
    print(
        "  Obs.: a etiqueta mw-reverted é só uma prévia; a detecção por SHA1 vem no próximo passo."
    )


if __name__ == "__main__":
    contas = ler_contas()
    print(f"Baixando edições de {len(contas)} contas em lotes de {TAMANHO_LOTE}...")
    edicoes = coletar(contas)
    salvar_edicoes(edicoes)
    resumir(edicoes, salvar_novatos(contas, edicoes))
