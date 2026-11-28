"""Valida a base e prepara a amostra para a codificação qualitativa."""

from pathlib import Path
from urllib.parse import quote

import pandas as pd

RAIZ = Path(__file__).resolve().parent.parent
DADOS = RAIZ / "dados"
ARQUIVO_BASE = DADOS / "base.csv"
ARQUIVO_MENSAGENS = DADOS / "mensagens.csv"
ARQUIVO_AUDITORIA = DADOS / "auditoria_classificacao_mensagens.csv"
ARQUIVOS_PILOTO = {
    1: DADOS / "piloto_codificador_1.csv",
    2: DADOS / "piloto_codificador_2.csv",
}
ARQUIVO_REVERSOES = DADOS / "reversoes.csv"
ARQUIVO_EDICOES = DADOS / "edicoes.csv"
ARQUIVO_SAIDA = DADOS / "subamostra_codificacao.csv"
SEMENTE = 42
TAMANHO_POR_GRUPO = 100
TAMANHO_PILOTO = 30


def exigir_colunas(tabela, colunas, arquivo):
    faltantes = sorted(set(colunas) - set(tabela.columns))
    if faltantes:
        raise ValueError(f"{arquivo.name}: faltam colunas obrigatórias: {faltantes}")


def proteger_codificacao_existente(caminho, colunas_manuais):
    if not caminho.exists():
        return
    existente = pd.read_csv(caminho, dtype="string", keep_default_na=False)
    preenchidas = [
        coluna
        for coluna in colunas_manuais
        if coluna in existente
        and existente[coluna].str.strip().ne("").any()
    ]
    if preenchidas:
        raise FileExistsError(
            f"{caminho.relative_to(RAIZ)} contém codificação manual "
            f"({', '.join(preenchidas)}); não será sobrescrito."
        )


def link_diferenca(revid):
    if pd.isna(revid) or not str(revid).strip():
        return ""
    return f"https://pt.wikipedia.org/w/index.php?diff={int(float(revid))}"


def link_discussao(usuario):
    titulo = quote(f"Usuário Discussão:{usuario}".replace(" ", "_"), safe=":")
    return (
        "https://pt.wikipedia.org/w/index.php?"
        f"title={titulo}&action=history"
    )


def link_historico_artigo(titulo):
    if pd.isna(titulo) or not str(titulo).strip():
        return ""
    pagina = quote(str(titulo).replace(" ", "_"), safe=":")
    return (
        "https://pt.wikipedia.org/w/index.php?"
        f"title={pagina}&action=history"
    )


def carregar_e_validar():
    base = pd.read_csv(ARQUIVO_BASE, dtype={"id_usuario": "string"})
    mensagens = pd.read_csv(ARQUIVO_MENSAGENS, dtype={"id_usuario": "string"})
    reversoes = pd.read_csv(ARQUIVO_REVERSOES, dtype={"id_usuario": "string"})
    edicoes = pd.read_csv(ARQUIVO_EDICOES, dtype={"id_usuario": "string"})

    exigir_colunas(
        base,
        [
            "id_usuario",
            "usuario",
            "criada_em",
            "primeira_revid",
            "primeira_timestamp",
            "primeira_titulo",
            "situacao_reversao",
            "comparavel",
            "revertida",
            "recepcao_semana",
            "na_analise_permanencia",
            "permaneceu",
        ],
        ARQUIVO_BASE,
    )
    exigir_colunas(
        mensagens,
        ["id_usuario", "revid", "tipo", "desfeita", "timestamp"],
        ARQUIVO_MENSAGENS,
    )
    exigir_colunas(
        reversoes,
        ["id_usuario", "revertor", "sumario_reversao"],
        ARQUIVO_REVERSOES,
    )
    exigir_colunas(
        edicoes,
        ["id_usuario", "revid", "sumario", "pagina_nova"],
        ARQUIVO_EDICOES,
    )

    for tabela, nome in [
        (base, "base"),
        (reversoes, "reversoes"),
    ]:
        if tabela["id_usuario"].duplicated().any():
            raise ValueError(f"Há id_usuario duplicado em {nome}.")
    if base["usuario"].isna().any() or base["primeira_revid"].isna().any():
        raise ValueError("A base contém novatos sem usuário ou primeira revisão.")

    base["criada_em"] = pd.to_datetime(base["criada_em"], utc=True, errors="raise")
    base["primeira_timestamp"] = pd.to_datetime(
        base["primeira_timestamp"], utc=True, errors="raise"
    )
    if (base["primeira_timestamp"] < base["criada_em"]).any():
        raise ValueError("Há primeira edição anterior à criação da conta.")

    elegiveis = base[base["na_analise_permanencia"].eq(1)].copy()
    comparaveis = elegiveis[elegiveis["comparavel"].eq(1)].copy()
    if set(comparaveis["revertida"].dropna().unique()) != {0, 1}:
        raise ValueError("A análise comparável não contém os dois grupos de reversão.")
    if comparaveis["revertida"].isna().any():
        raise ValueError("Há situação comparável sem indicador de reversão.")
    return base, elegiveis, comparaveis, mensagens, reversoes, edicoes


def montar_amostra(comparaveis, mensagens, reversoes, edicoes):
    colunas_manuais = [
        f"{atributo}_codificador_{codificador}"
        for atributo in ("boa_fe", "explicacao_reversao", "tom_mensagem")
        for codificador in range(1, 5)
    ]
    proteger_codificacao_existente(ARQUIVO_SAIDA, colunas_manuais)
    proteger_codificacao_existente(
        ARQUIVO_AUDITORIA,
        ["classificacao_manual", "observacao_auditoria"],
    )
    for caminho in ARQUIVOS_PILOTO.values():
        proteger_codificacao_existente(
            caminho, ["boa_fe", "explicacao_reversao", "tom_mensagem"]
        )

    amostras = []
    for revertida in (1, 0):
        grupo = comparaveis[comparaveis["revertida"].eq(revertida)]
        if len(grupo) < TAMANHO_POR_GRUPO:
            raise ValueError(
                f"Grupo revertida={revertida} tem {len(grupo)} casos; "
                f"são necessários {TAMANHO_POR_GRUPO}."
            )
        amostras.append(
            grupo.sample(n=TAMANHO_POR_GRUPO, random_state=SEMENTE)
        )
    amostra = pd.concat(amostras, ignore_index=True).sample(
        frac=1, random_state=SEMENTE
    )
    amostra = amostra.reset_index(drop=True)
    amostra.insert(0, "codigo_amostra", [f"PTW-{i:03d}" for i in range(1, 201)])

    piloto_ids = set(
        amostra.sample(n=TAMANHO_PILOTO, random_state=SEMENTE)["id_usuario"]
    )
    amostra["piloto_duplo"] = amostra["id_usuario"].isin(piloto_ids).astype(int)
    restantes = amostra[amostra["piloto_duplo"].eq(0)].sample(
        frac=1, random_state=SEMENTE
    )
    responsaveis = {
        row.id_usuario: f"codificador_{i % 4 + 1}"
        for i, row in enumerate(restantes.itertuples(index=False))
    }
    amostra["codificador_responsavel"] = amostra.apply(
        lambda row: (
            "codificador_1+codificador_2"
            if row["piloto_duplo"]
            else responsaveis[row["id_usuario"]]
        ),
        axis=1,
    )

    edicoes = edicoes.copy()
    edicoes["revid"] = edicoes["revid"].astype("string")
    primeiras = edicoes.drop_duplicates("revid").set_index("revid")
    reversoes = reversoes.set_index("id_usuario")
    amostra["primeira_revid"] = amostra["primeira_revid"].astype("string")
    amostra["link_primeira_edicao"] = amostra["primeira_revid"].map(link_diferenca)
    amostra["link_historico_artigo"] = amostra["primeira_titulo"].map(
        link_historico_artigo
    )
    amostra["primeiro_sumario"] = amostra["primeira_revid"].map(
        primeiras["sumario"]
    )
    amostra["pagina_nova"] = amostra["primeira_revid"].map(
        primeiras["pagina_nova"]
    )
    amostra["revertor"] = amostra["id_usuario"].map(reversoes["revertor"])
    amostra["sumario_reversao"] = amostra["id_usuario"].map(
        reversoes["sumario_reversao"]
    )
    amostra["link_pagina_discussao"] = amostra["usuario"].map(link_discussao)

    humanas_validas = mensagens[
        ~mensagens["tipo"].isin(["boas_vindas_automatica", "manutencao"])
        & mensagens["desfeita"].eq(0)
    ].copy()
    humanas_validas["id_usuario"] = humanas_validas["id_usuario"].astype("string")
    humanas_validas["link"] = humanas_validas["revid"].map(link_diferenca)
    links_por_novato = humanas_validas.groupby("id_usuario")["link"].agg(
        lambda links: " | ".join(links)
    )
    amostra["links_mensagens_semana"] = (
        amostra["id_usuario"].map(links_por_novato).fillna("")
    )

    for atributo in ("boa_fe", "explicacao_reversao", "tom_mensagem"):
        for codificador in range(1, 5):
            amostra[f"{atributo}_codificador_{codificador}"] = ""

    colunas = [
        "codigo_amostra",
        "id_usuario",
        "usuario",
        "situacao_reversao",
        "recepcao_semana",
        "primeira_revid",
        "link_primeira_edicao",
        "link_historico_artigo",
        "primeiro_sumario",
        "pagina_nova",
        "revertor",
        "sumario_reversao",
        "link_pagina_discussao",
        "links_mensagens_semana",
        "piloto_duplo",
        "codificador_responsavel",
    ]
    colunas += [
        f"{atributo}_codificador_{codificador}"
        for atributo in ("boa_fe", "explicacao_reversao", "tom_mensagem")
        for codificador in range(1, 5)
    ]
    amostra[colunas].to_csv(ARQUIVO_SAIDA, index=False, encoding="utf-8")
    return amostra


def preparar_pilotos(amostra):
    colunas = [
        "codigo_amostra",
        "situacao_reversao",
        "recepcao_semana",
        "link_primeira_edicao",
        "link_historico_artigo",
        "primeiro_sumario",
        "revertor",
        "sumario_reversao",
        "link_pagina_discussao",
        "links_mensagens_semana",
        "boa_fe",
        "explicacao_reversao",
        "tom_mensagem",
    ]
    piloto = amostra[amostra["piloto_duplo"].eq(1)].copy()
    for codificador, caminho in ARQUIVOS_PILOTO.items():
        piloto[colunas].to_csv(caminho, index=False, encoding="utf-8")
    return piloto


def preparar_auditoria_mensagens(mensagens):
    validas = mensagens[
        ~mensagens["tipo"].isin(["boas_vindas_automatica", "manutencao"])
    ].copy()
    amostra = validas.sample(
        n=min(50, len(validas)), random_state=SEMENTE
    ).copy()
    amostra["revid"] = amostra["revid"].astype("string")
    amostra["link_revisao"] = amostra["revid"].map(link_diferenca)
    amostra["classificacao_manual"] = ""
    amostra["observacao_auditoria"] = ""
    colunas = [
        "id_usuario",
        "usuario",
        "revid",
        "timestamp",
        "tipo",
        "desfeita",
        "sumario",
        "link_revisao",
        "classificacao_manual",
        "observacao_auditoria",
    ]
    amostra[colunas].to_csv(
        ARQUIVO_AUDITORIA, index=False, encoding="utf-8"
    )
    return amostra


def main():
    base, elegiveis, comparaveis, mensagens, reversoes, edicoes = (
        carregar_e_validar()
    )
    amostra = montar_amostra(comparaveis, mensagens, reversoes, edicoes)
    piloto = preparar_pilotos(amostra)
    auditoria = preparar_auditoria_mensagens(mensagens)
    por_reversao = amostra["revertida"].value_counts().to_dict()
    if por_reversao != {0: TAMANHO_POR_GRUPO, 1: TAMANHO_POR_GRUPO}:
        raise AssertionError(f"A amostra não ficou balanceada: {por_reversao}")

    print("Validação da base e preparação da codificação concluídas.")
    print(f"  Novatos na base: {len(base)}")
    print(f"  Elegíveis para permanência: {len(elegiveis)}")
    print(f"  Elegíveis com primeira edição comparável: {len(comparaveis)}")
    print(
        f"  Amostra: {len(amostra)} ({TAMANHO_POR_GRUPO} revertidas e "
        f"{TAMANHO_POR_GRUPO} não revertidas)"
    )
    print(f"  Piloto duplo: {int(amostra['piloto_duplo'].sum())} casos")
    print(f"  Arquivo para codificação: {ARQUIVO_SAIDA.relative_to(RAIZ)}")
    print(
        f"  Auditoria manual de mensagens: {len(auditoria)} linhas em "
        f"{ARQUIVO_AUDITORIA.relative_to(RAIZ)}"
    )
    print(
        f"  Pilotos independentes: {len(piloto)} casos em "
        f"{ARQUIVOS_PILOTO[1].relative_to(RAIZ)} e "
        f"{ARQUIVOS_PILOTO[2].relative_to(RAIZ)}"
    )


if __name__ == "__main__":
    main()
