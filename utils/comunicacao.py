import json

import pandas as pd


COLUNAS_OBRIGATORIAS = [
    "Tempo",
    "Origem",
    "Atributo",
    "Valor"
]

ATRIBUTOS_PACOTES = [
    "packets_sent",
    "packets_received",
    "packets_dropped"
]


def ler_resultados_comunicacao(uploaded_file):
    """
    Lê arquivo CSV de resultados da comunicação.
    """

    uploaded_file.seek(0)

    df = pd.read_csv(uploaded_file)

    df.columns = (
        df.columns
        .str.strip()
    )

    return df


def validar_resultados_comunicacao(df):
    """
    Valida estrutura mínima do CSV da comunicação.
    """

    erros = []

    colunas_ausentes = [
        coluna
        for coluna in COLUNAS_OBRIGATORIAS
        if coluna not in df.columns
    ]

    if colunas_ausentes:

        erros.append(
            "Colunas obrigatórias ausentes: "
            + ", ".join(colunas_ausentes)
        )

    return erros


def listar_origens(df):
    """
    Lista origens disponíveis no arquivo.
    """

    if "Origem" not in df.columns:
        return []

    return sorted(
        df["Origem"]
        .dropna()
        .astype(str)
        .unique()
        .tolist()
    )


def preparar_tabela_temporal(df, origem):
    """
    Filtra a origem OMNeT++ e pivota atributos por tempo.
    """

    node_data = (
        df[df["Origem"] == origem]
        .copy()
    )

    time_data = (
        node_data
        .pivot_table(
            index="Tempo",
            columns="Atributo",
            values="Valor",
            aggfunc="first"
        )
        .reset_index()
    )

    for coluna in ATRIBUTOS_PACOTES:

        if coluna not in time_data.columns:
            time_data[coluna] = 0.0

        time_data[coluna] = (
            pd.to_numeric(
                time_data[coluna],
                errors="coerce"
            )
            .fillna(0)
        )

    return time_data


def extrair_remetente(mensagem):
    """
    Extrai o remetente da mensagem FIPA-ACL serializada em JSON.
    """

    try:

        if pd.isna(mensagem) or str(mensagem).strip() == "":
            return "Rede"

        msg_json = json.loads(mensagem)

        sender = msg_json.get(
            "sender",
            ""
        )

        if sender:
            return sender.split("@")[0]

        return "Rede"

    except (TypeError, json.JSONDecodeError):

        return "Rede"


def _dividir_valores(valor):
    """
    Divide valores multiplexados por |||.
    """

    if pd.isna(valor):
        return []

    valor = str(valor)

    if valor == "" or valor == "nan":
        return []

    return valor.split("|||")


def _valor_float(lista, indice):
    """
    Retorna item numérico de uma lista multiplexada.
    """

    if indice >= len(lista):
        return 0.0

    try:
        return float(lista[indice])

    except (TypeError, ValueError):
        return 0.0


def expandir_mensagens(time_data):
    """
    Desempacota telemetria multiplexada em uma linha por mensagem.
    """

    dados_expandidos = []

    for _, row in time_data.iterrows():

        tempo = row["Tempo"]

        mensagens = _dividir_valores(
            row.get("val_out")
        )

        tamanhos = _dividir_valores(
            row.get("packet_sizes_out")
        )

        latencias = _dividir_valores(
            row.get("latencies_out")
        )

        jitters = _dividir_valores(
            row.get("jitters_out")
        )

        for indice, mensagem in enumerate(mensagens):

            agente = extrair_remetente(
                mensagem
            )

            dados_expandidos.append(
                {
                    "Tempo": tempo,
                    "Agente": agente,
                    "Tamanho do pacote": _valor_float(
                        tamanhos,
                        indice
                    ),
                    "Latencia": _valor_float(
                        latencias,
                        indice
                    ),
                    "Jitter": _valor_float(
                        jitters,
                        indice
                    )
                }
            )

    return pd.DataFrame(
        dados_expandidos
    )


def classificar_agente(agente):
    """
    Classifica agentes para visualização de topologia estrela.
    """

    if agente == "AgenteCentral":
        return "Central"

    if str(agente).startswith("AgenteP_"):
        return "Periférico"

    return "Rede"


def calcular_kpis(time_data, df_expandido):
    """
    Calcula indicadores globais da comunicação.
    """

    enviados = (
        time_data["packets_sent"].max()
        if "packets_sent" in time_data.columns
        else 0
    )

    recebidos = (
        time_data["packets_received"].max()
        if "packets_received" in time_data.columns
        else 0
    )

    dropados = (
        time_data["packets_dropped"].max()
        if "packets_dropped" in time_data.columns
        else 0
    )

    em_transito = max(
        0,
        enviados - recebidos - dropados
    )

    taxa_drop = (
        dropados / enviados * 100
        if enviados > 0
        else 0
    )

    return {
        "pacotes_enviados": enviados,
        "pacotes_recebidos": recebidos,
        "pacotes_dropados": dropados,
        "pacotes_em_transito": em_transito,
        "taxa_drop": taxa_drop,
        "mensagens": len(df_expandido),
        "agentes": (
            df_expandido["Agente"].nunique()
            if not df_expandido.empty
            else 0
        ),
        "latencia_media": (
            df_expandido["Latencia"].mean()
            if not df_expandido.empty
            else 0
        ),
        "latencia_maxima": (
            df_expandido["Latencia"].max()
            if not df_expandido.empty
            else 0
        ),
        "jitter_medio": (
            df_expandido["Jitter"].mean()
            if not df_expandido.empty
            else 0
        ),
        "tamanho_medio": (
            df_expandido["Tamanho do pacote"].mean()
            if not df_expandido.empty
            else 0
        )
    }
