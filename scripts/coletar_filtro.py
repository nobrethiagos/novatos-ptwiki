"""
Descobre quais contas da coorte editaram e não são robôs.

Entrada:
    dados/coorte.csv
Saídas:
    dados/brutos/usuarios/lote_0001.json, ...   respostas brutas da API
    dados/usuarios.csv                          coorte + edições, grupos e a coluna "incluir"
"""

import csv
import json
import statistics
from pathlib import Path

from wiki_api import consultar

RAIZ = Path(__file__).resolve().parent.parent
ARQUIVO_COORTE = RAIZ / "dados" / "coorte.csv"
PASTA_BRUTOS = RAIZ / "dados" / "brutos" / "usuarios"
ARQUIVO_SAIDA = RAIZ / "dados" / "usuarios.csv"
TAMANHO_LOTE = 50  # máximo que a API aceita por chamada


def ler_coorte():
    with ARQUIVO_COORTE.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def baixar_lote(numero, ids):
    """Busca um lote pelo ID da conta (não pelo nome, que pode ter mudado desde março)."""
    arquivo = PASTA_BRUTOS / f"lote_{numero:04d}.json"
    if arquivo.exists():
        return json.loads(arquivo.read_text(encoding="utf-8"))
    dados = consultar(
        {
            "action": "query",
            "list": "users",
            "ususerids": "|".join(ids),
            "usprop": "editcount|groups|registration",
        }
    )
    arquivo.write_text(json.dumps(dados, ensure_ascii=False), encoding="utf-8")
    return dados


def coletar(contas):
    PASTA_BRUTOS.mkdir(parents=True, exist_ok=True)
    ids = [c["id_usuario"] for c in contas if c["id_usuario"]]
    info = {}
    lotes = [ids[i : i + TAMANHO_LOTE] for i in range(0, len(ids), TAMANHO_LOTE)]
    for n, lote in enumerate(lotes, start=1):
        for u in baixar_lote(n, lote)["query"]["users"]:
            if "userid" in u:
                info[str(u["userid"])] = u
        if n % 20 == 0 or n == len(lotes):
            print(f"  lote {n} de {len(lotes)}")
    return info


def montar_tabela(contas, info):
    linhas = []
    for c in contas:
        u = info.get(c["id_usuario"])
        encontrada = u is not None and not u.get("missing")
        grupos = u.get("groups", []) if encontrada else []
        edicoes = u.get("editcount", 0) if encontrada else 0
        robo = "bot" in grupos
        linhas.append(
            {
                **c,
                "encontrada": int(encontrada),
                "nome_atual": u.get("name", "") if encontrada else "",
                "edicoes_total": edicoes,
                "grupos": ";".join(g for g in grupos if g != "*"),
                "robo": int(robo),
                "incluir": int(encontrada and edicoes > 0 and not robo),
            }
        )
    with ARQUIVO_SAIDA.open("w", newline="", encoding="utf-8") as f:
        escritor = csv.DictWriter(f, fieldnames=list(linhas[0]))
        escritor.writeheader()
        escritor.writerows(linhas)
    return linhas


def resumir(linhas):
    total = len(linhas)
    nao_encontradas = sum(1 for l in linhas if not l["encontrada"])
    renomeadas = sum(
        1 for l in linhas if l["encontrada"] and l["nome_atual"] != l["usuario"]
    )
    robos = sum(l["robo"] for l in linhas)
    sem_edicao = sum(1 for l in linhas if l["encontrada"] and l["edicoes_total"] == 0)
    incluidas = [l for l in linhas if l["incluir"]]
    edicoes = [l["edicoes_total"] for l in incluidas]

    def pct(n):
        return f"{n} ({100 * n / total:.1f}%)" if total else str(n)

    print("\nResumo (guarde para a metodologia):")
    print(f"  contas na coorte: {total}")
    print(f"  não encontradas pela API (ocultas ou removidas): {pct(nao_encontradas)}")
    print(f"  renomeadas desde a criação: {renomeadas}")
    print(f"  robôs: {robos}")
    print(f"  nunca editaram: {pct(sem_edicao)}")
    print(
        f"  editaram ao menos uma vez e não são robôs (incluir=1): {pct(len(incluidas))}"
    )
    if edicoes:
        uma = sum(1 for e in edicoes if e == 1)
        print(
            f"    com só 1 edição: {uma} ({100 * uma / len(edicoes):.1f}% das incluídas)"
        )
        print(
            f"    mediana de edições: {statistics.median(edicoes):g}  máximo: {max(edicoes)}"
        )
    print(f"  arquivo salvo: {ARQUIVO_SAIDA.relative_to(RAIZ)}")
    print(
        "  Obs.: a contagem de edições inclui todas as páginas e edições já apagadas."
    )


if __name__ == "__main__":
    contas = ler_coorte()
    print(f"Consultando {len(contas)} contas em lotes de {TAMANHO_LOTE}...")
    resumir(montar_tabela(contas, coletar(contas)))
