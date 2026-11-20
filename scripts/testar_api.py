"""
Testa, em pequena escala, cada chamada da API usada na coleta.
O script só lê dados públicos.
"""

import argparse
from datetime import datetime, timedelta

from wiki_api import consultar

INICIO = "2025-03-01T00:00:00Z"
FIM = "2025-03-31T23:59:59Z"


def data(ts):
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def titulo(texto):
    print(f"\n=== {texto}")


def teste_coorte():
    titulo("1. Coorte: contas criadas no período (list=logevents, newusers)")
    r = consultar(
        {
            "action": "query",
            "list": "logevents",
            "letype": "newusers",
            "lestart": INICIO,
            "leend": FIM,
            "ledir": "newer",
            "lelimit": 50,
        }
    )
    eventos = r["query"]["logevents"]
    for e in eventos[:5]:
        print(f"  {e['timestamp']}  {e['action']:<10} {e['title']}")
    acoes = {e["action"] for e in eventos}
    print(f"  {len(eventos)} eventos nesta página; ações vistas: {sorted(acoes)}")
    # O título vem como "Usuário(a):Nome"; tira o prefixo do domínio.
    return [e["title"].split(":", 1)[1] for e in eventos if e["action"] != "autocreate"]


def teste_usuarios(nomes):
    titulo("2. Filtro: edições e grupos (list=users)")
    r = consultar(
        {
            "action": "query",
            "list": "users",
            "ususers": "|".join(nomes[:50]),
            "usprop": "editcount|groups|registration",
        }
    )
    usuarios = [u for u in r["query"]["users"] if not u.get("missing")]
    com_edicao = [
        u
        for u in usuarios
        if u.get("editcount", 0) > 0 and "bot" not in u.get("groups", [])
    ]
    print(
        f"  {len(usuarios)} contas consultadas; {len(com_edicao)} com pelo menos uma edição e sem grupo bot"
    )
    for u in com_edicao[:3]:
        print(
            f"  {u['name']}: {u['editcount']} edições, registrada em {u.get('registration')}"
        )
    return com_edicao


def teste_contribuicoes(nome):
    titulo(f"3. Edições de {nome} (list=usercontribs)")
    r = consultar(
        {
            "action": "query",
            "list": "usercontribs",
            "ucuser": nome,
            "ucprop": "ids|title|timestamp|comment|size|sizediff|tags",
            "ucdir": "newer",
            "uclimit": 20,
        }
    )
    contribs = r["query"]["usercontribs"]
    for c in contribs[:5]:
        print(
            f"  {c['timestamp']}  ns={c['ns']}  {c['title']}  ({c.get('sizediff', 0):+})  tags={c.get('tags', [])}"
        )
    print(f"  {len(contribs)} edições visíveis nesta página")
    artigos = [c for c in contribs if c["ns"] == 0]
    return artigos[0] if artigos else None


def teste_reversao(edicao):
    titulo(
        f"4. Reversão da primeira edição em artigo: {edicao['title']} (prop=revisions)"
    )
    r = consultar(
        {
            "action": "query",
            "prop": "revisions",
            "titles": edicao["title"],
            "rvstartid": edicao["revid"],
            "rvdir": "newer",
            "rvlimit": 20,
            "rvprop": "ids|sha1|user|timestamp|comment|tags",
        }
    )
    revisoes = r["query"]["pages"][0].get("revisions", [])
    if edicao["parentid"] == 0:
        print(
            "  A edição criou a página: não há revisão anterior para comparar por SHA1."
        )
        return
    anterior = consultar(
        {
            "action": "query",
            "prop": "revisions",
            "revids": edicao["parentid"],
            "rvprop": "ids|sha1",
        }
    )["query"]["pages"][0]["revisions"][0]
    limite = data(edicao["timestamp"]) + timedelta(hours=48)
    autor = revisoes[0]["user"] if revisoes else None
    revertida = None
    for rev in revisoes[1:]:
        if data(rev["timestamp"]) > limite:
            break
        if rev.get("sha1") == anterior.get("sha1") and rev.get("user") != autor:
            revertida = rev
            break
    print(
        f"  {len(revisoes)} revisões a partir da edição; SHA1 anterior: {anterior.get('sha1')}"
    )
    if revertida:
        print(
            f"  REVERTIDA por {revertida['user']} em {revertida['timestamp']}: {revertida.get('comment', '')}"
        )
        print(f"  tags da reversão: {revertida.get('tags', [])}")
    else:
        print("  Não revertida em 48 horas.")


def teste_mensagens(nome, registro):
    titulo(f"5. Mensagens na página de discussão de {nome} (prop=revisions)")
    r = consultar(
        {
            "action": "query",
            "prop": "revisions",
            "titles": f"User talk:{nome}",
            "rvdir": "newer",
            "rvlimit": 20,
            "rvprop": "user|timestamp|comment",
        }
    )
    pagina = r["query"]["pages"][0]
    if pagina.get("missing"):
        print("  A página de discussão não existe: nenhuma mensagem.")
        return
    limite = data(registro) + timedelta(days=7) if registro else None
    for rev in pagina.get("revisions", [])[:5]:
        na_janela = limite is None or data(rev["timestamp"]) <= limite
        marca = "dentro de 7 dias" if na_janela else "depois de 7 dias"
        print(
            f"  {rev['timestamp']}  {rev['user']}  [{marca}]  {rev.get('comment', '')}"
        )


def teste_bloqueios(nome):
    titulo(f"6. Bloqueios de {nome} (list=logevents, block)")
    r = consultar(
        {
            "action": "query",
            "list": "logevents",
            "letype": "block",
            "letitle": f"User:{nome}",
            "lelimit": 10,
        }
    )
    eventos = r["query"]["logevents"]
    print(
        f"  {len(eventos)} registros de bloqueio" if eventos else "  Nenhum bloqueio."
    )


def rodar(nome_escolhido=None):
    passos = []
    try:
        nomes = [nome_escolhido] if nome_escolhido else teste_coorte()
        passos.append("coorte")
        usuarios = teste_usuarios(nomes)
        passos.append("usuarios")
        if not usuarios:
            print(
                "\nNenhuma conta com edições nesta amostra; rode de novo com --usuario."
            )
            return
        conta = usuarios[0]
        edicao = teste_contribuicoes(conta["name"])
        passos.append("contribuicoes")
        if edicao:
            teste_reversao(edicao)
            passos.append("reversao")
        else:
            print(
                "  Sem edição em artigo nesta página; o teste de reversão foi pulado."
            )
        teste_mensagens(conta["name"], conta.get("registration"))
        passos.append("mensagens")
        teste_bloqueios(conta["name"])
        passos.append("bloqueios")
    finally:
        print(f"\nPassos concluídos: {', '.join(passos) or 'nenhum'}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--usuario", help="nome de uma conta para testar")
    rodar(parser.parse_args().usuario)
