"""
Mensagens recebidas na página de discussão na primeira semana.

Entrada:
    dados/novatos.csv (só incluir_final=1)
Saídas:
    dados/brutos/mensagens/<id_usuario>.json  revisões brutas
    dados/mensagens.csv                        uma linha por mensagem de outra conta na semana
    dados/mensagens_por_novato.csv             uma linha por novato, com o tipo de recepção

"""

import csv
import json
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

from wiki_api import consultar_tudo

JANELA = timedelta(days=7)
CONTA_AUTOMATICA = "New user message"
FERRAMENTAS = {"diff-tools", "huggle"}
# Ordem de prioridade: manutenção > bloqueio > aviso > boas-vindas > outra.
# "manutencao" (edições de robô na página) não conta como mensagem.
PALAVRAS = {
    "manutencao": ["bot:"],
    "bloqueio": ["bloque"],
    "aviso": [
        "aviso",
        "advert",
        "vandalismo",
        "eliminação",
        "eliminacao",
        "esr",
        "predefinição:av-",
        "nome impróprio",
        "propaganda",
        "mostrar previsão",
    ],
    "boas_vindas": ["bem-vind", "bem vind", "boas-vindas", "boas vindas"],
}

RAIZ = Path(__file__).resolve().parent.parent
ARQUIVO_NOVATOS = RAIZ / "dados" / "novatos.csv"
PASTA = RAIZ / "dados" / "brutos" / "mensagens"
ARQUIVO_MENSAGENS = RAIZ / "dados" / "mensagens.csv"
ARQUIVO_POR_NOVATO = RAIZ / "dados" / "mensagens_por_novato.csv"


def data(ts):
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def iso(dt):
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def ler_novatos():
    with ARQUIVO_NOVATOS.open(encoding="utf-8") as f:
        return [n for n in csv.DictReader(f) if n["incluir_final"] == "1"]


def baixar(n):
    arquivo = PASTA / f"{n['id_usuario']}.json"
    if arquivo.exists():
        return json.loads(arquivo.read_text(encoding="utf-8"))
    criada = data(n["criada_em"])
    resultado = {"existe": False, "revisoes": []}
    for parte in consultar_tudo(
        {
            "action": "query",
            "prop": "revisions",
            "titles": f"User talk:{n['usuario']}",
            "rvstart": iso(criada),
            "rvend": iso(criada + JANELA),
            "rvdir": "newer",
            "rvlimit": "max",
            "rvprop": "ids|user|timestamp|comment|tags|sha1|size",
        }
    ):
        for p in parte["query"].get("pages", []):
            if not p.get("missing"):
                resultado["existe"] = True
                resultado["revisoes"].extend(p.get("revisions", []))
    arquivo.write_text(json.dumps(resultado, ensure_ascii=False), encoding="utf-8")
    return resultado


def tipo_por_sumario(sumario):
    s = sumario.lower()
    for tipo, palavras in PALAVRAS.items():
        if any(p in s for p in palavras):
            return tipo
    return "outra"


def analisar(n, bruto):
    revs = bruto["revisoes"]
    criada = data(n["criada_em"])
    mensagens = []
    for i, r in enumerate(revs):
        autor = r.get("user", "")
        if autor == n["usuario"]:
            continue  # o próprio novato editando a página
        if r.get("sha1") and any(revs[j].get("sha1") == r["sha1"] for j in range(i)):
            continue  # revisão que só volta a página a um estado anterior: desfaz, não é mensagem
        anterior = revs[i - 1].get("sha1") if i > 0 else None
        desfeita = anterior is not None and any(
            d.get("sha1") == anterior and d.get("user", "") != n["usuario"]
            for d in revs[i + 1 :]
        )
        automatica = autor == CONTA_AUTOMATICA
        etiquetas = r.get("tags", [])
        mensagens.append(
            {
                "id_usuario": n["id_usuario"],
                "usuario": n["usuario"],
                "revid": r["revid"],
                "autor": autor,
                "timestamp": r["timestamp"],
                "horas_desde_criacao": round(
                    (data(r["timestamp"]) - criada).total_seconds() / 3600, 2
                ),
                "tipo": "boas_vindas_automatica"
                if automatica
                else tipo_por_sumario(r.get("comment", "")),
                "desfeita": int(desfeita),
                "via_ferramenta": int(bool(FERRAMENTAS & set(etiquetas))),
                "etiquetas": ";".join(etiquetas),
                "sumario": r.get("comment", ""),
            }
        )

    validas = [
        m
        for m in mensagens
        if not m["desfeita"]
        and m["tipo"] not in ("boas_vindas_automatica", "manutencao")
    ]
    conta = Counter(m["tipo"] for m in validas)
    tem_bv = conta["boas_vindas"] > 0
    tem_aviso = conta["aviso"] + conta["bloqueio"] > 0
    if tem_bv and tem_aviso:
        semana = "ambas"
    elif tem_aviso:
        semana = "aviso"
    elif tem_bv:
        semana = "boas_vindas"
    elif conta["outra"]:
        semana = "outra"
    else:
        semana = "nenhuma"
    resumo = {
        "id_usuario": n["id_usuario"],
        "usuario": n["usuario"],
        "pagina_existe": int(bruto["existe"]),
        "boas_vindas_automatica": int(
            any(m["tipo"] == "boas_vindas_automatica" for m in mensagens)
        ),
        "n_boas_vindas": conta["boas_vindas"],
        "n_avisos": conta["aviso"],
        "n_bloqueio": conta["bloqueio"],
        "n_outras": conta["outra"],
        "n_desfeitas": sum(m["desfeita"] for m in mensagens),
        "avisos_via_ferramenta": sum(
            m["via_ferramenta"] for m in validas if m["tipo"] in ("aviso", "bloqueio")
        ),
        "horas_primeira_msg_humana": min(
            (m["horas_desde_criacao"] for m in validas), default=""
        ),
        "recepcao_semana": semana,
    }
    return mensagens, resumo


def salvar(caminho, linhas, campos):
    with caminho.open("w", newline="", encoding="utf-8") as f:
        escritor = csv.DictWriter(f, fieldnames=campos)
        escritor.writeheader()
        escritor.writerows(linhas)


def resumir(mensagens, resumos):
    total = len(resumos)

    def pct(k, base):
        return f"{k} ({100 * k / base:.1f}%)" if base else str(k)

    humanas = [m for m in mensagens if m["tipo"] != "boas_vindas_automatica"]
    print("\nResumo (guarde para a metodologia):")
    print(f"  novatos: {total}")
    print(
        f"  com página de discussão na primeira semana: {pct(sum(r['pagina_existe'] for r in resumos), total)}"
    )
    print(
        f"  receberam boas-vindas automáticas: {pct(sum(r['boas_vindas_automatica'] for r in resumos), total)}"
    )
    print(f"  mensagens de outras pessoas na semana: {len(humanas)}")
    for tipo, k in Counter(m["tipo"] for m in humanas).most_common():
        print(f"    {tipo}: {k}")
    print(f"    desfeitas (não contam): {sum(m['desfeita'] for m in humanas)}")
    print(
        "  RECEPÇÃO NA PRIMEIRA SEMANA (só mensagens humanas válidas; bloqueio conta como aviso):"
    )
    for tipo, k in Counter(r["recepcao_semana"] for r in resumos).most_common():
        print(f"    {tipo}: {pct(k, total)}")
    avisos = [
        m for m in humanas if m["tipo"] in ("aviso", "bloqueio") and not m["desfeita"]
    ]
    print(
        f"  avisos enviados com ferramenta: {pct(sum(m['via_ferramenta'] for m in avisos), len(avisos))}"
    )
    print("  sumários mais comuns classificados como 'outra' (para ajustar PALAVRAS):")
    for sumario, k in Counter(
        m["sumario"][:80] for m in humanas if m["tipo"] == "outra"
    ).most_common(12):
        print(f"    {k:>4}  {sumario or '(sem sumário)'}")
    print(
        f"  arquivos salvos: {ARQUIVO_MENSAGENS.relative_to(RAIZ)}, {ARQUIVO_POR_NOVATO.relative_to(RAIZ)}"
    )


if __name__ == "__main__":
    novatos = ler_novatos()
    PASTA.mkdir(parents=True, exist_ok=True)
    print(
        f"Baixando a página de discussão de {len(novatos)} novatos (7 dias após a criação)..."
    )
    mensagens, resumos = [], []
    for i, n in enumerate(novatos, start=1):
        m, r = analisar(n, baixar(n))
        mensagens.extend(m)
        resumos.append(r)
        if i % 100 == 0 or i == len(novatos):
            print(f"  {i} de {len(novatos)} novatos")
    campos_m = [
        "id_usuario",
        "usuario",
        "revid",
        "autor",
        "timestamp",
        "horas_desde_criacao",
        "tipo",
        "desfeita",
        "via_ferramenta",
        "etiquetas",
        "sumario",
    ]
    salvar(ARQUIVO_MENSAGENS, mensagens, campos_m)
    salvar(ARQUIVO_POR_NOVATO, resumos, list(resumos[0]))
    resumir(mensagens, resumos)
