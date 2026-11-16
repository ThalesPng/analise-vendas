"""
vendas.py — contagem de vendas (sem I/O: nada de banco, tela ou arquivo).

Os itens normalizados (ver banco) trazem "id_venda": todos os itens de uma mesma venda
têm o mesmo valor. Contar vendas é contar esses identificadores distintos. Como todos
os itens de uma venda têm a mesma data e hora, filtrar itens por data/hora nunca corta
uma venda ao meio. A contagem usa as mesmas vendas dos relatórios de valor (as que a
fonte considera válidas), então número de vendas e valor sempre batem.
"""

from datetime import datetime

import config as cfg


def id_venda(item):
    """Identificador da venda do item. Erro (em vez de contar a menos em silêncio) se
    o item não trouxer "id_venda"."""
    idv = item.get("id_venda")
    if not idv:
        raise ValueError("item sem id_venda: não dá para identificar a venda")
    return idv


def contar_vendas(itens):
    """Quantidade de vendas distintas entre os itens (0 se não houver itens)."""
    return len({id_venda(i) for i in itens})


def contar_vendas_periodo(fonte, data_ini, data_fim=None, hora_ini=None, hora_fim=None):
    """Quantidade de vendas de data_ini a data_fim (DD-MM-AAAA, inclusive), e só da faixa
    hora_ini a hora_fim (HH:MM, inclusive, por minuto) de cada dia, se houver. Mesma
    assinatura de historico_vendas: a `fonte` é chamada UMA vez para o período inteiro.
    Erros de coleta propagam."""
    data_fim = data_fim or data_ini
    if datetime.strptime(data_fim, cfg.FMT_DATA) < datetime.strptime(data_ini, cfg.FMT_DATA):
        raise ValueError("data_fim anterior a data_ini")
    return contar_vendas(fonte(data_ini, data_fim, hora_ini, hora_fim))
