import hashlib
from io import BytesIO

import pandas as pd
import streamlit as st

from components.identidade import BASE_DIR, apply_brand_style, render_page_header
from components.graficos_comunicacao import (
    criar_jitter, criar_latencia, criar_mapa, criar_payload, render_cards_comunicacao,
    render_figura, render_grafico_confiabilidade, render_grafico_jitter,
    render_grafico_latencia, render_grafico_payload, render_tabela_mensagens,
)
from utils.comunicacao import (
    calcular_kpis, expandir_mensagens, ler_resultados_comunicacao,
    preparar_tabela_temporal, tabela_comparativa, validar_resultados_comunicacao,
)
from utils.comunicacao_metadados import MetadadosComunicacao, ler_metadado


@st.cache_data(show_spinner=False, max_entries=3)
def processar_csv(content):
    data = ler_resultados_comunicacao(BytesIO(content))
    errors = validar_resultados_comunicacao(data)
    if errors:
        return data, None, None, errors
    temporal = preparar_tabela_temporal(data)
    return data, temporal, expandir_mensagens(temporal), []


st.set_page_config(page_title="Comunicação | ARGOS", page_icon=str(BASE_DIR / "imagens" / "logo.png"), layout="wide")
apply_brand_style(workspace=True)
render_page_header("Comunicação", "MENSAGENS E DESEMPENHO", "Mensagens, latência, jitter e confiabilidade da comunicação na co-simulação.")

uploaded = st.file_uploader("Resultados de comunicação (CSV)", type=["csv"], key="comunicacao_csv")
if uploaded is None:
    st.info("Nenhum resultado de comunicação carregado.")
    st.stop()

content = uploaded.getvalue()
dataset_id = hashlib.sha256(content).hexdigest()[:12]
try:
    raw, temporal, messages, errors = processar_csv(content)
except (ValueError, UnicodeError, pd.errors.EmptyDataError) as error:
    st.error(f"Não foi possível ler o CSV: {error}")
    st.stop()
if errors:
    for error in errors:
        st.error(error)
    st.dataframe(raw.head(20), use_container_width=True)
    st.stop()

metadata = MetadadosComunicacao()
warnings = list(messages.attrs.get("avisos", []))
with st.expander("Metadados da comunicação (opcionais)"):
    columns = st.columns(3)
    for column, kind, title in zip(columns, ("config", "links", "posicoes"),
                                   ("Configuração · config.json", "Enlaces · links.json", "Coordenadas · posicoes.json")):
        with column:
            file = st.file_uploader(title, type=["json"], key=f"comunicacao_{kind}_{dataset_id}")
            if file is not None:
                try:
                    setattr(metadata, kind, ler_metadado(file.getvalue(), kind))
                except (ValueError, UnicodeError) as error:
                    warnings.append(f"{file.name}: {error} Esse metadado não foi aplicado.")

messages = metadata.associar(messages)
kpis = calcular_kpis(temporal, messages)
warnings.extend(kpis["avisos"])
warnings.extend(metadata.diagnosticar(temporal, messages))

st.subheader("Indicadores globais da execução")
if isinstance(metadata.config.get("topologia"), str):
    st.caption("Topologia declarada: " + metadata.config["topologia"])
render_cards_comunicacao(kpis)
with st.expander("Critérios e diagnóstico dos dados", expanded=bool(warnings)):
    st.caption("Período completo do CSV. Contadores acumulados: máximo por nó, somado entre nós. "
               "PDR global = recebidos / enviados; descarte = descartados / enviados. "
               "O saldo sem desfecho registrado não comprova trânsito físico. "
               "Latência e jitter de entrada em segundos; apresentação em ms e µs. Payload em bytes.")
    st.caption("Os metadados de comunicação não possuem verificação criptográfica de vínculo com este CSV. "
               "As associações usam identificadores e enlaces declarados, não a topologia elétrica.")
    for warning in dict.fromkeys(warnings):
        st.warning(warning)

overview, detail, processed = st.tabs(["Painel comparativo", "Mensagens", "Dados processados"])

st_filter_key = "comunicacao_filtro_" + dataset_id
with overview:
    left, middle, right = st.columns(3)
    receivers = sorted(temporal.NodeId.unique())
    with left:
        all_nodes = st.toggle("Todos os nós receptores", value=True, key=st_filter_key + "todos_nos")
        selected_nodes = receivers if all_nodes else st.multiselect("Nós receptores", receivers, key=st_filter_key + "nos")
    with middle:
        technologies = sorted(messages.Tecnologia.unique())
        selected_technologies = st.multiselect("Tecnologias dos enlaces", technologies, default=technologies, key=st_filter_key + "tecnologias")
    with right:
        groups = {"Nó receptor": "NodeId", "Remetente": "Agente"}
        if metadata.links:
            groups["Tecnologia do enlace / último salto estimado"] = "Tecnologia"
        if metadata.posicoes:
            groups["Camada declarada"] = "Camada"
        group_label = st.selectbox("Comparação por", list(groups), key=st_filter_key + "grupo")
    group = groups[group_label]
    filtered = messages[messages.NodeId.isin(selected_nodes) & messages.Tecnologia.isin(selected_technologies)]
    st.caption(f"{len(filtered)} mensagens no recorte · indicadores e entrega globais referentes à execução completa")
    a, b = st.columns(2)
    with a:
        if not filtered.empty:
            render_figura(criar_latencia(filtered, group), "comunicacao_media_latencia")
            render_figura(criar_jitter(filtered, group), "comunicacao_boxplot_jitter")
        else:
            st.info("Nenhuma mensagem recebida no recorte selecionado.")
    with b:
        if not filtered.empty:
            render_figura(criar_payload(filtered, group), "comunicacao_media_payload")
        render_grafico_confiabilidade(kpis)
    if not filtered.empty:
        st.subheader("Comparativo de desempenho")
        table = tabela_comparativa(filtered, group).rename(columns={group: group_label})
        st.dataframe(table, hide_index=True, use_container_width=True)
    if metadata.posicoes:
        render_figura(criar_mapa(filtered, metadata, selected_nodes), "comunicacao_mapa")

with detail:
    if filtered.empty:
        st.info("Sem mensagens no recorte selecionado.")
    else:
        a, b = st.columns(2)
        with a:
            render_grafico_latencia(filtered)
            render_grafico_payload(filtered)
        with b:
            render_grafico_jitter(filtered)
        render_tabela_mensagens(filtered)

with processed:
    st.subheader("Contadores acumulados por nó")
    counters = temporal.groupby(["Origem", "NodeId"], as_index=False)[
        ["packets_sent", "packets_received", "packets_dropped", "packets_forwarded"]
    ].max().rename(columns={"packets_sent": "Enviados", "packets_received": "Recebidos",
                           "packets_dropped": "Descartados", "packets_forwarded": "Encaminhados"})
    st.dataframe(counters, hide_index=True, use_container_width=True)
    with st.expander("Mensagens e associações do período completo"):
        render_tabela_mensagens(messages)
    with st.expander("Tabela temporal por origem"):
        st.dataframe(temporal, hide_index=True, use_container_width=True)
    with st.expander("Registros originais"):
        st.dataframe(raw, hide_index=True, use_container_width=True)
