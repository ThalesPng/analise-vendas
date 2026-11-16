"""
banco.py — ÚNICO ponto de acesso a dados do relatório de vendas.

Daqui sai apenas FONTE_PADRAO(data_ini, data_fim, hora_ini, hora_fim), que devolve
itens normalizados de TODOS os caixas (hora_ini/hora_fim None = sem filtro).
Quem chama não precisa saber de conexão, SQL ou XML.

Item normalizado (o ÚNICO contrato entre este módulo e o resto):
    {"cod": "1180", "descricao": "BOLO DE CENOURA", "qtde": 1.0,
     "valor_total": 22.45, "cod_depart": "7", "departamento": "CONFEITARIA",
     "data": "09-11-2026", "hora": "09:31"}
    - data "DD-MM-AAAA" da venda (a fonte é chamada uma vez para o intervalo inteiro;
      quem consome agrupa por dia em memória)
    - qtde na unidade de venda do produto (UN, KG...), como no XML
    - valor_total já líquido de desconto
    - cod_depart / departamento "" quando desconhecidos
    - hora "HH:MM" da venda ("" quando desconhecida)

Hoje a fonte é provisória (fonte_nfce: lê os !vendas_*.json de todos os caixas via
vendas_nfce.listar_vendas, já sincronizados pelo OneDrive). Quando tudo vier do
banco, implemente fonte_banco() e aponte FONTE_PADRAO para ela; o resto não muda.

Chamadas ao banco: só para descobrir o departamento dos produtos, numa única
consulta por carga (um único lote) e apenas para códigos ainda desconhecidos —
o que já foi descoberto fica em memória enquanto o programa estiver aberto.
Os relatórios nunca consultam o banco.
"""

import config as cfg

# ── Banco de dados SammiNFC (mesmo acesso do Pedidos_v2.pyw) ─────────────────

_SAMMI_CONN_STRINGS = [
    "DRIVER={SQL Server};SERVER=localhost\\SAMMI;DATABASE=BancoSammi;Trusted_Connection=yes",
    "DRIVER={SQL Server};SERVER=localhost;DATABASE=BancoSammi;Trusted_Connection=yes",
]


def _conectar_sammi():
    import pyodbc
    for cs in _SAMMI_CONN_STRINGS:
        try:
            return pyodbc.connect(cs, timeout=3)
        except Exception:
            continue
    return None


def _consultar_em_lotes(sql, cods):
    """Executa 'sql' (com {ph} no IN (...)) numa ÚNICA conexão, em lotes de
    códigos, e devolve todas as linhas. [] se o banco estiver indisponível
    ou a consulta falhar."""
    cods = sorted({c for c in cods if c})
    if not cods:
        return []
    try:
        conn = _conectar_sammi()
    except Exception:
        return []
    if conn is None:
        return []
    try:
        cur = conn.cursor()
        linhas = []
        TAMANHO_LOTE = 200  # evita estourar o limite de parâmetros do driver
        for k in range(0, len(cods), TAMANHO_LOTE):
            lote = cods[k:k + TAMANHO_LOTE]
            cur.execute(sql.format(ph=", ".join("?" for _ in lote)), lote)
            linhas.extend(cur.fetchall())
        return linhas
    except Exception:
        return []
    finally:
        conn.close()


def _departamentos_por_codigo(cods):
    """{cod_produto: (cod_depart, nome_departamento)} — mesma consulta do
    buscar_departamentos_por_codigo do Pedidos_v2.pyw. {} se indisponível."""
    linhas = _consultar_em_lotes("""
        SELECT P.COD_PROD, P.COD_DEPART, D.DESCRICAO
        FROM PRODUTO P
        LEFT JOIN DEPARTAMENTO D
            ON D.COD_DEPART = P.COD_DEPART AND D.COD_LOJA = P.COD_LOJA
        WHERE P.COD_PROD IN ({ph})
    """, cods)
    return {str(c).strip(): (str(d).strip() if d is not None else "",
                             n.strip() if n else "")
            for c, d, n in linhas}


# ── FONTES ───────────────────────────────────────────────────────────────────
# Assinatura de qualquer fonte: fonte(data_ini, data_fim, hora_ini, hora_fim) ->
# itens normalizados de TODOS os caixas (hora_ini/hora_fim None = sem filtro).
# Datas DD-MM-AAAA (inclusive); horas "HH:MM" (inclusive, por minuto), valendo
# para cada dia do intervalo.

_cache_departamentos = {}    # {cod_produto: (cod_depart, nome)} — vale até fechar o programa


def fonte_nfce(data_ini, data_fim=None, hora_ini=None, hora_fim=None, pasta_vendas=None,
               resolver_departamento=_departamentos_por_codigo):
    """FONTE PROVISÓRIA: vendas coletadas dos XMLs pelo vendas_nfce.py.
    listar_vendas() já junta os arquivos de todos os caixas. Os itens gravados
    não trazem departamento, então ele é buscado no banco aqui — uma consulta
    para os produtos ainda desconhecidos (o resto vem do cache em memória).
    Descartável quando existir fonte_banco()."""
    import vendas_nfce
    vendas = vendas_nfce.listar_vendas(data_ini, data_fim or data_ini,
                                       pasta_vendas=pasta_vendas or cfg.pasta_vendas())
    if hora_ini or hora_fim:
        hi, hf = hora_ini or cfg.HORA_MIN, hora_fim or cfg.HORA_MAX
        vendas = [v for v in vendas if hi <= (v.get("hora") or "")[:5] <= hf]

    itens = [{"cod": i["cod"], "descricao": i.get("descricao") or "",
              "qtde": i.get("qtde") or 0.0, "valor_total": i["valor_total"],
              "cod_depart": i.get("cod_depart") or "",
              "departamento": i.get("departamento") or "",
              "data": v.get("data") or "", "hora": (v.get("hora") or "")[:5]}
             for v in vendas for i in v["itens"]]

    faltando = {i["cod"] for i in itens
                if not i["cod_depart"] and i["cod"] not in _cache_departamentos}
    if faltando and resolver_departamento:
        try:
            _cache_departamentos.update(resolver_departamento(faltando) or {})
        except Exception:
            pass
    for i in itens:
        if not i["cod_depart"] and i["cod"] in _cache_departamentos:
            i["cod_depart"], i["departamento"] = _cache_departamentos[i["cod"]]
    return itens


def fonte_banco(data_ini, data_fim=None, hora_ini=None, hora_fim=None):
    """FONTE FUTURA: itens vendidos direto do banco, no mesmo formato de item
    normalizado, de data_ini a data_fim (e da faixa hora_ini a hora_fim, se
    houver) de todos os caixas — numa única consulta para o intervalo inteiro
    (nunca uma por dia), já com o departamento (JOIN) e com "data" em
    DD-MM-AAAA em cada item. A consulta SQL fica aqui, com _conectar_sammi()."""
    raise NotImplementedError("fonte_banco ainda não implementada")


FONTE_PADRAO = fonte_nfce
