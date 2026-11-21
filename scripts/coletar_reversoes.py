"""
Detecta se a primeira edição em artigo de cada novato foi revertida em 48 horas.

Entrada:
    dados/novatos.csv (só incluir_final=1)
Saídas:
    dados/brutos/reversoes/...   respostas brutas da API
    dados/reversoes.csv          uma linha por novato: situação, quem reverteu, quando e como
"""

import csv
import json
import statistics
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

from wiki_api import consultar, consultar_tudo

JANELA = timedelta(hours=48)
# Etiquetas de ferramentas semiautomáticas de reversão. Amplie com o que aparecer no resumo.
FERRAMENTAS = {"diff-tools", "huggle"}

RAIZ = Path(__file__).resolve().parent.parent
ARQUIVO_NOVATOS = RAIZ / "dados" / "novatos.csv"
PASTA = RAIZ / "dados" / "brutos" / "reversoes"
ARQUIVO_SAIDA = RAIZ / "dados" / "reversoes.csv"


def data(ts):
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def iso(dt):
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def em_cache(nome, buscar):
    """Lê a resposta do disco se já existir; senão busca na API e grava."""
    arquivo = PASTA / nome
    if arquivo.exists():
        return json.loads(arquivo.read_text(encoding="utf-8"))
    dados = buscar()
    arquivo.parent.mkdir(parents=True, exist_ok=True)
    arquivo.write_text(json.dumps(dados, ensure_ascii=False), encoding="utf-8")
    return dados


def ler_novatos():
    with ARQUIVO_NOVATOS.open(encoding="utf-8") as f:
        return [n for n in csv.DictReader(f) if n["incluir_final"] == "1"]


def buscar_sha1(novatos):
    """Em lotes de 50 revisões: SHA1 da edição do novato e da anterior, e a página atual."""
    revids = []
    for n in novatos:
        revids.append(n["primeira_revid"])
        if n["primeira_parentid"] not in ("", "0"):
            revids.append(n["primeira_parentid"])
    sha1, pagina = {}, {}
    lotes = [revids[i : i + 50] for i in range(0, len(revids), 50)]
    for k, lote in enumerate(lotes, start=1):
        dados = em_cache(
            f"sha1/lote_{k:04d}.json",
            lambda: consultar(
                {
                    "action": "query",
                    "prop": "revisions",
                    "revids": "|".join(lote),
                    "rvprop": "ids|sha1",
                }
            ),
        )
        for p in dados["query"].get("pages", []):
            for r in p.get("revisions", []):
                sha1[str(r["revid"])] = r.get("sha1")
                pagina[str(r["revid"])] = (p["pageid"], p["title"])
    print(f"  SHA1: {len(lotes)} lotes, {len(sha1)} revisões encontradas")
    return sha1, pagina


def revisoes_seguintes(revid, pageid, ts):
    """Revisões da página a partir da edição do novato, até 48 horas depois."""

    def buscar():
        revs = []
        for parte in consultar_tudo(
            {
                "action": "query",
                "prop": "revisions",
                "pageids": pageid,
                "rvstartid": revid,
                "rvend": iso(data(ts) + JANELA),
                "rvdir": "newer",
                "rvlimit": "max",
                "rvprop": "ids|sha1|user|timestamp|comment|tags",
            }
        ):
            for p in parte["query"].get("pages", []):
                revs.extend(p.get("revisions", []))
        return revs

    return em_cache(f"paginas/rev_{revid}.json", buscar)


def classificar(n, sha1, pagina):
    base = {
        "id_usuario": n["id_usuario"],
        "usuario": n["usuario"],
        "primeira_revid": n["primeira_revid"],
        "primeira_timestamp": n["primeira_timestamp"],
        "etiqueta_mw_reverted": int(
            "mw-reverted" in n["primeira_etiquetas"].split(";")
        ),
        "pageid": "",
        "titulo_atual": "",
        "situacao": "",
        "segundos_ate_reversao": "",
        "revertor": "",
        "etiquetas_reversao": "",
        "sumario_reversao": "",
    }
    revid, parent = n["primeira_revid"], n["primeira_parentid"]
    if parent in ("", "0"):
        return {**base, "situacao": "pagina_nova"}
    if revid not in pagina or sha1.get(parent) is None or sha1.get(revid) is None:
        return {**base, "situacao": "indisponivel"}  # revisão oculta ou apagada
    pageid, titulo = pagina[revid]
    base.update(pageid=pageid, titulo_atual=titulo)
    if sha1[revid] == sha1[parent]:
        return {**base, "situacao": "edicao_nula"}  # a edição não mudou o conteúdo

    revs = revisoes_seguintes(revid, pageid, n["primeira_timestamp"])
    for r in revs:
        if str(r["revid"]) == revid:
            continue
        if r.get("sha1") == sha1[parent]:
            if r.get("user") == n["usuario"]:
                return {**base, "situacao": "autorreversao"}
            segundos = (
                data(r["timestamp"]) - data(n["primeira_timestamp"])
            ).total_seconds()
            return {
                **base,
                "situacao": "revertida",
                "segundos_ate_reversao": int(segundos),
                "revertor": r.get("user", ""),
                "etiquetas_reversao": ";".join(r.get("tags", [])),
                "sumario_reversao": r.get("comment", ""),
            }
    return {**base, "situacao": "nao_revertida"}


def info_revertores(nomes):
    info = {}
    nomes = sorted(nomes)
    for k in range(0, len(nomes), 50):
        lote = nomes[k : k + 50]
        dados = em_cache(
            f"revertores/lote_{k // 50 + 1:04d}.json",
            lambda: consultar(
                {
                    "action": "query",
                    "list": "users",
                    "ususers": "|".join(lote),
                    "usprop": "groups|editcount",
                }
            ),
        )
        for u in dados["query"]["users"]:
            info[u["name"]] = u
    return info


def tipo_revertor(linha, info):
    u = info.get(linha["revertor"], {})
    if "bot" in u.get("groups", []):
        return "robo"
    if FERRAMENTAS & set(linha["etiquetas_reversao"].split(";")):
        return "ferramenta"
    return "humano"


def resumir(linhas, etiquetas_reversao):
    situacoes = Counter(l["situacao"] for l in linhas)
    comparaveis = [
        l
        for l in linhas
        if l["situacao"] in ("revertida", "nao_revertida", "autorreversao")
    ]
    revertidas = [l for l in linhas if l["situacao"] == "revertida"]
    tempos = [l["segundos_ate_reversao"] for l in revertidas]

    def pct(n, base):
        return f"{n} ({100 * n / base:.1f}%)" if base else str(n)

    print("\nResumo (guarde para a metodologia):")
    print(f"  novatos analisados: {len(linhas)}")
    for s, k in situacoes.most_common():
        print(f"    {s}: {k}")
    print(
        f"  REVERTIDAS EM 48 h, entre as comparáveis: {pct(len(revertidas), len(comparaveis))}"
    )
    if tempos:
        print(f"    mediana até a reversão: {statistics.median(tempos) / 60:.1f} min")
        print(
            f"    revertidas em até 1 hora: {pct(sum(t <= 3600 for t in tempos), len(tempos))}"
        )
        tipos = Counter(l["tipo_revertor"] for l in revertidas)
        print(
            "    quem reverteu: "
            + ", ".join(
                f"{t} {pct(k, len(revertidas))}" for t, k in tipos.most_common()
            )
        )
    print("  etiquetas mais comuns nas reversões (para ampliar FERRAMENTAS):")
    for etiqueta, k in etiquetas_reversao.most_common(10):
        print(f"    {etiqueta}: {k}")
    sha = {l["primeira_revid"] for l in revertidas}
    tag = {l["primeira_revid"] for l in comparaveis if l["etiqueta_mw_reverted"]}
    print(
        "  concordância SHA1 (48 h) x etiqueta mw-reverted (qualquer prazo), entre as comparáveis:"
    )
    print(
        f"    as duas: {len(sha & tag)}  só SHA1: {len(sha - tag)}  só etiqueta: {len(tag - sha)}  "
        f"nenhuma: {len(comparaveis) - len(sha | tag)}"
    )
    print(f"  arquivo salvo: {ARQUIVO_SAIDA.relative_to(RAIZ)}")


if __name__ == "__main__":
    novatos = ler_novatos()
    print(f"Analisando a primeira edição de {len(novatos)} novatos...")
    sha1, pagina = buscar_sha1(novatos)
    linhas = []
    for i, n in enumerate(novatos, start=1):
        linhas.append(classificar(n, sha1, pagina))
        if i % 100 == 0 or i == len(novatos):
            print(f"  {i} de {len(novatos)} novatos")
    info = info_revertores({l["revertor"] for l in linhas if l["revertor"]})
    etiquetas = Counter()
    for l in linhas:
        if l["situacao"] == "revertida":
            u = info.get(l["revertor"], {})
            l["revertor_edicoes"] = u.get("editcount", "")
            l["revertor_robo"] = int("bot" in u.get("groups", []))
            l["tipo_revertor"] = tipo_revertor(l, info)
            etiquetas.update(t for t in l["etiquetas_reversao"].split(";") if t)
        else:
            l.update(revertor_edicoes="", revertor_robo="", tipo_revertor="")
    with ARQUIVO_SAIDA.open("w", newline="", encoding="utf-8") as f:
        escritor = csv.DictWriter(f, fieldnames=list(linhas[0]))
        escritor.writeheader()
        escritor.writerows(linhas)
    resumir(linhas, etiquetas)
