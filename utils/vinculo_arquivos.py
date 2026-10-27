"""Leitura e verificação do vínculo SHA-256 entre a topologia e os resultados."""

import hashlib
import json


def calcular_sha256_upload(uploaded_file):
    uploaded_file.seek(0)
    try:
        return hashlib.sha256(uploaded_file.read()).hexdigest().upper()
    finally:
        uploaded_file.seek(0)


def carregar_json_upload(uploaded_file):
    uploaded_file.seek(0)
    try:
        raw = uploaded_file.read()
    finally:
        uploaded_file.seek(0)
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8-sig")
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("O JSON de topologia deve ter um objeto na raiz.")
    return data


def obter_hash_vinculado(topology_data):
    metadata = topology_data.get("metadata")
    metadata = metadata if isinstance(metadata, dict) else {}
    containers = (metadata, metadata.get("hash"), topology_data, topology_data.get("hash"))
    for container in containers:
        if not isinstance(container, dict):
            continue
        for key in ("results_sha256", "csv_sha256", "sha256"):
            value = container.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip().upper()
    return ""


def validar_vinculo(topology_data, results_hash):
    expected = obter_hash_vinculado(topology_data)
    if not expected:
        raise ValueError(
            "Topologia sem vínculo SHA-256 com o arquivo CSV. Solicite à equipe "
            "da co-simulação um JSON com results_sha256 na raiz ou campo legado equivalente."
        )
    if expected != str(results_hash).strip().upper():
        raise ValueError("Vínculo inválido: o hash do CSV carregado não corresponde ao hash registrado na topologia.")
    return expected
