import re


def friendly_dss_error(msg):

    if "(#266)" in msg:

        match = re.search(
            r'"([^"]+)"',
            msg
        )

        element = (
            match.group(1)
            if match
            else "Elemento desconhecido"
        )

        return (
            "Circuito não compilado.\n\n"
            "Foi encontrado um elemento duplicado.\n\n"
            f"Elemento: {element}\n\n"
            "Verifique os arquivos DSS."
        )

    return msg