import tempfile
import zipfile
import re
import os

from pathlib import Path

import opendssdirect as dss


# =====================================================
# EXTRAÇÃO DO ZIP
# =====================================================

def extract_zip(zip_file):

    temp_dir = tempfile.mkdtemp()

    with zipfile.ZipFile(
        zip_file,
        "r"
    ) as z:

        z.extractall(temp_dir)

    return Path(temp_dir)


# =====================================================
# LOCALIZAÇÃO DO ARQUIVO PRINCIPAL
# =====================================================

def find_master(root):

    dss_files = list(
        root.rglob("*.dss")
    )

    if not dss_files:

        raise FileNotFoundError(
            "Nenhum arquivo .dss encontrado."
        )

    # Prioridade 1:
    # arquivos contendo "master"

    master_candidates = [

        f for f in dss_files

        if "master" in f.name.lower()

    ]

    if master_candidates:

        return sorted(
            master_candidates,
            key=lambda x: len(x.name)
        )[0]

    # Prioridade 2:
    # arquivos contendo "main"

    main_candidates = [

        f for f in dss_files

        if "main" in f.name.lower()

    ]

    if main_candidates:

        return sorted(
            main_candidates,
            key=lambda x: len(x.name)
        )[0]

    # Prioridade 3:
    # existe apenas um DSS

    if len(dss_files) == 1:

        return dss_files[0]

    # Prioridade 4:
    # maior arquivo DSS

    return max(
        dss_files,
        key=lambda f: f.stat().st_size
    )


# =====================================================
# REMOÇÃO DE COMANDOS GRÁFICOS
# =====================================================

def sanitize_master(master_file):

    content = master_file.read_text(
        encoding="latin1"
    )

    patterns = [
        r"^\s*show\b.*$",
        r"^\s*plot\b.*$",
    ]

    clean_lines = []

    for line in content.splitlines():

        remove = False

        for pattern in patterns:

            if re.match(
                pattern,
                line,
                re.IGNORECASE
            ):

                remove = True
                break

        if not remove:

            clean_lines.append(line)

    sanitized = (
        master_file.parent
        / "_master_clean.dss"
    )

    sanitized.write_text(
        "\n".join(clean_lines),
        encoding="latin1"
    )

    return sanitized


# =====================================================
# COMPILAÇÃO
# =====================================================

def compile_circuit(zip_file):

    original_cwd = os.getcwd()

    root = extract_zip(
        zip_file
    )

    original_master = find_master(
        root
    )

    sanitized_master = sanitize_master(
        original_master
    )

    dss.Basic.ClearAll()

    warning_message = None

    try:

        dss.Text.Command(
            f'Compile "{sanitized_master}"'
        )

    except Exception as e:

        warning_message = str(e)

    finally:

        os.chdir(
            original_cwd
        )

    buses = []

    try:

        buses = dss.Circuit.AllBusNames()

    except Exception:

        pass

    if len(buses) == 0:

        raise RuntimeError(
            warning_message
            or
            "O OpenDSS não conseguiu compilar o circuito."
        )

    return {
        "dss": dss,
        "master_file": original_master.name,
        "warning": warning_message,
    }