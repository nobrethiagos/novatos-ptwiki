"""
Acesso à API da Wikipédia em português, seguindo a política de User-Agent da Wikimedia.
Utilizado nos outros scripts:
    from wiki_api import consultar, consultar_tudo
"""

import time

import requests

API_URL = "https://pt.wikipedia.org/w/api.php"

CONTATO = "thiagosn811@gmail.com"
USER_AGENT = f"NovatosPtWiki/0.1 ({CONTATO}) python-requests/{requests.__version__}"

# Uma sessão reaproveita a conexão e manda o User-Agent em todas as chamadas.
sessao = requests.Session()
sessao.headers.update({"User-Agent": USER_AGENT})


def _espera(resp, padrao=5.0):
    try:
        return float(resp.headers.get("Retry-After", padrao))
    except ValueError:
        return padrao


def consultar(params, pausa=1.0, tentativas=5):
    """
    Faz uma chamada à API e devolve o JSON.
    Espera e tenta de novo quando o servidor está sobrecarregado (maxlag, 429 ou 503).
    """
    params = {"format": "json", "formatversion": 2, "maxlag": 5, **params}
    for _ in range(tentativas):
        resp = sessao.get(API_URL, params=params, timeout=60)
        if resp.status_code in (429, 503):
            time.sleep(_espera(resp))
            continue
        resp.raise_for_status()
        dados = resp.json()
        erro = dados.get("error")
        if erro and erro.get("code") == "maxlag":
            time.sleep(_espera(resp))
            continue
        if erro:
            raise RuntimeError(f"Erro da API: {erro}")
        time.sleep(pausa)  # chamadas em série, com pausa, como pede a Wikimedia
        return dados
    raise RuntimeError(
        "O servidor pediu para esperar muitas vezes seguidas; tente mais tarde."
    )


def consultar_tudo(params, pausa=1.0):
    """Segue a paginação da API ('continue') e devolve cada página de resultado."""
    params = dict(params)
    while True:
        dados = consultar(params, pausa=pausa)
        yield dados
        if "continue" not in dados:
            break
        params.update(dados["continue"])


if __name__ == "__main__":
    # Teste rápido: mostra o User-Agent e as estatísticas da Wikipédia em português.
    print("User-Agent:", USER_AGENT)
    r = consultar({"action": "query", "meta": "siteinfo", "siprop": "statistics"})
    print(r["query"]["statistics"])
