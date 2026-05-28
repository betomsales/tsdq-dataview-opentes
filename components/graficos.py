import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from utils.prodist import (
    obter_limites_prodist
)


CORES_PRODIST = {
    "critico": "rgba(231, 76, 60, 0.14)",
    "precario": "rgba(243, 156, 18, 0.18)",
    "adequado": "rgba(46, 204, 113, 0.13)",
}


def montar_linhas_limite_prodist(limites):
    """
    Agrupa limites coincidentes para evitar linhas sobrepostas.
    """

    linhas_base = [
        (
            limites["critico_min"],
            "Limite crítico inf.",
            "#c0392b",
            "dot",
            "inf"
        ),
        (
            limites["adequado_min"],
            "Limite inf. PRODIST",
            "#e67e22",
            "dash",
            "inf"
        ),
        (
            limites["adequado_max"],
            "Limite sup. PRODIST",
            "#e67e22",
            "dash",
            "sup"
        ),
        (
            limites["critico_max"],
            "Limite crítico sup.",
            "#c0392b",
            "dot",
            "sup"
        ),
    ]

    grupos = []

    for valor, rotulo, cor, dash, lado in linhas_base:

        grupo_existente = None

        for grupo in grupos:

            if abs(grupo["valor"] - valor) < 1e-9:

                grupo_existente = grupo
                break

        if grupo_existente is None:

            grupos.append(
                {
                    "valor": valor,
                    "rotulos": [rotulo],
                    "cor": cor,
                    "dash": dash,
                    "lado": lado,
                    "tem_critico": "crítico" in rotulo,
                }
            )

        else:

            grupo_existente["rotulos"].append(
                rotulo
            )

            grupo_existente["tem_critico"] = (
                grupo_existente["tem_critico"]
                or
                "crítico" in rotulo
            )

    linhas = []

    for grupo in grupos:

        if len(grupo["rotulos"]) > 1:

            rotulo = (
                "Limite inf. PRODIST"
                if grupo["lado"] == "inf"
                else
                "Limite sup. PRODIST"
            )

        else:

            rotulo = grupo["rotulos"][0]

        cor = (
            "#c0392b"
            if grupo["tem_critico"]
            else
            grupo["cor"]
        )

        dash = (
            "dot"
            if grupo["tem_critico"]
            else
            grupo["dash"]
        )

        linhas.append(
            (
                grupo["valor"],
                rotulo,
                cor,
                dash
            )
        )

    return linhas


def eh_tensao_pu(variavel_info):
    """
    Verifica se a variavel permite aplicar limites PRODIST em pu.
    """

    return (
        variavel_info["tipo"] == "Tensão"
        and
        variavel_info.get(
            "unidade_detectada"
        ) == "pu"
    )


def eh_tensao(variavel_info):
    """
    Verifica se a variavel e uma tensao reconhecida.
    """

    return variavel_info["tipo"] == "Tensão"


def aplicar_faixas_prodist_temporal(
    fig,
    serie,
    limites=None
):
    """
    Adiciona zonas coloridas e linhas de limite PRODIST no eixo Y.
    """

    if limites is None:

        limites = obter_limites_prodist()

    serie = serie.dropna()

    if serie.empty:
        return

    y_min = min(
        float(serie.min()),
        limites["critico_min"]
    )

    y_max = max(
        float(serie.max()),
        limites["critico_max"]
    )

    bandas = [
        (
            y_min,
            limites["critico_min"],
            CORES_PRODIST["critico"],
            "Crítico inferior"
        ),
        (
            limites["critico_min"],
            limites["adequado_min"],
            CORES_PRODIST["precario"],
            "Precário inferior"
        ),
        (
            limites["adequado_min"],
            limites["adequado_max"],
            CORES_PRODIST["adequado"],
            "Adequado"
        ),
        (
            limites["adequado_max"],
            limites["critico_max"],
            CORES_PRODIST["precario"],
            "Precário superior"
        ),
        (
            limites["critico_max"],
            y_max,
            CORES_PRODIST["critico"],
            "Crítico superior"
        ),
    ]

    for y0, y1, cor, _ in bandas:

        if y1 > y0:

            fig.add_hrect(
                y0=y0,
                y1=y1,
                fillcolor=cor,
                layer="below",
                line_width=0
            )

    linhas = montar_linhas_limite_prodist(
        limites
    )

    for y, rotulo, cor, dash in linhas:

        fig.add_hline(
            y=y,
            line_dash=dash,
            line_color=cor,
            annotation_text=rotulo
        )


def render_grafico_individual(
    df_plot,
    coluna_real,
    label_grafico,
    variavel_info,
    mostrar_limites_prodist=True,
    limites_prodist=None
):
    """
    Renderiza grafico individual.
    """

    fig = px.line(
        df_plot,
        x="Tempo",
        y="Valor",
        title=coluna_real
    )

    if (
        mostrar_limites_prodist
        and
        eh_tensao(
            variavel_info
        )
    ):

        aplicar_faixas_prodist_temporal(
            fig,
            df_plot["Valor"],
            limites_prodist
        )

    fig.update_layout(

        xaxis_title="Tempo",

        yaxis_title=label_grafico,

        hovermode="x unified"
    )

    st.subheader(
        "Série Temporal"
    )

    st.plotly_chart(
        fig,
        use_container_width=True
    )


def render_grafico_multiserie(
    df_multiserie,
    label_grafico,
    variavel_info,
    mostrar_limites_prodist=True,
    limites_prodist=None
):
    """
    Renderiza grafico multivariavel.
    """

    colunas_plot = [

        coluna

        for coluna in df_multiserie.columns

        if coluna != "Tempo"
    ]

    fig_multiserie = px.line(
        df_multiserie,
        x="Tempo",
        y=colunas_plot
    )

    if (
        mostrar_limites_prodist
        and
        eh_tensao(
            variavel_info
        )
    ):

        aplicar_faixas_prodist_temporal(
            fig_multiserie,
            df_multiserie[colunas_plot].stack(),
            limites_prodist
        )

    fig_multiserie.update_layout(

        title="Visualização conjunta",

        xaxis_title="Tempo",

        yaxis_title=label_grafico,

        hovermode="x unified"
    )

    st.subheader(
        "Visualização conjunta"
    )

    st.plotly_chart(
        fig_multiserie,
        use_container_width=True
    )


def render_grafico_distribuicao_tensao(
    df_tensoes,
    label_grafico,
    mostrar_limites_prodist=True,
    limites_prodist=None
):
    """
    Renderiza histogramas de distribuicao de tensao por fase/serie.
    """

    colunas_plot = [

        coluna

        for coluna in df_tensoes.columns

        if coluna != "Tempo"
    ]

    if not colunas_plot:
        return

    limites = None

    if mostrar_limites_prodist:

        limites = limites_prodist or obter_limites_prodist()

    fig = make_subplots(
        rows=len(colunas_plot),
        cols=1,
        shared_xaxes=True,
        subplot_titles=colunas_plot,
        vertical_spacing=0.13
    )

    for indice, coluna in enumerate(colunas_plot, start=1):

        serie = df_tensoes[coluna].dropna()

        if serie.empty:
            continue

        valor_min = float(
            serie.min()
        )

        valor_max = float(
            serie.max()
        )

        if limites is None:

            x_min = valor_min
            x_max = valor_max

        else:

            x_min = min(
                valor_min,
                limites["critico_min"]
            )

            x_max = max(
                valor_max,
                limites["critico_max"]
            )

        if mostrar_limites_prodist:

            bandas = [
                (
                    x_min,
                    limites["critico_min"],
                    CORES_PRODIST["critico"]
                ),
                (
                    limites["critico_min"],
                    limites["adequado_min"],
                    CORES_PRODIST["precario"]
                ),
                (
                    limites["adequado_min"],
                    limites["adequado_max"],
                    CORES_PRODIST["adequado"]
                ),
                (
                    limites["adequado_max"],
                    limites["critico_max"],
                    CORES_PRODIST["precario"]
                ),
                (
                    limites["critico_max"],
                    x_max,
                    CORES_PRODIST["critico"]
                ),
            ]

            for x0, x1, cor in bandas:

                if x1 > x0:

                    fig.add_vrect(
                        x0=x0,
                        x1=x1,
                        fillcolor=cor,
                        layer="below",
                        line_width=0,
                        row=indice,
                        col=1
                    )

            linhas = montar_linhas_limite_prodist(
                limites
            )

            for x, _, cor, dash in linhas:

                fig.add_vline(
                    x=x,
                    line_color=cor,
                    line_dash=dash,
                    row=indice,
                    col=1
                )

        if valor_min == valor_max:

            largura_barra = max(
                (x_max - x_min) * 0.012,
                0.002
            )

            fig.add_trace(
                go.Bar(
                    x=[valor_min],
                    y=[len(serie)],
                    width=[largura_barra],
                    name=coluna,
                    opacity=0.85,
                    showlegend=False,
                    hovertemplate=(
                        "%{y} leituras em "
                        f"{valor_min:.5f}"
                        "<extra></extra>"
                    )
                ),
                row=indice,
                col=1
            )

        else:

            tamanho_bin = max(
                (valor_max - valor_min) / 60,
                0.002
            )

            fig.add_trace(
                go.Histogram(
                    x=serie,
                    name=coluna,
                    xbins=dict(
                        start=valor_min,
                        end=valor_max + tamanho_bin,
                        size=tamanho_bin
                    ),
                    opacity=0.85,
                    showlegend=False,
                    hovertemplate=(
                        "%{y} leituras em %{x:.5f}"
                        "<extra></extra>"
                    )
                ),
                row=indice,
                col=1
            )

        fig.update_yaxes(
            title_text="Freq.",
            row=indice,
            col=1
        )

    fig.update_xaxes(
        title_text=label_grafico,
        row=len(colunas_plot),
        col=1
    )

    fig.update_layout(
        title="Distribuição de tensão por fase",
        height=280 * len(colunas_plot) + 120,
        margin=dict(
            l=60,
            r=40,
            t=80,
            b=60
        ),
        template="plotly_white",
        bargap=0.03
    )

    st.subheader(
        "Distribuição de tensão por fase"
    )

    st.plotly_chart(
        fig,
        use_container_width=True
    )
