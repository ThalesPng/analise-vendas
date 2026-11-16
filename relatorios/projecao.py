"""
relatorios/projecao.py — projeção do dia e perfil por hora (sem I/O: nada de banco, tela ou
arquivo). Como historico_vendas (historico.py), recebe a FONTE por parâmetro, então
pode ser testada com dados falsos. Usa de utils.py só os helpers de data e hora.
"""

from datetime import datetime, timedelta
from statistics import median, quantiles

import config as cfg
from .utils import agrupar_por_dia, dias_entre, faixa, hora_min, min_hora
from .vendas import id_venda


# ── Projeção do dia e perfil por hora ────────────────────────────────────────
# Recebem a FONTE por parâmetro (como historico_vendas) e não fazem I/O.
# Dias passados não mudam: o `cache` (dict) evita reler a mesma data; o dia de
# referência e datas futuras nunca entram nele. A fonte é chamada uma vez por
# intervalo (só o que falta no cache), nunca uma vez por dia.

LIMITE_DIA_FRACO = 0.4      # dia com total < 40% da mediana é tratado como atípico
MIN_FRACAO_CONFIAVEL = 0.15  # antes disso (menos de 15% do dia) a projeção é frágil
MIN_DIAS_CONFIAVEL = 3


def _vendas_por_dia(fonte, datas, cache, hoje):
    """{data: [(minuto, valor, id_venda), ...]} ordenado, para cada data de `datas`.
    Uma ÚNICA chamada à fonte cobre o intervalo das datas que faltam no cache;
    os itens são agrupados por item["data"] em memória. Só dias anteriores a
    `hoje` vão ao cache."""
    faltam = [d for d in datas if cache is None or d not in cache]
    lidos = {}
    if faltam:
        dts = [datetime.strptime(d, cfg.FMT_DATA) for d in faltam]
        ini, fim = min(dts).strftime(cfg.FMT_DATA), max(dts).strftime(cfg.FMT_DATA)
        lidos = {d: [] for d in dias_entre(ini, fim)}
        itens_dia = agrupar_por_dia(fonte(ini, fim, None, None))
        for d in lidos:
            lidos[d] = [(min_hora(i["hora"]), i["valor_total"], id_venda(i))
                        for i in itens_dia.get(d, []) if i.get("hora")]
        for d, vendas in lidos.items():
            vendas.sort()
            if cache is not None and datetime.strptime(d, cfg.FMT_DATA) < hoje:
                cache[d] = vendas
    return {d: lidos[d] if d in lidos else cache[d] for d in datas}


def _datas_anteriores(data_ref, semanas):
    """As `semanas` * 7 datas antes de data_ref, da mais recente para a mais antiga."""
    ref = datetime.strptime(data_ref, cfg.FMT_DATA)
    ini = (ref - timedelta(days=semanas * 7)).strftime(cfg.FMT_DATA)
    fim = (ref - timedelta(days=1)).strftime(cfg.FMT_DATA)
    return dias_entre(ini, fim)[::-1]


def _dias_validos(vendas_dias, datas):
    """Separa os dias que servem de base dos atípicos. `vendas_dias` é o
    resultado de _vendas_por_dia. Retorna ([(data, vendas, total)], [(data, motivo)])."""
    lidos = []
    for d in datas:
        v = vendas_dias[d]
        lidos.append((d, v, round(sum(x for _, x, _ in v), 2)))
    descartados = [(d, "sem vendas") for d, _, t in lidos if t <= 0]
    lidos = [x for x in lidos if x[2] > 0]
    if len(lidos) >= 3:
        mediana = median(t for _, _, t in lidos)
        fracos = {d for d, _, t in lidos if t < mediana * LIMITE_DIA_FRACO}
        descartados += [(d, "venda muito abaixo do normal") for d in fracos]
        lidos = [x for x in lidos if x[0] not in fracos]
    return lidos, descartados


def perfil_horario(fonte, data_ref, semanas=8, passo_min=60, cache=None):
    """Curva média por faixa horária de cada dia da semana (0=segunda ... 6=domingo),
    olhando as últimas `semanas` semanas antes de data_ref.

    Retorna {dia_semana: {"dias": n, "descartados": [(data, motivo)],
                          "media_total": R$ médio do dia,
                          "faixas": [{"inicio","fim","media","vendas","pct"}],
                          "pico": "HH:MM" da faixa mais forte}}
    "media" é o valor médio vendido na faixa e "vendas" a quantidade média de vendas
    na faixa, ambos por dia válido (dia da semana sem nenhum dia válido: "dias" = 0 e
    "faixas" vazia)."""
    hoje = datetime.strptime(data_ref, cfg.FMT_DATA)
    por_dia = {n: [] for n in range(7)}
    anteriores = _datas_anteriores(data_ref, semanas)
    for d in anteriores:
        por_dia[datetime.strptime(d, cfg.FMT_DATA).weekday()].append(d)
    vendas_dias = _vendas_por_dia(fonte, anteriores, cache, hoje)

    perfil = {}
    for dia, datas in por_dia.items():
        validos, descartados = _dias_validos(vendas_dias, datas)
        if not validos:
            perfil[dia] = {"dias": 0, "descartados": descartados, "media_total": 0.0,
                           "faixas": [], "pico": None}
            continue
        soma, qtd_vendas = {}, {}
        for _, vendas, _ in validos:
            ids_dia = {}                       # faixa -> ids das vendas desse dia nela
            for m, v, idv in vendas:
                k = faixa(m, passo_min)
                soma[k] = soma.get(k, 0.0) + v
                ids_dia.setdefault(k, set()).add(idv)
            for k, ids in ids_dia.items():
                qtd_vendas[k] = qtd_vendas.get(k, 0) + len(ids)
        n = len(validos)
        media_total = sum(soma.values()) / n
        faixas = []
        for k in range(min(soma), max(soma) + 1, passo_min):
            media = soma.get(k, 0.0) / n
            faixas.append({"inicio": hora_min(k), "fim": hora_min(min(k + passo_min, 1439)),
                           "media": round(media, 2),
                           "vendas": round(qtd_vendas.get(k, 0) / n, 1),
                           "pct": round(media / media_total * 100, 2)})
        pico = max(faixas, key=lambda f: f["media"])["inicio"]
        perfil[dia] = {"dias": n, "descartados": descartados,
                       "media_total": round(media_total, 2), "faixas": faixas, "pico": pico}
    return perfil


def projetar_dia(fonte, data, ate_hora, semanas=8, cache=None, passo_min=60):
    """Fechamento estimado de `data`, com o vendido até `ate_hora` (HH:MM, inclusive).

    Base: os mesmos dias da semana das últimas `semanas` semanas. Dois métodos:
      proporcional  vendido / fração do dia que costuma estar vendida a essa hora
      aditivo       vendido + média do que costuma vender depois dessa hora
    A faixa (baixa-alta) vem da dispersão entre os dias usados como base.

    Retorna dict: vendido, fracao (0-1), estimativa, baixa, alta, aditivo, dias,
    descartados, media_total_historico, avisos (lista de textos) e
    por_faixa ({minuto de início da faixa de passo_min: vendido até ate_hora})."""
    hoje = datetime.strptime(data, cfg.FMT_DATA)
    limite = min_hora(ate_hora)
    mesmos = [d for d in _datas_anteriores(data, semanas)
              if datetime.strptime(d, cfg.FMT_DATA).weekday() == hoje.weekday()]
    vendas_dias = _vendas_por_dia(fonte, [data] + mesmos, cache, hoje)
    ate_agora = [(m, v) for m, v, _ in vendas_dias[data] if m <= limite]
    vendido = round(sum(v for _, v in ate_agora), 2)
    por_faixa = {}
    for m, v in ate_agora:
        k = faixa(m, passo_min)
        por_faixa[k] = round(por_faixa.get(k, 0.0) + v, 2)

    validos, descartados = _dias_validos(vendas_dias, mesmos)
    res = {"vendido": vendido, "fracao": None, "estimativa": None, "baixa": None,
           "alta": None, "aditivo": None, "dias": len(validos),
           "descartados": descartados, "media_total_historico": None, "avisos": [],
           "por_faixa": por_faixa}
    if not validos:
        res["avisos"].append("Sem dias anteriores com vendas no mesmo dia da semana.")
        return res

    totais = [t for _, _, t in validos]
    acums = [sum(v for m, v, _ in vendas if m <= limite) for _, vendas, _ in validos]
    res["media_total_historico"] = round(sum(totais) / len(totais), 2)
    fracao = sum(acums) / sum(totais)
    res["fracao"] = round(fracao, 4)

    if fracao <= 0:
        res["avisos"].append("Nesse horário os dias anteriores ainda não tinham vendido nada; "
                             "a projeção só faz sentido depois que o movimento começa.")
        return res
    res["estimativa"] = round(vendido / fracao, 2)
    res["aditivo"] = round(vendido + (sum(totais) - sum(acums)) / len(totais), 2)

    por_dia = sorted(vendido / (a / t) for a, t in zip(acums, totais) if a > 0)
    if len(por_dia) >= 4:
        q = quantiles(por_dia, n=4)
        baixa, alta = q[0], q[2]
    else:
        baixa, alta = por_dia[0], por_dia[-1]
    res["baixa"], res["alta"] = round(min(baixa, res["estimativa"]), 2), \
        round(max(alta, res["estimativa"]), 2)

    if fracao < MIN_FRACAO_CONFIAVEL:
        res["avisos"].append(f"Ainda cedo: só {fracao * 100:.0f}% do dia costuma estar vendido "
                             "até essa hora, então a estimativa varia bastante.")
    if len(validos) < MIN_DIAS_CONFIAVEL:
        res["avisos"].append(f"Base pequena: só {len(validos)} dia(s) comparável(is).")
    return res
