"""
formato.py — helpers puros da interface: formatação e leitura de datas, horas e valores.
Sem Tkinter: só texto entra e texto sai.
"""

from datetime import datetime

import config as cfg


def hoje():
    return datetime.now().strftime(cfg.FMT_DATA)


def brl(v):
    return "R$ " + f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def pct(v):
    return f"{v:.2f}".replace(".", ",") + "%"


def parse_data(txt):
    """'' = hoje; aceita DD-MM-AAAA, DD/MM/AAAA e DD/MM. None se inválida."""
    txt = txt.strip().replace("/", "-")
    if not txt:
        return hoje()
    if txt.count("-") == 1:
        txt += f"-{datetime.now().year}"
    try:
        return datetime.strptime(txt, cfg.FMT_DATA).strftime(cfg.FMT_DATA)
    except ValueError:
        return None


def dkey(data):
    """DD-MM-AAAA -> datetime (para comparar datas)."""
    return datetime.strptime(data, cfg.FMT_DATA)


def parse_hora(txt):
    """Aceita HH:MM, HH, H:MM e 14h30. None se inválida."""
    txt = txt.strip().lower().replace("h", ":").rstrip(":")
    if ":" not in txt:
        txt += ":00"
    try:
        return datetime.strptime(txt, "%H:%M").strftime("%H:%M")
    except ValueError:
        return None


def qtde(v):
    """Quantidade com até 3 casas, vírgula decimal, sem zeros sobrando."""
    txt = f"{v:,.3f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return txt.rstrip("0").rstrip(",")


def nome_dia(n):
    return cfg.DIAS_SEMANA[n]


def rotulo(cod, nomes):
    """Só o nome do produto/departamento — a interface não mostra códigos."""
    nome = nomes.get(cod)
    if nome:
        return nome
    return "Sem departamento" if cod == cfg.DEPTO_SEM else "Sem nome"
