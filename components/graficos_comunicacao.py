"""Figuras Plotly e componentes visuais exclusivos da Comunicacao."""

import math

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from components.identidade import style_plotly_figure


CORES = ["#2E8963", "#176BBD", "#D58220", "#BB4343", "#8D62A8", "#177F89"]
ROTULOS = {"NodeId": "Nó receptor", "Agente": "Remetente", "Tecnologia": "Tecnologia do enlace", "Camada": "Camada"}


def _layout(fig, title, **kwargs):
    fig.update_layout(
        template="plotly_white", title={"text": title, "font": {"size": 16}},
        height=390, margin={"l": 30, "r": 25, "t": 65, "b": 65},
        colorway=CORES, legend={"orientation": "h", "y": -0.22}, **kwargs,
    )
    return style_plotly_figure(fig)


def render_figura(fig, key):
    st.plotly_chart(fig, key=key, theme=None, use_container_width=True)


def _sem_amostras(fig, values):
    if not values.notna().any():
        fig.add_annotation(text="Sem amostras válidas no recorte", x=.5, y=.5,
                           xref="paper", yref="paper", showarrow=False)
    return fig


def _format(value, suffix="", scale=1, decimals=2):
    return f"{value * scale:,.{decimals}f}{suffix}" if pd.notna(value) and math.isfinite(value) else "N/D"


def render_cards_comunicacao(kpis):
    rows = [
        [("Pacotes enviados", "pacotes_enviados", "", 1, 0), ("Pacotes recebidos", "pacotes_recebidos", "", 1, 0),
         ("Pacotes descartados", "pacotes_dropados", "", 1, 0), ("PDR global", "pdr", "%", 1, 1)],
        [("Taxa de descarte", "taxa_drop", "%", 1, 1), ("Latência média", "latencia_media", " ms", 1000, 2),
         ("Latência P95", "latencia_p95", " ms", 1000, 2), ("Jitter médio", "jitter_medio", " µs", 1e6, 2)],
    ]
    for row in rows:
        for column, (label, key, suffix, scale, decimals) in zip(st.columns(4), row):
            column.metric(label, _format(kpis[key], suffix, scale, decimals))
    st.caption(f"{kpis['agentes']} nós com registros · {kpis['mensagens']} mensagens recebidas · "
               f"Payload médio: {_format(kpis['tamanho_medio'], ' bytes')} · "
               f"Encaminhados: {_format(kpis['pacotes_encaminhados'], decimals=0)}")


def criar_latencia(messages, group):
    fig = go.Figure()
    for index, (name, data) in enumerate(messages.groupby(group)):
        summary = data.groupby("Tempo")["Latencia"].agg(["mean", "min", "max"]).reset_index()
        if summary["mean"].notna().sum() == 0:
            continue
        color = CORES[index % len(CORES)]
        fig.add_trace(go.Scatter(x=summary.Tempo, y=summary["max"] * 1000, mode="lines", line={"width": 0},
                                 legendgroup=str(name), showlegend=False, hoverinfo="skip"))
        fig.add_trace(go.Scatter(x=summary.Tempo, y=summary["min"] * 1000, mode="lines", line={"width": 0},
                                 fill="tonexty", fillcolor=_alpha(color), legendgroup=str(name), showlegend=False, hoverinfo="skip"))
        fig.add_trace(go.Scatter(x=summary.Tempo, y=summary["mean"] * 1000, mode="lines+markers", marker_size=3,
                                 name=str(name), legendgroup=str(name), line_color=color, connectgaps=False))
    return _layout(_sem_amostras(fig, messages.Latencia), "Latência temporal<br><sup>Média e faixa mínima–máxima</sup>", xaxis_title="Tempo (s)", yaxis_title="Latência (ms)",
                   showlegend=messages[group].nunique() <= 10)


def _alpha(color):
    return "rgba(" + ",".join(str(int(color[index:index+2], 16)) for index in (1, 3, 5)) + ",0.12)"


def criar_payload(messages, group):
    summary = messages.groupby(group, as_index=False)["Tamanho do pacote"].mean()
    fig = px.bar(summary, x=group, y="Tamanho do pacote", color=group, color_discrete_sequence=CORES,
                 labels={**ROTULOS, "Tamanho do pacote": "Payload médio (bytes)"})
    return _layout(_sem_amostras(fig, messages["Tamanho do pacote"]), "Payload médio recebido", showlegend=False)


def criar_jitter(messages, group):
    data = messages.copy()
    data["Jitter (µs)"] = data["Jitter"] * 1e6
    fig = px.box(data, x="Jitter (µs)", y=group, color=group, points="outliers", color_discrete_sequence=CORES, labels=ROTULOS)
    fig = _layout(_sem_amostras(fig, messages.Jitter), "Distribuição de jitter", showlegend=False)
    fig.update_layout(height=max(390, min(1000, messages[group].nunique() * 25 + 110)))
    return fig


def criar_entrega(kpis):
    fig = go.Figure()
    if pd.notna(kpis["pdr"]):
        values = [("Entregues", kpis["pdr"], "#2E8963"), ("Descartados", kpis["taxa_drop"], "#BB4343"),
                  ("Sem desfecho registrado", 100 - kpis["pdr"] - kpis["taxa_drop"], "#899396")]
        for label, value, color in values:
            fig.add_trace(go.Bar(x=[value], y=["Execução"], name=label, orientation="h", marker_color=color,
                                 hovertemplate=label + ": %{x:.2f}%<extra></extra>"))
        fig.update_layout(barmode="stack", xaxis={"range": [0, 100], "ticksuffix": "%"})
        title = "Entrega e descarte globais"
    else:
        values = [("Enviados", kpis["pacotes_enviados"]), ("Recebidos", kpis["pacotes_recebidos"]), ("Descartados", kpis["pacotes_dropados"])]
        available = [(name, value) for name, value in values if pd.notna(value)]
        fig.add_trace(go.Bar(x=[item[0] for item in available], y=[item[1] for item in available], marker_color=CORES))
        title = "Contadores globais · percentuais indisponíveis"
    return _layout(fig, title)


def criar_mapa(messages, metadata, selected_nodes=None):
    fig = go.Figure()
    positions = {item["id"]: item for item in metadata.posicoes}
    technologies = sorted({link["tipo"] for link in metadata.links})
    for index, technology in enumerate(technologies):
        xs, ys = [], []
        for link in metadata.links:
            if link["tipo"] == technology and link["origem"] in positions and link["destino"] in positions:
                a, b = positions[link["origem"]], positions[link["destino"]]
                xs.extend([a["x"], b["x"], None]); ys.extend([a["y"], b["y"], None])
        fig.add_trace(go.Scatter(x=xs, y=ys, mode="lines", name=technology,
                                 line={"color": CORES[index % len(CORES)], "width": 1.8}, hoverinfo="name"))
    means = messages.groupby("NodeId")["Latencia"].mean() * 1000
    measured = [node for node in positions if node in means and pd.notna(means[node])]
    missing = [node for node in positions if node not in measured]
    for nodes, known in ((missing, False), (measured, True)):
        if not nodes:
            continue
        marker = {"size": [17 if selected_nodes and node in selected_nodes else 12 for node in nodes],
                  "line": {"width": 1, "color": "#23342D"}}
        if known:
            marker.update(color=[means[node] for node in nodes], colorscale="RdYlGn_r", showscale=True,
                          colorbar={"title": "Latência<br>média (ms)", "thickness": 12})
        else:
            marker.update(color="#CBD2CF")
        fig.add_trace(go.Scatter(
            x=[positions[node]["x"] for node in nodes], y=[positions[node]["y"] for node in nodes],
            mode="markers", text=nodes,
            marker=marker, name="Nós com medição" if known else "Sem medição no recorte",
            customdata=[[node, _format(means[node], ' ms') if known else 'Sem medição'] for node in nodes],
            hovertemplate="%{customdata[0]}<br>%{customdata[1]}<extra></extra>", showlegend=False,
        ))
    fig = _layout(fig, "Rede de comunicação<br><sup>Latência média fim a fim</sup>", xaxis_title="Coordenada X", yaxis_title="Coordenada Y")
    fig.update_layout(height=520, yaxis={"scaleanchor": "x", "scaleratio": 1}, uirevision="comunicacao-mapa")
    return fig


def criar_detalhe(messages, variable):
    data = messages.copy()
    scale, unit = {"Latencia": (1000, "ms"), "Jitter": (1e6, "µs"), "Tamanho do pacote": (1, "bytes")}[variable]
    data["Valor"] = data[variable] * scale
    title = {"Latencia": "Latência", "Jitter": "Jitter", "Tamanho do pacote": "Payload"}[variable]
    fig = px.scatter(data, x="Tempo", y="Valor", color="NodeId", color_discrete_sequence=CORES,
                     hover_data=["Agente", "Tecnologia", "Associação"], labels={**ROTULOS, "Valor": f"{title} ({unit})", "Tempo": "Tempo (s)"})
    return _layout(_sem_amostras(fig, data["Valor"]), f"{title} por mensagem recebida", showlegend=data.NodeId.nunique() <= 10)


def render_grafico_latencia(df_expandido):
    render_figura(criar_detalhe(df_expandido, "Latencia"), "comunicacao_detalhe_latencia")


def render_grafico_payload(df_expandido):
    render_figura(criar_detalhe(df_expandido, "Tamanho do pacote"), "comunicacao_detalhe_payload")


def render_grafico_jitter(df_expandido):
    render_figura(criar_detalhe(df_expandido, "Jitter"), "comunicacao_detalhe_jitter")


def render_grafico_confiabilidade(kpis):
    render_figura(criar_entrega(kpis), "comunicacao_entrega")


def render_tabela_mensagens(df_expandido):
    st.dataframe(df_expandido, hide_index=True, use_container_width=True)
