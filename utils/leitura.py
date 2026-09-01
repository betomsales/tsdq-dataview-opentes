import os
import pickle
import tempfile

import pandas as pd


def _normalizar_colunas(df):
    """
    Normaliza nomes de colunas vindos de CSV ou HDF5.
    """

    df.columns = (
        df.columns
        .astype(str)
        .str.strip()
    )

    return df


def _obter_extensao(uploaded_file):
    """
    Retorna a extensão do arquivo carregado.
    """

    nome = getattr(
        uploaded_file,
        "name",
        ""
    )

    return os.path.splitext(
        nome.lower()
    )[1]


def ler_csv(uploaded_file):
    """
    Le um CSV e normaliza as colunas.
    """

    try:
        uploaded_file.seek(0)
        df = pd.read_csv(uploaded_file)

    except UnicodeDecodeError:

        uploaded_file.seek(0)

        df = pd.read_csv(
            uploaded_file,
            encoding="latin1"
        )

    return _normalizar_colunas(
        df
    )


def _salvar_upload_temporario(
    uploaded_file,
    suffix
):
    """
    Salva upload em arquivo temporario para leitura HDF5 do pandas.
    """

    uploaded_file.seek(0)

    descritor, caminho = tempfile.mkstemp(
        suffix=suffix
    )

    with os.fdopen(
        descritor,
        "wb"
    ) as arquivo:

        arquivo.write(
            uploaded_file.read()
        )

    return caminho


def _decodificar_attr_pytables(valor):
    """
    Decodifica listas de colunas armazenadas como pickle pelo PyTables.
    """

    if hasattr(
        valor,
        "tobytes"
    ):

        valor = valor.tobytes()

    if isinstance(
        valor,
        bytes
    ):

        try:

            return pickle.loads(
                valor
            )

        except Exception:

            return []

    return []


def _decodificar_valor_hdf5(valor):
    """
    Converte bytes vindos do HDF5 para texto.
    """

    if isinstance(
        valor,
        bytes
    ):

        return valor.decode(
            "utf-8",
            errors="replace"
        )

    return valor


def _ler_hdf5_com_h5py(caminho):
    """
    Fallback para tabelas HDF5 salvas no formato Pandas/PyTables.
    """

    try:

        import h5py

    except ImportError as erro:

        raise ImportError(
            "Para ler HDF5, instale 'tables' ou 'h5py'."
        ) from erro

    with h5py.File(
        caminho,
        "r"
    ) as arquivo:

        grupos_tabela = []

        def visitar(
            nome,
            objeto
        ):

            if (
                isinstance(objeto, h5py.Group)
                and
                "table" in objeto
            ):

                grupos_tabela.append(
                    nome
                )

        arquivo.visititems(
            visitar
        )

        if not grupos_tabela:

            raise ValueError(
                "Nenhuma tabela compativel foi encontrada no arquivo HDF5."
            )

        grupo = arquivo[
            grupos_tabela[0]
        ]

        tabela = grupo[
            "table"
        ]

        dados = tabela[:]

        colunas = {}

        for nome_bloco in tabela.dtype.names:

            if nome_bloco == "index":

                continue

            nomes_colunas = _decodificar_attr_pytables(
                tabela.attrs.get(
                    f"{nome_bloco}_kind",
                    b""
                )
            )

            if not nomes_colunas:

                nomes_colunas = [
                    nome_bloco
                ]

            valores = dados[
                nome_bloco
            ]

            if len(
                valores.shape
            ) == 1:

                valores = valores.reshape(
                    -1,
                    1
                )

            for indice, nome_coluna in enumerate(
                nomes_colunas
            ):

                serie = valores[
                    :,
                    indice
                ]

                colunas[
                    str(nome_coluna)
                ] = [
                    _decodificar_valor_hdf5(
                        valor
                    )
                    for valor in serie
                ]

        return pd.DataFrame(
            colunas
        )


def ler_hdf5(
    uploaded_file,
    chave=None
):
    """
    Le um HDF5/PyTables e normaliza as colunas.
    """

    caminho_temporario = _salvar_upload_temporario(
        uploaded_file,
        _obter_extensao(uploaded_file) or ".h5"
    )

    try:

        with pd.HDFStore(
            caminho_temporario,
            mode="r"
        ) as store:

            chaves = store.keys()

        if not chaves:

            raise ValueError(
                "Nenhuma tabela foi encontrada no arquivo HDF5."
            )

        chave_leitura = chave or chaves[0]

        df = pd.read_hdf(
            caminho_temporario,
            key=chave_leitura
        )

    except ImportError:

        df = _ler_hdf5_com_h5py(
            caminho_temporario
        )

    finally:

        if os.path.exists(
            caminho_temporario
        ):

            os.remove(
                caminho_temporario
            )

    if not isinstance(
        df.index,
        pd.RangeIndex
    ):

        df = df.reset_index()

    return _normalizar_colunas(
        df
    )


def ler_dados(uploaded_file):
    """
    Le CSV ou HDF5 e retorna um DataFrame padronizado.
    """

    extensao = _obter_extensao(
        uploaded_file
    )

    if extensao in [
        ".h5",
        ".hdf5"
    ]:

        return ler_hdf5(
            uploaded_file
        )

    if extensao == ".csv":

        return ler_csv(
            uploaded_file
        )

    raise ValueError(
        "Formato não suportado. Use CSV, H5 ou HDF5."
    )


def processar_tempo(df):
    """
    Cria eixo temporal padronizado.
    """

    primeira_coluna = df.columns[0]

    tempo = pd.to_datetime(
        df[primeira_coluna]
        .astype(str)
        .str.strip(),
        format="mixed",
        errors="coerce"
    )

    if tempo.isna().all():

        df["Tempo_EixoX"] = range(len(df))

    else:

        df["Tempo_EixoX"] = tempo

    return df
