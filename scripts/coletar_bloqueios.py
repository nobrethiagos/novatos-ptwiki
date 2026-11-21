"""
Marca os novatos bloqueados até 30 dias depois da criação da conta.

Entradas:
    dados/novatos.csv (só incluir_final=1)
    dados/reversoes.csv (só para o cruzamento do resumo)
Saídas:
    dados/brutos/bloqueios/pagina_0001.json, ...  registro de bloqueios bruto
    dados/bloqueios.csv                            uma linha por novato
"""

import csv
import json
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path

from wiki_api import consultar_tudo

INICIO = "2025-03-01T00:00:00Z"
FIM = "2025-05-01T00:00:00Z"  # 31/03 + 30 dias, com folga
JANELA = timedelta(days=30)

RAIZ = Path(__file__).resolve().parent.parent
ARQUIVO_NOVATOS = RAIZ / "dados" / "novatos.csv"
ARQUIVO_REVERSOES = RAIZ / "dados" / "reversoes.csv"
PASTA = RAIZ / "dados" / "brutos" / "bloqueios"
ARQUIVO_SAIDA = RAIZ / "dados" / "bloqueios.csv"


def data(ts):
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def baixar_registro():
    PASTA.mkdir(parents=True, exist_ok=True)
    paginas = sorted(PASTA.glob("pagina_*.json"))
    if paginas and (PASTA / "completo").exists():
        return [
            e
            for p in paginas
            for e in json.loads(p.read_text(encoding="utf-8"))["query"]["logevents"]
        ]
    eventos = []
    for n, pagina in enumerate(
        consultar_tudo(
            {
                "action": "query",
                "list": "logevents",
                "letype": "block",
                "lestart": INICIO,
                "leend": FIM,
                "ledir": "newer",
                "lelimit": "max",
            }
        ),
        start=1,
    ):
        (PASTA / f"pagina_{n:04d}.json").write_text(
            json.dumps(pagina, ensure_ascii=False), encoding="utf-8"
        )
        eventos.extend(pagina["query"]["logevents"])
        print(f"  página {n}: {len(eventos)} eventos")
    (PASTA / "completo").write_text("ok", encoding="utf-8")
    return eventos


def ler(caminho, filtro=None):
    with caminho.open(encoding="utf-8") as f:
        linhas = list(csv.DictReader(f))
    return [l for l in linhas if filtro is None or filtro(l)]


def montar(novatos, eventos):
    por_conta = {}
    for e in eventos:
        if e.get("action") not in ("block", "reblock") or "title" not in e:
            continue
        nome = e["title"].split(":", 1)[1]
        por_conta.setdefault(nome, []).append(e)

    linhas = []
    for n in novatos:
        criada = data(n["criada_em"])
        dentro = sorted(
            (
                e
                for e in por_conta.get(n["usuario"], [])
                if criada <= data(e["timestamp"]) <= criada + JANELA
            ),
            key=lambda e: e["timestamp"],
        )
        b = dentro[0] if dentro else None
        params = b.get("params", {}) if b else {}
        duracao = params.get("duration", "")
        linhas.append(
            {
                "id_usuario": n["id_usuario"],
                "usuario": n["usuario"],
                "bloqueada_30d": int(b is not None),
                "horas_ate_bloqueio": round(
                    (data(b["timestamp"]) - criada).total_seconds() / 3600, 2
                )
                if b
                else "",
                "duracao": duracao,
                "indefinido": int(duracao in ("infinite", "infinity", "indefinite"))
                if b
                else "",
                "parcial": int(params.get("sitewide") is False) if b else "",
                "bloqueador": b.get("user", "") if b else "",
                "motivo": b.get("comment", "") if b else "",
            }
        )
    with ARQUIVO_SAIDA.open("w", newline="", encoding="utf-8") as f:
        escritor = csv.DictWriter(f, fieldnames=list(linhas[0]))
        escritor.writeheader()
        escritor.writerows(linhas)
    return linhas


def resumir(eventos, linhas):
    total = len(linhas)
    bloqueados = [l for l in linhas if l["bloqueada_30d"]]

    def pct(k, base):
        return f"{k} ({100 * k / base:.1f}%)" if base else str(k)

    print("\nResumo (guarde para a metodologia):")
    print(
        f"  eventos no registro de bloqueios ({INICIO[:10]} a {FIM[:10]}): {len(eventos)}"
    )
    print(f"  novatos: {total}")
    print(f"  BLOQUEADOS ATÉ 30 DIAS DEPOIS DA CRIAÇÃO: {pct(len(bloqueados), total)}")
    if bloqueados:
        print(
            f"    na primeira semana: {pct(sum(l['horas_ate_bloqueio'] <= 168 for l in bloqueados), len(bloqueados))}"
        )
        print(
            f"    por tempo indefinido: {pct(sum(l['indefinido'] for l in bloqueados), len(bloqueados))}"
        )
        print(
            f"    bloqueio parcial: {pct(sum(l['parcial'] for l in bloqueados), len(bloqueados))}"
        )
        print("  motivos mais comuns:")
        for motivo, k in Counter(l["motivo"][:70] for l in bloqueados).most_common(8):
            print(f"    {k:>4}  {motivo or '(sem motivo)'}")
    if ARQUIVO_REVERSOES.exists():
        situacao = {r["id_usuario"]: r["situacao"] for r in ler(ARQUIVO_REVERSOES)}
        print("  bloqueados por situação da primeira edição:")
        for s in ("revertida", "nao_revertida"):
            grupo = [l for l in linhas if situacao.get(l["id_usuario"]) == s]
            print(f"    {s}: {pct(sum(l['bloqueada_30d'] for l in grupo), len(grupo))}")
    print(f"  arquivo salvo: {ARQUIVO_SAIDA.relative_to(RAIZ)}")
    print("  Obs.: bloqueios globais (Meta-Wiki) não estão no registro local.")


if __name__ == "__main__":
    novatos = ler(ARQUIVO_NOVATOS, lambda n: n["incluir_final"] == "1")
    print("Baixando o registro de bloqueios do período...")
    eventos = baixar_registro()
    resumir(eventos, montar(novatos, eventos))
