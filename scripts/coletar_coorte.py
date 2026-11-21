"""
Lista as contas criadas no período da coorte.
Saídas:
    dados/brutos/coorte/pagina_0001.json, ...  respostas brutas da API
    dados/coorte.csv                           contas que entram na coorte
"""

import csv
import json
from collections import Counter
from pathlib import Path

from wiki_api import consultar_tudo

# Mesmo período do definicoes.md (UTC).
INICIO = "2025-03-01T00:00:00Z"
FIM = "2025-03-31T23:59:59Z"
ACOES_INCLUIDAS = {"create", "create2", "byemail"}  # autocreate fica de fora

RAIZ = Path(__file__).resolve().parent.parent
PASTA_BRUTOS = RAIZ / "dados" / "brutos" / "coorte"
ARQUIVO_CSV = RAIZ / "dados" / "coorte.csv"


def coletar():
    PASTA_BRUTOS.mkdir(parents=True, exist_ok=True)
    params = {
        "action": "query",
        "list": "logevents",
        "letype": "newusers",
        "lestart": INICIO,
        "leend": FIM,
        "ledir": "newer",
        "lelimit": "max",
    }
    eventos = []
    for n, pagina in enumerate(consultar_tudo(params), start=1):
        (PASTA_BRUTOS / f"pagina_{n:04d}.json").write_text(
            json.dumps(pagina, ensure_ascii=False), encoding="utf-8"
        )
        novos = pagina["query"]["logevents"]
        eventos.extend(novos)
        print(f"  página {n}: {len(novos)} eventos (total {len(eventos)})")
    return eventos


def salvar_csv(eventos):
    acoes = Counter(e.get("action", "?") for e in eventos)
    linhas, sem_nome = [], 0
    for e in eventos:
        if e.get("action") not in ACOES_INCLUIDAS:
            continue
        if "title" not in e:  # registro oculto pelos administradores
            sem_nome += 1
            continue
        linhas.append(
            {
                "usuario": e["title"].split(":", 1)[1],  # tira o prefixo "Usuário(a):"
                "criada_em": e["timestamp"],
                "acao": e["action"],
                "id_usuario": e.get("params", {}).get("userid", ""),
                "criada_por": e.get("user", ""),
                "id_registro": e.get("logid", ""),
            }
        )

    ARQUIVO_CSV.parent.mkdir(parents=True, exist_ok=True)
    with ARQUIVO_CSV.open("w", newline="", encoding="utf-8") as f:
        escritor = csv.DictWriter(
            f, fieldnames=list(linhas[0]) if linhas else ["usuario"]
        )
        escritor.writeheader()
        escritor.writerows(linhas)

    print("\nResumo (guarde para a metodologia):")
    print(f"  eventos de criação de conta no período: {len(eventos)}")
    for acao, n in acoes.most_common():
        print(f"    {acao}: {n}")
    if sem_nome:
        print(f"  registros ocultos, descartados: {sem_nome}")
    print(f"  contas na coorte (create, create2, byemail): {len(linhas)}")
    if linhas:
        print(
            f"  primeira: {linhas[0]['criada_em']}  última: {linhas[-1]['criada_em']}"
        )
    print(f"  arquivo salvo: {ARQUIVO_CSV.relative_to(RAIZ)}")


if __name__ == "__main__":
    print(f"Coletando contas criadas de {INICIO} a {FIM}...")
    salvar_csv(coletar())
