import unicodedata

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from components.graficos import aplicar_faixas_prodist_temporal
from utils.escalas import obter_escala_visual
from utils.rotulos_medicoes import montar_rotulo_serie


CORES_FASES = {
    "V1": "#2563eb",
    "V2": "#f97316",
    "V3": "#16a34a",
    "VA": "#2563eb",
    "VB": "#f97316",
    "VC": "#16a34a",
    "A": "#2563eb",
    "B": "#f97316",
    "C": "#16a34a",
}

ORDEM_FASES = {
    "V1": 0,
    "VA": 0,
    "A": 0,
    "V2": 1,
    "VB": 1,
    "B": 1,
    "V3": 2,
    "VC": 2,
    "C": 2,
}


def _normalizar_texto(texto):
    texto = str(texto or "")
    texto = unicodedata.normalize(
        "NFKD",
        texto,
    )
    texto = texto.encode(
        "ascii",
        errors="ignore",
    ).decode(
        "ascii",
    )
    return texto.lower().strip()


def _eh_tensao(variavel):
    return _normalizar_texto(
        variavel.get("tipo")
    ) == "tensao"


def _ordem_variavel(variavel):
    fase = str(
        variavel.get("fase") or ""
    ).upper()

    return (
        ORDEM_FASES.get(fase, 99),
        fase,
        variavel.get("rotulo_serie") or variavel.get("coluna_original", ""),
    )


def _variaveis_tensao_no(estrutura, node_id):
    variaveis = []

    for elementos in estrutura.values():
        for elemento, itens in elementos.items():
            if elemento != node_id:
                continue

            for variavel in itens:
                if _eh_tensao(variavel):
                    variaveis.append(variavel)

    return sorted(
        variaveis,
        key=_ordem_variavel,
    )


def _tempo_atual(df_plot, frame_index):
    if df_plot.empty:
        return None, None

    try:
        indice = int(frame_index)
    except (TypeError, ValueError):
        indice = 0

    indice = min(
        max(indice, 0),
        len(df_plot) - 1,
    )

    return indice, df_plot["Tempo"].iloc[indice]


def _formatar_valor(valor, unidade):
    if pd.isna(valor):
        return "sem medição"

    texto = f"{float(valor):.4f}".rstrip("0").rstrip(".")

    if unidade:
        return f"{texto} {unidade}"

    return texto


def render_oscilografia_no(
    df,
    estrutura,
    node_id,
    frame_index=None,
    key_prefix="oscilografia",
):
    """Renderiza a série temporal de tensão do nó com marcador do frame atual."""

    variaveis = _variaveis_tensao_no(
        estrutura,
        node_id,
    )

    st.subheader(
        f"Oscilografia do nó {node_id}"
    )
    st.caption(
        "A curva representa a série temporal disponível no CSV para a barra "
        "selecionada. O marcador vertical acompanha o instante selecionado "
        "no grafo ou no controle de tempo."
    )

    if not variaveis:
        st.info(
            "O barramento selecionado não possui séries de tensão reconhecidas "
            "para oscilografia."
        )
        return

    colunas_validas = [
        variavel
        for variavel in variaveis
        if variavel.get("coluna_original") in df.columns
    ]

    if not colunas_validas:
        st.info(
            "As colunas de tensão associadas ao barramento não foram "
            "encontradas no conjunto temporal carregado."
        )
        return

    unidade_original = colunas_validas[0].get(
        "unidade_detectada"
    )
    unidades = {
        variavel.get("unidade_detectada")
        for variavel in colunas_validas
    }

    valores_base = []
    df_plot = pd.DataFrame()
    df_plot["Tempo"] = df["Tempo_EixoX"]
    nomes_series = []

    for variavel in colunas_validas:
        coluna = variavel["coluna_original"]
        rotulo = montar_rotulo_serie(
            variavel,
            incluir_origem=False,
        )
        serie = pd.to_numeric(
            df[coluna],
            errors="coerce",
        )
        df_plot[rotulo] = serie
        nomes_series.append(
            (
                rotulo,
                variavel,
            )
        )
        valores_base.append(
            serie
        )

    serie_conjunta = pd.concat(
        valores_base,
        ignore_index=True,
    )

    unidade_final = unidade_original
    fator_visual = 1.0

    if len(unidades) == 1:
        unidade_final, fator_visual = obter_escala_visual(
            serie_conjunta,
            unidade_original,
        )

    for rotulo, _variavel in nomes_series:
        df_plot[rotulo] = df_plot[rotulo] * fator_visual

    indice_atual, tempo_atual = _tempo_atual(
        df_plot,
        frame_index,
    )

    fig = go.Figure()

    for rotulo, variavel in nomes_series:
        fase = str(
            variavel.get("fase") or ""
        ).upper()
        cor = CORES_FASES.get(
            fase,
            None,
        )

        fig.add_trace(
            go.Scatter(
                x=df_plot["Tempo"],
                y=df_plot[rotulo],
                mode="lines",
                name=rotulo,
                line={
                    "width": 2.4,
                    **({"color": cor} if cor else {}),
                },
                hovertemplate=(
                    "%{fullData.name}<br>Tempo: %{x}<br>Valor: %{y:.6g}"
                    "<extra></extra>"
                ),
            )
        )

    if indice_atual is not None and tempo_atual is not None:
        fig.add_shape(
            type="line",
            x0=tempo_atual,
            x1=tempo_atual,
            y0=0,
            y1=1,
            xref="x",
            yref="paper",
            line={
                "color": "#111827",
                "width": 2,
                "dash": "dash",
            },
        )
        fig.add_annotation(
            x=tempo_atual,
            y=1,
            xref="x",
            yref="paper",
            text="Instante do grafo",
            showarrow=False,
            yanchor="bottom",
            font={
                "color": "#111827",
                "size": 12,
            },
        )

        for rotulo, variavel in nomes_series:
            valor = df_plot[rotulo].iloc[indice_atual]

            if pd.isna(valor):
                continue

            fase = str(
                variavel.get("fase") or ""
            ).upper()
            cor = CORES_FASES.get(
                fase,
                "#111827",
            )

            fig.add_trace(
                go.Scatter(
                    x=[tempo_atual],
                    y=[valor],
                    mode="markers",
                    name=f"{rotulo} no instante",
                    marker={
                        "color": cor,
                        "size": 9,
                        "line": {
                            "color": "#ffffff",
                            "width": 1.5,
                        },
                    },
                    showlegend=False,
                    hovertemplate=(
                        "%{y:.6g}"
                        "<extra>Instante do grafo</extra>"
                    ),
                )
            )

    label_y = "Tensão"

    if unidade_final:
        label_y = f"Tensão [{unidade_final}]"

    if unidade_final == "pu":
        aplicar_faixas_prodist_temporal(
            fig,
            pd.concat(
                [df_plot[rotulo] for rotulo, _ in nomes_series],
                ignore_index=True,
            ),
        )

    fig.update_layout(
        title="Tensões do barramento selecionado",
        xaxis_title="Tempo",
        yaxis_title=label_y,
        hovermode="x unified",
        template="plotly_white",
        margin={
            "l": 20,
            "r": 20,
            "t": 54,
            "b": 20,
        },
        legend={
            "orientation": "h",
            "yanchor": "bottom",
            "y": 1.02,
            "xanchor": "left",
            "x": 0,
        },
    )

    st.plotly_chart(
        fig,
        use_container_width=True,
        key=f"{key_prefix}_grafico",
    )

    if indice_atual is None:
        return

    valores_instante = []

    for rotulo, _variavel in nomes_series:
        valores_instante.append(
            {
                "Série": rotulo,
                "Valor no instante": _formatar_valor(
                    df_plot[rotulo].iloc[indice_atual],
                    unidade_final,
                ),
            }
        )

    with st.expander(
        "Valores no instante do grafo",
        expanded=False,
    ):
        st.dataframe(
            pd.DataFrame(valores_instante),
            use_container_width=True,
            hide_index=True,
        )