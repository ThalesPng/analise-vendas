"""
utils.py — helpers compartilhados pelos relatórios (sem I/O): agrupamento de itens,
datas do período, conversão de hora e faixas de minutos. Só entra aqui o que é usado
por mais de uma aba.
"""

from datetime import datetime, timedelta

import config as cfg


def agrupar(itens, por):
    """Soma os itens por 'produto' ou 'departamento'.
    Retorna {cod: {"nome", "valor", "qtde"}}. Em departamento a qtde é None
    (somaria unidades diferentes, como UN e KG)."""
    grupos = {}
    for i in itens:
        if por == "produto":
            cod, nome = i["cod"], i.get("descricao") or ""
        else:
            cod, nome = i.get("cod_depart") or cfg.DEPTO_SEM, i.get("departamento") or ""
        g = grupos.setdefault(cod, {"nome": "", "valor": 0.0,
                                    "qtde": 0.0 if por == "produto" else None})
        g["valor"] += i["valor_total"]
        if g["qtde"] is not None:
            g["qtde"] += i.get("qtde", 0.0)
        g["nome"] = g["nome"] or nome
    for g in grupos.values():
        g["valor"] = round(g["valor"], 2)
        if g["qtde"] is not None:
            g["qtde"] = round(g["qtde"], 4)
    return grupos


def dias_entre(ini, fim):
    """Datas DD-MM-AAAA de `ini` a `fim`, inclusive e em ordem cronológica.
    Lista vazia se `fim` for anterior a `ini`."""
    d0 = datetime.strptime(ini, cfg.FMT_DATA)
    d1 = datetime.strptime(fim, cfg.FMT_DATA)
    return [(d0 + timedelta(days=n)).strftime(cfg.FMT_DATA)
            for n in range((d1 - d0).days + 1)]


def agrupar_por_dia(itens):
    """Separa os itens pelo dia da venda. Retorna {data DD-MM-AAAA: [itens]}
    (só os dias que têm itens)."""
    por_dia = {}
    for i in itens:
        por_dia.setdefault(i.get("data"), []).append(i)
    return por_dia


def min_hora(txt):
    """'HH:MM' -> minutos desde 00:00."""
    h, m = txt.split(":")
    return int(h) * 60 + int(m)


def hora_min(n):
    """Minutos desde 00:00 -> 'HH:MM'."""
    return f"{n // 60:02d}:{n % 60:02d}"


def faixa(minuto, passo, origem=0):
    """Minuto em que começa a faixa de `passo` minutos que contém `minuto`
    (faixas contadas a partir de `origem`; minuto >= origem)."""
    return origem + (minuto - origem) // passo * passo
