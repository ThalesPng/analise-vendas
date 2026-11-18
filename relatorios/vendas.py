"""
vendas.py — identificação da venda de cada item (sem I/O: nada de banco, tela ou arquivo).

Os itens normalizados (ver banco) trazem "id_venda": todos os itens de uma mesma venda
têm o mesmo valor. A projeção usa isso para contar vendas (ids distintos). Como todos os
itens de uma venda têm a mesma data e hora, filtrar itens por data/hora nunca corta uma
venda ao meio, e a contagem usa as mesmas vendas dos relatórios de valor (as que a fonte
considera válidas): número de vendas e valor sempre batem.
"""


def id_venda(item):
    """Identificador da venda do item. Erro (em vez de contar a menos em silêncio) se
    o item não trouxer "id_venda"."""
    idv = item.get("id_venda")
    if not idv:
        raise ValueError("item sem id_venda: não dá para identificar a venda")
    return idv
