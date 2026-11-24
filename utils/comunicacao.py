"""Leitura e indicadores de comunicacao, sem dependencias da interface."""

import json
import math

import pandas as pd


COLUNAS_OBRIGATORIAS = ["Tempo", "Origem", "Atributo", "Valor"]
ATRIBUTOS_PACOTES = ["packets_sent", "packets_received", "packets_dropped"]
CONTADORES = ATRIBUTOS_PACOTES + ["packets_forwarded"]
COLUNAS_MENSAGENS = [
    "Tempo", "Origem", "NodeId", "Agente", "RemetenteId", "Mensagem",
    "Tamanho do pacote", "Latencia", "Jitter",
]


def ler_resultados_comunicacao(uploaded_file):
    uploaded_file.seek(0)
    df = pd.read_csv(uploaded_file, dtype=str, encoding="utf-8-sig")
    df.columns = df.columns.str.strip()
    for column in ("Origem", "Atributo"):
        if column in df:
            df[column] = df[column].str.strip()
    return df


def validar_resultados_comunicacao(df):
    missing = [column for column in COLUNAS_OBRIGATORIAS if column not in df]
    if missing:
        return ["Colunas obrigatórias ausentes: " + ", ".join(missing)]
    errors = []
    if df.empty:
        errors.append("O CSV não contém registros.")
    times = pd.to_numeric(df["Tempo"], errors="coerce")
    if not times.map(lambda value: pd.notna(value) and math.isfinite(value) and value >= 0).all():
        errors.append("Tempo deve conter segundos numéricos, finitos e não negativos.")
    for column in ("Origem", "Atributo"):
        if df[column].isna().any() or df[column].astype(str).str.strip().eq("").any():
            errors.append(f"{column} contém identificadores vazios.")
    normalized = df.assign(Tempo=times)
    if normalized.duplicated(["Tempo", "Origem", "Atributo"]).any():
        errors.append("Há registros duplicados para Tempo, Origem e Atributo; o carregamento foi interrompido para não descartar valores.")
    return errors


def listar_origens(df):
    return sorted(df["Origem"].dropna().astype(str).unique()) if "Origem" in df else []


def normalizar_agente(value):
    name = str(value).split("@", 1)[0].strip()
    if name == "AgenteCentral":
        return "agent_central"
    if name.startswith("AgenteP_"):
        return "agent_p_" + name[len("AgenteP_"):]
    return name


def preparar_tabela_temporal(df, origem=None):
    data = df.copy()
    data["Origem"] = data["Origem"].astype(str)
    data["Tempo"] = pd.to_numeric(data["Tempo"], errors="raise")
    if origem is not None:
        data = data[data["Origem"] == str(origem)]
    temporal = data.pivot(index=["Tempo", "Origem"], columns="Atributo", values="Valor").reset_index()
    temporal.columns.name = None
    temporal["NodeId"] = temporal["Origem"].map(lambda value: normalizar_agente(value.split(".", 1)[-1]))
    for column in CONTADORES:
        values = temporal[column] if column in temporal else pd.Series(float("nan"), index=temporal.index)
        numeric = pd.to_numeric(values, errors="coerce")
        temporal[column] = numeric.where(numeric.ge(0) & numeric.map(lambda value: pd.notna(value) and math.isfinite(value)))
    return temporal.sort_values(["Tempo", "Origem"]).reset_index(drop=True)


def extrair_remetente(mensagem):
    try:
        parsed = json.loads(mensagem)
    except (TypeError, ValueError):
        return "Não identificado"
    sender = parsed.get("sender") if isinstance(parsed, dict) else None
    return sender.split("@", 1)[0] if isinstance(sender, str) and sender.strip() else "Não identificado"


def _dividir_valores(value):
    return [] if pd.isna(value) or not str(value).strip() else str(value).split("|||")


def _valor_float(values, index):
    try:
        result = float(values[index])
        return result if math.isfinite(result) and result >= 0 else float("nan")
    except (IndexError, TypeError, ValueError):
        return float("nan")


def expandir_mensagens(time_data):
    records = []
    warnings = set()
    for row in time_data.to_dict("records"):
        messages = _dividir_valores(row.get("val_out"))
        signals = [_dividir_valores(row.get(column)) for column in ("packet_sizes_out", "latencies_out", "jitters_out")]
        if any(len(values) != len(messages) for values in signals):
            warnings.add("Listas de mensagens e telemetria têm comprimentos diferentes; itens sem correspondência não foram convertidos em zero.")
        for index, message in enumerate(messages):
            if not message.strip():
                warnings.add("Uma mensagem vazia foi ignorada, preservando os índices da telemetria.")
                continue
            sender = extrair_remetente(message)
            if sender == "Não identificado":
                warnings.add("Há mensagens sem remetente JSON identificável; não foi atribuída uma tecnologia a elas.")
            records.append({
                "Tempo": row["Tempo"], "Origem": row.get("Origem", ""),
                "NodeId": row.get("NodeId", ""), "Agente": sender,
                "RemetenteId": normalizar_agente(sender), "Mensagem": message,
                **{column: _valor_float(values, index) for column, values in zip(
                    ("Tamanho do pacote", "Latencia", "Jitter"), signals)},
            })
    result = pd.DataFrame(records, columns=COLUNAS_MENSAGENS)
    if result[["Tamanho do pacote", "Latencia", "Jitter"]].isna().any().any():
        warnings.add("Há amostras de tamanho, latência ou jitter ausentes ou inválidas; as estatísticas usam apenas valores válidos.")
    result.attrs["avisos"] = sorted(warnings)
    return result


def classificar_agente(agente):
    if agente == "AgenteCentral":
        return "Central"
    return "Periférico" if str(agente).startswith("AgenteP_") else "Rede"


def calcular_kpis(time_data, df_expandido):
    totals, warnings = {}, []
    for column in CONTADORES:
        series = time_data.groupby("Origem")[column]
        maxima = series.max()
        totals[column] = float(maxima.sum()) if len(maxima) and maxima.notna().all() else float("nan")
        if time_data[column].isna().any() and (column != "packets_forwarded" or time_data[column].notna().any()):
            warnings.append(f"{column}: contador ausente ou inválido em parte dos registros.")
        if (time_data.sort_values("Tempo").groupby("Origem")[column].diff() < 0).any():
            warnings.append(f"{column}: houve redução do contador acumulado; os máximos não reconstituem reinícios.")
    sent, received, dropped = (totals[column] for column in ATRIBUTOS_PACOTES)
    # Local send/receive counters concern different flows; ratios are global only.
    complete = all(time_data[column].notna().all() for column in ATRIBUTOS_PACOTES)
    consistent = complete and not any("redução" in warning for warning in warnings) and sent > 0 and received + dropped <= sent
    if complete and sent >= 0 and received + dropped > sent:
        warnings.append("Recebidos mais descartados excedem enviados; PDR e composição percentual estão indisponíveis, sem truncamento artificial.")
    return {
        "pacotes_enviados": sent, "pacotes_recebidos": received,
        "pacotes_dropados": dropped, "pacotes_encaminhados": totals["packets_forwarded"],
        "pacotes_em_transito": sent - received - dropped if consistent else float("nan"),
        "pdr": received / sent * 100 if consistent else float("nan"),
        "taxa_drop": dropped / sent * 100 if consistent else float("nan"),
        "mensagens": len(df_expandido), "agentes": time_data["Origem"].nunique(),
        "latencia_media": df_expandido["Latencia"].mean(),
        "latencia_maxima": df_expandido["Latencia"].max(),
        "latencia_p95": df_expandido["Latencia"].quantile(.95),
        "jitter_medio": df_expandido["Jitter"].mean(),
        "tamanho_medio": df_expandido["Tamanho do pacote"].mean(),
        "avisos": warnings,
    }


def tabela_comparativa(messages, group):
    return messages.groupby(group, dropna=False).agg(**{
        "Mensagens recebidas": ("Tempo", "size"),
        "Amostras de latência": ("Latencia", "count"),
        "Latência média (ms)": ("Latencia", lambda values: values.mean() * 1000),
        "Latência P95 (ms)": ("Latencia", lambda values: values.quantile(.95) * 1000),
        "Jitter médio (µs)": ("Jitter", lambda values: values.mean() * 1e6),
        "Payload médio (bytes)": ("Tamanho do pacote", "mean"),
    }).reset_index()
