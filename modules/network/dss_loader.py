import tempfile
import zipfile
import re

from pathlib import Path

import opendssdirect as dss


def extract_zip(zip_file):

    temp_dir = tempfile.mkdtemp()

    with zipfile.ZipFile(
        zip_file,
        "r"
    ) as z:

        z.extractall(temp_dir)

    return Path(temp_dir)


def find_master(root):

    masters = list(
        root.rglob("master.dss")
    )

    if not masters:

        raise FileNotFoundError(
            "master.dss não encontrado"
        )

    return masters[0]


def sanitize_master(master_file):

    content = master_file.read_text(
        encoding="latin1"
    )

    patterns = [
        r"^\s*show\b.*$",
        r"^\s*plot\b.*$",
    ]

    lines = content.splitlines()

    clean_lines = []

    for line in lines:

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

    sanitized = master_file.parent / "_master_clean.dss"

    sanitized.write_text(
        "\n".join(clean_lines),
        encoding="latin1"
    )

    return sanitized

def compile_circuit(zip_file):

    root = extract_zip(zip_file)

    master = find_master(root)

    master = sanitize_master(master)

    dss.Basic.ClearAll()

    dss.Text.Command(
        f'Compile "{master}"'
    )

    return dss