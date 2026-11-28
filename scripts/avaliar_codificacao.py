"""Calcula kappa de Cohen nas avaliações independentes do piloto."""

from pathlib import Path

import pandas as pd
from sklearn.metrics import cohen_kappa_score

RAIZ = Path(__file__).resolve().parent.parent
ARQUIVOS_PILOTO = [
    RAIZ / "dados" / "piloto_codificador_1.csv",
    RAIZ / "dados" / "piloto_codificador_2.csv",
]
ATRIBUTOS = ("boa_fe", "explicacao_reversao", "tom_mensagem")
LIMIAR_KAPPA = 0.7
CATEGORIAS = {
    "boa_fe": {"boa_fe", "ma_fe", "indeterminada"},
    "explicacao_reversao": {
        "especifica",
        "generica",
        "ausente",
        "incerta",
        "nao_aplicavel",
    },
    "tom_mensagem": {
        "acolhedor_construtivo",
        "neutro_informativo",
        "repreensivo_punitivo",
        "misto_ou_incerto",
        "sem_mensagem",
    },
}


def main():
    ausentes = [arquivo for arquivo in ARQUIVOS_PILOTO if not arquivo.exists()]
    if ausentes:
        raise FileNotFoundError(
            f"{', '.join(arquivo.relative_to(RAIZ).as_posix() for arquivo in ausentes)} "
            "não existe; execute "
            "'python3 scripts/preparar_codificacao.py' primeiro."
        )
    primeiro, segundo = [
        pd.read_csv(arquivo, dtype="string", keep_default_na=False)
        for arquivo in ARQUIVOS_PILOTO
    ]
    chave = "codigo_amostra"
    for arquivo, dados in zip(ARQUIVOS_PILOTO, (primeiro, segundo)):
        if dados[chave].duplicated().any():
            raise ValueError(
                f"{arquivo.relative_to(RAIZ)} contém códigos de caso duplicados."
            )
        if len(dados) != 30:
            raise ValueError(
                f"{arquivo.relative_to(RAIZ)} deve conter exatamente 30 casos."
            )
        for atributo in ATRIBUTOS:
            if atributo not in dados:
                raise ValueError(
                    f"{arquivo.relative_to(RAIZ)} não contém a coluna {atributo}."
                )
            invalidas = set(dados[atributo].str.strip()) - {
                "",
                *CATEGORIAS[atributo],
            }
            if invalidas:
                raise ValueError(
                    f"Categorias inválidas em {arquivo.relative_to(RAIZ)} "
                    f"({atributo}): {sorted(invalidas)}."
                )
    if set(primeiro[chave]) != set(segundo[chave]):
        raise ValueError("Os dois arquivos do piloto devem conter os mesmos casos.")
    piloto = primeiro.merge(
        segundo[[chave, *ATRIBUTOS]],
        on=chave,
        how="inner",
        validate="one_to_one",
        suffixes=("_codificador_1", "_codificador_2"),
    )
    if len(piloto) != 30:
        raise ValueError(
            f"Os dois arquivos devem conter os mesmos 30 casos do piloto; "
            f"foram encontrados {len(piloto)} em comum."
        )
    print(
        "Kappa do piloto independente. Preencha os dois arquivos separados "
        "antes de calcular."
    )
    for atributo in ATRIBUTOS:
        coluna_1 = f"{atributo}_codificador_1"
        coluna_2 = f"{atributo}_codificador_2"
        avaliados = piloto[
            piloto[f"{atributo}_codificador_1"].str.strip().ne("")
            & piloto[f"{atributo}_codificador_2"].str.strip().ne("")
        ]
        if len(avaliados) < 2:
            print(f"  {atributo}: ainda não calculável (menos de 2 pares completos).")
            continue
        kappa = cohen_kappa_score(
            avaliados[f"{atributo}_codificador_1"],
            avaliados[f"{atributo}_codificador_2"],
        )
        if pd.isna(kappa):
            print(
                f"  {atributo}: kappa indefinido; verifiquem se há variação "
                "nas categorias atribuídas."
            )
            continue
        estado = "atingiu o limiar" if kappa >= LIMIAR_KAPPA else "abaixo do limiar"
        print(
            f"  {atributo}: kappa={kappa:.3f}; "
            f"n={len(avaliados)}/{len(piloto)}; {estado} ({LIMIAR_KAPPA:.1f})."
        )
        if kappa < LIMIAR_KAPPA:
            print(
                "    Discutam divergências, revisem o livro de códigos e "
                "codifiquem outro piloto independente."
            )


if __name__ == "__main__":
    main()
