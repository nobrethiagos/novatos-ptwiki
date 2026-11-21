"""
Monta a base final: uma linha por novato.

Entradas (geradas na etapa 2):
    dados/novatos.csv               primeira edição e contagens (só incluir_final=1)
    dados/edicoes.csv               edições visíveis de cada conta
    dados/reversoes.csv             situação da primeira edição e quem reverteu
    dados/mensagens_por_novato.csv  recepção na primeira semana
    dados/bloqueios.csv             bloqueios até 30 dias depois da criação
Saída:
    dados/base.csv
"""

from pathlib import Path

import pandas as pd

RAIZ = Path(__file__).resolve().parent.parent
DADOS = RAIZ / "dados"
SAIDA = DADOS / "base.csv"

# Permanência: pelo menos uma edição entre o 31º e o 90º dia depois da criação, inclusive.
# O 1º dia são as primeiras 24 horas; o 31º começa 30 dias depois da criação e o 90º termina 90 dias depois.
INICIO_JANELA = pd.Timedelta(days=30)
FIM_JANELA = pd.Timedelta(days=90)
PRIMEIRAS_24H = pd.Timedelta(hours=24)
# Na análise da permanência entram só novatos cuja primeira edição em artigo foi feita até 7 dias
# depois da criação. Assim a primeira experiência (edição, reversão e mensagens da semana) acontece
# antes da janela de permanência, e a própria primeira edição não conta como "permanecer".
LIMITE_PRIMEIRA_EDICAO = pd.Timedelta(days=7)
COMPARAVEIS = {"revertida", "nao_revertida"}


def ler(nome):
    return pd.read_csv(
        DADOS / nome, dtype={"id_usuario": "int64"}, keep_default_na=True
    )


def main():
    novatos = ler("novatos.csv")
    novatos = novatos[novatos["incluir_final"] == 1].copy()
    edicoes = ler("edicoes.csv")
    reversoes = ler("reversoes.csv")
    mensagens = ler("mensagens_por_novato.csv")
    bloqueios = ler("bloqueios.csv")

    for nome, tabela in [
        ("novatos", novatos),
        ("reversoes", reversoes),
        ("mensagens", mensagens),
        ("bloqueios", bloqueios),
    ]:
        assert tabela["id_usuario"].is_unique, f"id_usuario repetido em {nome}"

    novatos["criada_em"] = pd.to_datetime(novatos["criada_em"], utc=True)
    novatos["primeira_timestamp"] = pd.to_datetime(
        novatos["primeira_timestamp"], utc=True
    )
    edicoes["timestamp"] = pd.to_datetime(edicoes["timestamp"], utc=True)

    # Atividade a partir das edições visíveis (qualquer página).
    ed = edicoes.merge(
        novatos[["id_usuario", "criada_em"]], on="id_usuario", how="inner"
    )
    desde = ed["timestamp"] - ed["criada_em"]
    ed["em_24h"] = desde < PRIMEIRAS_24H
    ed["na_janela"] = (desde >= INICIO_JANELA) & (desde < FIM_JANELA)
    atividade = (
        ed.groupby("id_usuario")
        .agg(
            edicoes_visiveis_coletadas=("revid", "size"),
            edicoes_24h=("em_24h", "sum"),
            edicoes_dia31_90=("na_janela", "sum"),
        )
        .reset_index()
    )

    base = novatos[
        [
            "id_usuario",
            "usuario",
            "criada_em",
            "primeira_revid",
            "primeira_titulo",
            "primeira_timestamp",
            "primeira_pagina_nova",
            "edicoes_apagadas_estimadas",
        ]
    ].rename(columns={"primeira_pagina_nova": "artigo_novo"})
    base["artigo_novo"] = base["artigo_novo"].astype(int)
    base["semana_criacao"] = (base["criada_em"].dt.day - 1) // 7 + 1
    base["primeira_edicao_7d"] = (
        base["primeira_timestamp"] - base["criada_em"] <= LIMITE_PRIMEIRA_EDICAO
    ).astype(int)
    base["horas_ate_primeira_edicao"] = (
        (base["primeira_timestamp"] - base["criada_em"]).dt.total_seconds() / 3600
    ).round(2)
    base["tem_edicoes_apagadas"] = (base["edicoes_apagadas_estimadas"] > 0).astype(int)

    base = base.merge(atividade, on="id_usuario", how="left")

    rev = reversoes[
        [
            "id_usuario",
            "situacao",
            "segundos_ate_reversao",
            "tipo_revertor",
            "revertor_edicoes",
            "etiqueta_mw_reverted",
        ]
    ].rename(columns={"situacao": "situacao_reversao"})
    base = base.merge(rev, on="id_usuario", how="left", validate="one_to_one")
    base["comparavel"] = base["situacao_reversao"].isin(COMPARAVEIS).astype(int)
    base["revertida"] = (
        base["situacao_reversao"]
        .map({"revertida": 1, "nao_revertida": 0})
        .astype("Int64")
    )
    base["minutos_ate_reversao"] = (base["segundos_ate_reversao"] / 60).round(1)
    base = base.drop(columns="segundos_ate_reversao")

    msg = mensagens[
        [
            "id_usuario",
            "recepcao_semana",
            "n_avisos",
            "n_bloqueio",
            "avisos_via_ferramenta",
            "horas_primeira_msg_humana",
        ]
    ]
    base = base.merge(msg, on="id_usuario", how="left", validate="one_to_one")
    base["recebeu_aviso"] = (base["recepcao_semana"] == "aviso").astype(int)
    base["aviso_via_ferramenta"] = (base["avisos_via_ferramenta"].fillna(0) > 0).astype(
        int
    )
    base = base.drop(columns="avisos_via_ferramenta")

    blq = bloqueios[
        ["id_usuario", "bloqueada_30d", "horas_ate_bloqueio", "indefinido"]
    ].rename(columns={"indefinido": "bloqueio_indefinido"})
    base = base.merge(blq, on="id_usuario", how="left", validate="one_to_one")
    base["bloqueio_indefinido"] = base["bloqueio_indefinido"].fillna(0).astype(int)

    base["permaneceu"] = (base["edicoes_dia31_90"] > 0).astype(int)
    base["na_analise_permanencia"] = (
        (base["bloqueada_30d"] == 0) & (base["primeira_edicao_7d"] == 1)
    ).astype(int)

    # Colunas da codificação manual (etapa 4).
    for coluna in ["boa_fe", "explicacao_reversao", "tom_mensagem"]:
        base[coluna] = pd.NA

    # Checagens: nada pode ter se perdido nas junções.
    assert len(base) == len(novatos), "o número de novatos mudou nas junções"
    for coluna in [
        "edicoes_visiveis_coletadas",
        "situacao_reversao",
        "recepcao_semana",
        "bloqueada_30d",
    ]:
        faltando = base[coluna].isna().sum()
        assert faltando == 0, f"{faltando} novatos sem {coluna}"
    assert (base["primeira_timestamp"] >= base["criada_em"]).all(), (
        "primeira edição antes da criação da conta"
    )

    for coluna in ["criada_em", "primeira_timestamp"]:
        base[coluna] = base[coluna].dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    base.to_csv(SAIDA, index=False)

    # Resumo
    analise = base[base["na_analise_permanencia"] == 1]
    comp = analise[analise["comparavel"] == 1]

    def taxa(df):
        return f"{df['permaneceu'].mean():.1%} de {len(df)}" if len(df) else "sem casos"

    print("Resumo (guarde para a metodologia):")
    print(f"  novatos na base: {len(base)}")
    bloqueados = base["bloqueada_30d"] == 1
    tardios = (base["primeira_edicao_7d"] == 0) & ~bloqueados
    print("  fora da análise de permanência:")
    print(f"    bloqueados até 30 dias: {int(bloqueados.sum())}")
    print(
        f"    não bloqueados, com a primeira edição em artigo depois de 7 dias: {int(tardios.sum())}"
    )
    print(
        f"  na análise de permanência: {len(analise)}; com primeira edição comparável: {len(comp)}"
    )
    print(f"  permaneceram (todos os novatos): {taxa(base)}")
    print(f"  permaneceram (na análise): {taxa(analise)}")
    print("Prévia descritiva, sem testes (os testes ficam para a etapa 5):")
    print(f"  primeira edição revertida:     {taxa(comp[comp['revertida'] == 1])}")
    print(f"  primeira edição não revertida: {taxa(comp[comp['revertida'] == 0])}")
    print(
        f"  recebeu aviso na semana:       {taxa(analise[analise['recebeu_aviso'] == 1])}"
    )
    print(
        f"  não recebeu aviso:             {taxa(analise[analise['recebeu_aviso'] == 0])}"
    )
    print(f"  arquivo salvo: {SAIDA.relative_to(RAIZ)} ({len(base.columns)} colunas)")


if __name__ == "__main__":
    main()
