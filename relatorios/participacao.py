"""
participacao.py — relatório da aba Participação: percentual de cada produto ou
departamento no total arrecadado (sem I/O). Recebe os grupos de utils.agrupar().
"""


def _ordenar(grupos):
    return sorted(grupos.items(), key=lambda p: (-p[1]["valor"], p[0]))


def participacao(grupos):
    """Percentual de cada código no total arrecadado.
    Retorna (total, [(cod, valor, percentual), ...]) do maior para o menor."""
    total = round(sum(g["valor"] for g in grupos.values()), 2)
    itens = [(cod, g["valor"], round(g["valor"] / total * 100, 2) if total else 0.0)
             for cod, g in _ordenar(grupos)]
    return total, itens
