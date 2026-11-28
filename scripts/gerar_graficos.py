"""Gera gráficos e testes descritivos para as perguntas do projeto."""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
from scipy.stats import chi2_contingency
from statsmodels.formula.api import logit
from statsmodels.stats.proportion import proportion_confint

RAIZ = Path(__file__).resolve().parent.parent
DADOS = RAIZ / "dados"
PASTA_GRAFICOS = RAIZ / "graficos"
ARQUIVO_RESUMO = DADOS / "resultados_quantitativos.csv"
ARQUIVO_TESTES = DADOS / "testes_associacao.csv"
ARQUIVO_MODELOS = DADOS / "modelos_logisticos.csv"
ARQUIVO_QP2 = DADOS / "etapa5_qp2.csv"

plt.rcParams.update(
    {
        "figure.dpi": 120,
        "savefig.dpi": 180,
        "font.size": 10,
        "axes.titlesize": 13,
        "axes.labelsize": 10,
    }
)


def proporcao_com_ic(sucessos, total):
    if total == 0:
        return np.nan, np.nan, np.nan
    inferior, superior = proportion_confint(
        sucessos, total, alpha=0.05, method="wilson"
    )
    return sucessos / total, inferior, superior


def adicionar_intervalos_no_bordo(ax, barras, taxas, erros):
    for i, barra in enumerate(barras):
        x = barra.get_x() + barra.get_width() * 0.94
        x_inicio_traco = x - barra.get_width() * 0.035
        inferior = taxas[i] - erros[0][i]
        superior = taxas[i] + erros[1][i]
        estilo = {"color": "black", "linewidth": 1.4, "solid_capstyle": "butt"}

        ax.plot([x, x], [inferior, superior], **estilo)
        ax.plot([x_inicio_traco, x], [inferior, inferior], **estilo)
        ax.plot([x_inicio_traco, x], [superior, superior], **estilo)


def adicionar_legenda(ax, categorias, colunas, loc="upper left"):
    itens = [
        Patch(facecolor=cor, edgecolor="none", label=rotulo)
        for rotulo, cor in categorias
    ]
    itens.append(
        Line2D(
            [],
            [],
            color="black",
            marker="|",
            linestyle="none",
            markersize=10,
            markeredgewidth=1.4,
            label="Barra preta: intervalo de confiança de 95% (Wilson)",
        )
    )
    ax.legend(
        handles=itens,
        loc=loc,
        ncol=colunas,
        frameon=True,
        facecolor="white",
        edgecolor="none",
        framealpha=0.9,
        fontsize=8,
    )


def linha_proporcao(analise, grupo, sucessos, total):
    proporcao, inferior, superior = proporcao_com_ic(sucessos, total)
    return {
        "analise": analise,
        "grupo": grupo,
        "n": int(total),
        "eventos": int(sucessos),
        "proporcao": proporcao,
        "ic95_inferior": inferior,
        "ic95_superior": superior,
    }


def carregar_dados():
    base = pd.read_csv(DADOS / "base.csv")
    coorte = pd.read_csv(DADOS / "coorte.csv")
    novatos = pd.read_csv(DADOS / "novatos.csv")
    reversoes = pd.read_csv(DADOS / "reversoes.csv")
    for arquivo, tabela in [
        ("base.csv", base),
        ("coorte.csv", coorte),
        ("novatos.csv", novatos),
        ("reversoes.csv", reversoes),
    ]:
        if tabela.empty:
            raise ValueError(f"{arquivo} está vazio.")
    obrigatorias = {
        "na_analise_permanencia",
        "comparavel",
        "revertida",
        "recebeu_aviso",
        "recepcao_semana",
        "permaneceu",
        "edicoes_24h",
        "artigo_novo",
        "semana_criacao",
        "situacao_reversao",
        "minutos_ate_reversao",
        "tipo_revertor",
    }
    faltantes = obrigatorias - set(base.columns)
    if faltantes:
        raise ValueError(f"base.csv: faltam colunas obrigatórias: {sorted(faltantes)}")
    return base, coorte, novatos, reversoes


def salvar_grafico_reversoes(base, reversoes):
    comparaveis = base[base["comparavel"].eq(1)]
    grupos = [
        ("Não revertida", int(comparaveis["revertida"].eq(0).sum())),
        ("Revertida em até 48 h", int(comparaveis["revertida"].eq(1).sum())),
    ]
    total = len(comparaveis)
    valores = [proporcao_com_ic(n, total) for _, n in grupos]
    taxas = [v[0] * 100 for v in valores]
    erros = [
        [
            (v[0] - v[1]) * 100
            for v in valores
        ],
        [
            (v[2] - v[0]) * 100
            for v in valores
        ],
    ]

    fig, ax = plt.subplots(figsize=(8, 4.8))
    barras = ax.bar(
        [g[0] for g in grupos],
        taxas,
        color=["#6b8e9b", "#d47761"],
    )
    adicionar_intervalos_no_bordo(ax, barras, taxas, erros)
    ax.set_ylabel("Percentual entre primeiras edições comparáveis")
    ax.set_title(f"Reversão da primeira edição (n = {total:,})".replace(",", "."))
    ax.set_ylim(0, 100)
    adicionar_legenda(
        ax,
        [
            ("Não revertida", "#6b8e9b"),
            ("Revertida em até 48 h", "#d47761"),
        ],
        colunas=1,
    )
    for barra, (_, n), taxa in zip(barras, grupos, taxas):
        ax.text(
            barra.get_x() + barra.get_width() / 2,
            barra.get_height() + 1.5,
            f"{taxa:.1f}% (n={n:,})".replace(",", "."),
            ha="center",
        )
    minutos = reversoes.loc[
        reversoes["situacao"].eq("revertida"), "segundos_ate_reversao"
    ]
    mediana_min = pd.to_numeric(minutos, errors="coerce").median() / 60
    ax.text(
        0.98,
        0.9,
        f"Mediana até a reversão: {mediana_min:.1f} min",
        transform=ax.transAxes,
        ha="right",
        va="top",
    )
    fig.tight_layout()
    fig.savefig(PASTA_GRAFICOS / "reversoes_primeira_edicao.png")
    plt.close(fig)


def salvar_grafico_tempo_reversao(reversoes):
    revertidas = reversoes[reversoes["situacao"].eq("revertida")].copy()
    segundos = pd.to_numeric(
        revertidas["segundos_ate_reversao"], errors="coerce"
    )
    faixas = [
        ("Até 1 hora", segundos.le(3600)),
        (">1 a 24 horas", segundos.gt(3600) & segundos.le(86400)),
        (">24 a 48 horas", segundos.gt(86400) & segundos.le(172800)),
    ]
    dados = [
        (rotulo, int(filtro.sum()))
        for rotulo, filtro in faixas
    ]
    total = int(segundos.notna().sum())
    proporcoes = [proporcao_com_ic(n, total) for _, n in dados]
    taxas = [p[0] * 100 for p in proporcoes]
    erros = [
        [(p[0] - p[1]) * 100 for p in proporcoes],
        [(p[2] - p[0]) * 100 for p in proporcoes],
    ]

    fig, ax = plt.subplots(figsize=(8, 4.8))
    barras = ax.bar(
        [rotulo for rotulo, _ in dados],
        taxas,
        color=["#d47761", "#c5a35a", "#6b8e9b"],
    )
    adicionar_intervalos_no_bordo(ax, barras, taxas, erros)
    ax.set_ylabel("Reversões (%)")
    ax.set_title(
        f"Tempo até a reversão da primeira edição (n = {total:,})".replace(",", ".")
    )
    ax.set_ylim(0, 100)
    adicionar_legenda(
        ax,
        [
            ("Até 1 hora", "#d47761"),
            (">1 a 24 horas", "#c5a35a"),
            (">24 a 48 horas", "#6b8e9b"),
        ],
        colunas=1,
        loc="upper right",
    )
    for barra, (_, n), taxa in zip(barras, dados, taxas):
        ax.text(
            barra.get_x() + barra.get_width() / 2,
            barra.get_height() + 1.5,
            f"{taxa:.1f}% (n={n:,})".replace(",", "."),
            ha="center",
        )
    fig.tight_layout()
    fig.savefig(PASTA_GRAFICOS / "tempo_ate_reversao.png")
    plt.close(fig)


def salvar_grafico_tipo_revertor(reversoes):
    revertidas = reversoes[reversoes["situacao"].eq("revertida")]
    rotulos = ["Humano", "Ferramenta semiautomática", "Robô"]
    categorias = ["humano", "ferramenta", "robo"]
    total = len(revertidas)
    dados = [
        (rotulo, int(revertidas["tipo_revertor"].eq(categoria).sum()))
        for rotulo, categoria in zip(rotulos, categorias)
    ]
    proporcoes = [proporcao_com_ic(n, total) for _, n in dados]
    taxas = [p[0] * 100 for p in proporcoes]
    erros = [
        [(p[0] - p[1]) * 100 for p in proporcoes],
        [(p[2] - p[0]) * 100 for p in proporcoes],
    ]

    fig, ax = plt.subplots(figsize=(8, 4.8))
    barras = ax.bar(
        [rotulo for rotulo, _ in dados],
        taxas,
        color=["#6b8e9b", "#d47761", "#c5a35a"],
    )
    adicionar_intervalos_no_bordo(ax, barras, taxas, erros)
    ax.set_ylabel("Reversões (%)")
    ax.set_title(f"Quem reverteu a primeira edição (n = {total:,})".replace(",", "."))
    ax.set_ylim(0, max(65, max(taxas) + 8))
    adicionar_legenda(
        ax,
        [
            ("Humano", "#6b8e9b"),
            ("Ferramenta semiautomática", "#d47761"),
            ("Robô", "#c5a35a"),
        ],
        colunas=1,
        loc="upper right",
    )
    for barra, (_, n), taxa in zip(barras, dados, taxas):
        ax.text(
            barra.get_x() + barra.get_width() / 2,
            barra.get_height() + 1.5,
            f"{taxa:.1f}% (n={n:,})",
            ha="center",
        )
    fig.tight_layout()
    fig.savefig(PASTA_GRAFICOS / "tipo_revertor_primeira_edicao.png")
    plt.close(fig)


def salvar_grafico_recepcao(base):
    totais = base["recepcao_semana"].value_counts()
    rotulos = ["Nenhuma", "Aviso (inclui bloqueio)", "Outra"]
    categorias = ["nenhuma", "aviso", "outra"]
    n_total = len(base)
    dados = [
        (rotulo, int(totais.get(categoria, 0)))
        for rotulo, categoria in zip(rotulos, categorias)
    ]
    proporcoes = [proporcao_com_ic(n, n_total) for _, n in dados]
    taxas = [p[0] * 100 for p in proporcoes]
    erros = [
        [(p[0] - p[1]) * 100 for p in proporcoes],
        [(p[2] - p[0]) * 100 for p in proporcoes],
    ]

    fig, ax = plt.subplots(figsize=(9, 5))
    barras = ax.bar(
        [d[0] for d in dados],
        taxas,
        color=["#6b8e9b", "#d47761", "#c5a35a"],
    )
    adicionar_intervalos_no_bordo(ax, barras, taxas, erros)
    ax.set_ylabel("Novatos (%)")
    ax.set_title(
        f"Recepção humana nos primeiros 7 dias (n = {n_total:,})".replace(",", ".")
    )
    ax.set_ylim(0, max(100, max(taxas) + 8))
    adicionar_legenda(
        ax,
        [
            ("Nenhuma", "#6b8e9b"),
            ("Aviso (inclui bloqueio)", "#d47761"),
            ("Outra", "#c5a35a"),
        ],
        colunas=2,
    )
    for barra, (_, n), taxa in zip(barras, dados, taxas):
        ax.text(
            barra.get_x() + barra.get_width() / 2,
            barra.get_height() + 1.5,
            f"{taxa:.1f}% (n={n:,})".replace(",", "."),
            ha="center",
        )
    fig.tight_layout()
    fig.savefig(PASTA_GRAFICOS / "recepcao_primeira_semana.png")
    plt.close(fig)


def salvar_grafico_permanencia(base):
    elegiveis = base[base["na_analise_permanencia"].eq(1)]
    comparaveis = elegiveis[elegiveis["comparavel"].eq(1)]
    grupos = [
        (
            "Primeira edição\nrevertida",
            comparaveis[comparaveis["revertida"].eq(1)],
        ),
        (
            "Primeira edição\nnão revertida",
            comparaveis[comparaveis["revertida"].eq(0)],
        ),
        ("Recebeu aviso", elegiveis[elegiveis["recebeu_aviso"].eq(1)]),
        ("Sem aviso", elegiveis[elegiveis["recebeu_aviso"].eq(0)]),
    ]
    dados = [
        (rotulo, int(df["permaneceu"].sum()), len(df))
        for rotulo, df in grupos
    ]
    proporcoes = [proporcao_com_ic(sucessos, total) for _, sucessos, total in dados]
    taxas = [p[0] * 100 for p in proporcoes]
    erros = [
        [(p[0] - p[1]) * 100 for p in proporcoes],
        [(p[2] - p[0]) * 100 for p in proporcoes],
    ]

    fig, ax = plt.subplots(figsize=(10, 5.2))
    cores = ["#d47761", "#6b8e9b", "#8e6c9f", "#c5a35a"]
    barras = ax.bar(
        [d[0] for d in dados],
        taxas,
        color=cores,
    )
    adicionar_intervalos_no_bordo(ax, barras, taxas, erros)
    ax.set_ylabel("Permaneceu (edição entre os dias 31 e 90, %)")
    ax.set_title("Permanência segundo a primeira experiência")
    ax.set_ylim(0, max(18, max(taxas) + 3))
    adicionar_legenda(
        ax,
        [
            ("Primeira edição revertida", "#d47761"),
            ("Primeira edição não revertida", "#6b8e9b"),
            ("Recebeu aviso", "#8e6c9f"),
            ("Sem aviso", "#c5a35a"),
        ],
        colunas=2,
    )
    for barra, (_, sucessos, total), taxa in zip(barras, dados, taxas):
        ax.text(
            barra.get_x() + barra.get_width() / 2,
            barra.get_height() + 0.5,
            f"{taxa:.1f}% ({sucessos}/{total})",
            ha="center",
        )
    ax.text(
        0.99,
        0.98,
        "IC 95% de Wilson; comparações observacionais",
        transform=ax.transAxes,
        ha="right",
        va="top",
        fontsize=8,
    )
    fig.tight_layout()
    fig.savefig(PASTA_GRAFICOS / "permanencia_por_recepcao.png")
    plt.close(fig)


def resumo_descritivo(base, coorte, novatos, reversoes):
    elegiveis = base[base["na_analise_permanencia"].eq(1)]
    comparaveis = elegiveis[elegiveis["comparavel"].eq(1)]
    linhas = []
    linhas.append(
        linha_proporcao(
            "funil", "Coorte incluída", len(coorte), len(coorte)
        )
    )
    linhas.append(
        linha_proporcao(
            "funil",
            "Editaram ao menos uma vez",
            len(novatos),
            len(coorte),
        )
    )
    linhas.append(
        linha_proporcao(
            "funil",
            "Novatos com edição em artigo",
            len(base),
            len(novatos),
        )
    )
    linhas.append(
        linha_proporcao(
            "funil",
            "Na análise de permanência",
            len(elegiveis),
            len(base),
        )
    )
    linhas.append(
        linha_proporcao(
            "funil",
            "Primeira edição comparável na análise",
            len(comparaveis),
            len(elegiveis),
        )
    )

    total_comparaveis = int(base["comparavel"].eq(1).sum())
    revertidas = int(
        base.loc[base["comparavel"].eq(1), "revertida"].eq(1).sum()
    )
    linhas.append(
        linha_proporcao(
            "QP1", "Primeira edição revertida (até 48 h)", revertidas, total_comparaveis
        )
    )
    rev = reversoes[reversoes["situacao"].eq("revertida")]
    segundos = pd.to_numeric(rev["segundos_ate_reversao"], errors="coerce")
    for grupo, mascara in [
        ("Revertidas em até 1 h", segundos.le(3600)),
        (
            "Revertidas em >1 a 24 h",
            segundos.gt(3600) & segundos.le(86400),
        ),
        (
            "Revertidas em >24 a 48 h",
            segundos.gt(86400) & segundos.le(172800),
        ),
    ]:
        linhas.append(
            linha_proporcao("QP1", grupo, int(mascara.sum()), int(segundos.notna().sum()))
        )
    for categoria in ("nenhuma", "aviso", "outra"):
        n = int(base["recepcao_semana"].eq(categoria).sum())
        linhas.append(
            linha_proporcao(
                "QP1",
                f"Recepção na semana: {categoria}",
                n,
                len(base),
            )
        )
    for categoria in ("humano", "ferramenta", "robo"):
        n = int(reversoes.loc[reversoes["situacao"].eq("revertida"), "tipo_revertor"].eq(categoria).sum())
        linhas.append(
            linha_proporcao(
                "QP2", f"Reversões por {categoria}", n, len(rev)
            )
        )

    for rotulo, df in [
        ("Revertida", comparaveis[comparaveis["revertida"].eq(1)]),
        ("Não revertida", comparaveis[comparaveis["revertida"].eq(0)]),
        ("Recebeu aviso", elegiveis[elegiveis["recebeu_aviso"].eq(1)]),
        ("Sem aviso", elegiveis[elegiveis["recebeu_aviso"].eq(0)]),
    ]:
        linhas.append(
            linha_proporcao(
                "QP3",
                f"Permaneceu: {rotulo}",
                int(df["permaneceu"].sum()),
                len(df),
            )
        )
    return pd.DataFrame(linhas)


def testar_associacoes(base):
    elegiveis = base[base["na_analise_permanencia"].eq(1)].copy()
    comparaveis = elegiveis[elegiveis["comparavel"].eq(1)].copy()
    configuracoes = [
        ("H1: reversão x permanência", comparaveis, "revertida"),
        ("H2: aviso x permanência", elegiveis, "recebeu_aviso"),
        (
            "H2: aviso x permanência entre revertidos",
            comparaveis[comparaveis["revertida"].eq(1)],
            "recebeu_aviso",
        ),
    ]
    linhas = []
    for nome, dados, exposicao in configuracoes:
        tabela = pd.crosstab(dados[exposicao], dados["permaneceu"]).reindex(
            index=[0, 1], columns=[0, 1], fill_value=0
        )
        resultado = chi2_contingency(tabela, correction=True)
        linhas.append(
            {
                "comparacao": nome,
                "variavel_exposicao": exposicao,
                "n": len(dados),
                "chi2": resultado.statistic,
                "graus_liberdade": 1,
                "p_valor": resultado.pvalue,
                "correcao_yates": True,
                "tabela_2x2": (
                    f"exposto: não permaneceu={tabela.loc[1, 0]}, "
                    f"permaneceu={tabela.loc[1, 1]}; "
                    f"referência: não permaneceu={tabela.loc[0, 0]}, "
                    f"permaneceu={tabela.loc[0, 1]}"
                ),
            }
        )
    return pd.DataFrame(linhas)


def ajustar_modelos(base):
    elegiveis = base[base["na_analise_permanencia"].eq(1)].copy()
    comparaveis = elegiveis[elegiveis["comparavel"].eq(1)].copy()
    for dados in (elegiveis, comparaveis):
        dados["log_edicoes_24h"] = np.log1p(dados["edicoes_24h"])
        dados["semana_criacao"] = dados["semana_criacao"].astype("category")

    modelos = [
        (
            "H1 - comparáveis",
            comparaveis,
            "permaneceu ~ revertida + recebeu_aviso + log_edicoes_24h + C(semana_criacao)",
        ),
        (
            "H2 - elegíveis",
            elegiveis,
            "permaneceu ~ recebeu_aviso + log_edicoes_24h + artigo_novo + C(semana_criacao)",
        ),
        (
            "H2 - revertidos",
            comparaveis[comparaveis["revertida"].eq(1)].copy(),
            "permaneceu ~ recebeu_aviso + log_edicoes_24h + C(semana_criacao)",
        ),
    ]
    linhas = []
    for nome, dados, formula in modelos:
        ajuste = logit(formula, data=dados).fit(disp=False)
        intervalos = ajuste.conf_int()
        for variavel in ajuste.params.index:
            if variavel == "Intercept":
                continue
            linhas.append(
                {
                    "modelo": nome,
                    "variavel": variavel,
                    "n": int(ajuste.nobs),
                    "odds_ratio": float(np.exp(ajuste.params[variavel])),
                    "ic95_inferior": float(np.exp(intervalos.loc[variavel, 0])),
                    "ic95_superior": float(np.exp(intervalos.loc[variavel, 1])),
                    "p_valor": float(ajuste.pvalues[variavel]),
                    "formula": formula,
                }
            )
    return pd.DataFrame(linhas)


def resumo_qp2(reversoes):
    revertidas = reversoes[reversoes["situacao"].eq("revertida")]
    total = len(revertidas)
    sumario = revertidas["sumario_reversao"].fillna("").astype(str).str.strip()
    categorias = [
        ("Reversões feitas por humanos", "humano", None),
        ("Reversões feitas por ferramenta semiautomática", "ferramenta", None),
        ("Reversões feitas por robôs", "robo", None),
        ("Reversões com sumário registrado (não mede qualidade da explicação)", None, True),
        ("Reversões sem sumário registrado", None, False),
    ]
    linhas = []
    for rotulo, ator, tem_sumario in categorias:
        if ator is not None:
            eventos = int(revertidas["tipo_revertor"].eq(ator).sum())
        else:
            eventos = int(sumario.ne("").sum() if tem_sumario else sumario.eq("").sum())
        proporcao, inferior, superior = proporcao_com_ic(eventos, total)
        linhas.append(
            {
                "indicador": rotulo,
                "eventos": eventos,
                "total_reversoes": total,
                "proporcao": proporcao,
                "ic95_inferior": inferior,
                "ic95_superior": superior,
            }
        )
    return pd.DataFrame(linhas)


def main():
    PASTA_GRAFICOS.mkdir(parents=True, exist_ok=True)
    base, coorte, novatos, reversoes = carregar_dados()
    resumo = resumo_descritivo(base, coorte, novatos, reversoes)
    testes = testar_associacoes(base)
    modelos = ajustar_modelos(base)
    qp2 = resumo_qp2(reversoes)

    resumo.to_csv(ARQUIVO_RESUMO, index=False)
    testes.to_csv(ARQUIVO_TESTES, index=False)
    modelos.to_csv(ARQUIVO_MODELOS, index=False)
    qp2.to_csv(ARQUIVO_QP2, index=False)
    salvar_grafico_reversoes(base, reversoes)
    salvar_grafico_tempo_reversao(reversoes)
    salvar_grafico_tipo_revertor(reversoes)
    salvar_grafico_recepcao(base)
    salvar_grafico_permanencia(base)

    print("Análises concluídas.")
    print(f"  Resumo: {ARQUIVO_RESUMO.relative_to(RAIZ)}")
    print(f"  Testes: {ARQUIVO_TESTES.relative_to(RAIZ)}")
    print(f"  Modelos: {ARQUIVO_MODELOS.relative_to(RAIZ)}")
    print(f"  QP2: {ARQUIVO_QP2.relative_to(RAIZ)}")
    print(f"  Gráficos: {PASTA_GRAFICOS.relative_to(RAIZ)}")
    print("\nProporções de permanência:")
    print(resumo[resumo["analise"].eq("QP3")].to_string(index=False))
    print("\nTestes de associação:")
    print(testes.to_string(index=False))
    print("\nEfeitos principais dos modelos (OR):")
    print(
        modelos[
            modelos["variavel"].isin(["revertida", "recebeu_aviso"])
        ].to_string(index=False)
    )


if __name__ == "__main__":
    main()
