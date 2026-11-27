"""
relatorios/desvios.py — dias com vendas fora do padrão e o que explica o desvio (sem I/O:
nada de banco, tela ou arquivo). Como historico_vendas e projetar_dia, recebe a FONTE por
parâmetro, então pode ser testado com dados falsos.

Referência ("o padrão"): os MESMOS DIAS DA SEMANA das últimas N semanas antes do dia
analisado. Entram na base só os dias válidos (a mesma regra da projeção: sem vendas ou
muito abaixo do normal ficam de fora) e é preciso um mínimo de dias válidos.

Fluxo de cada dia (cada passo só roda se o anterior não encerrou a análise):

  1. Há desvio?      faturamento E nº de vendas contra a referência -> "normal" encerra.
  2. É pontual?      só para faturamento ACIMA do padrão: tira a(s) maior(es) venda(s) e vê
                     se o dia volta ao normal -> "pontual" encerra; se a maior venda explica
                     parte do desvio, os passos seguintes analisam o dia SEM ela. Para a
                     comparação ser justa, a maior venda também sai de CADA dia da base
                     (os dias normais também têm suas vendas grandes).
  3. Quando?         faixa de horas que concentra o desvio.
  4. Vendas/ticket?  o desvio vem de mais/menos vendas ou de um ticket médio maior/menor.
  5. Quem puxou?     departamentos e produtos que mais pesaram (esperado x real).
  6. Qtde ou preço?  de cada produto, quanto veio de quantidade vendida e quanto de preço.

Convenções
  - esperado = MÉDIA dos dias da base (como a "média do dia" da projeção). Com média tudo é
    aditivo: a soma do desvio dos itens fecha exatamente com o desvio do dia, sem resíduo.
    (Com mediana, item que vende em poucos dias teria esperado 0 e a soma não fecharia.)
  - "fora do padrão" = desvio de pelo menos PCT_MIN do esperado E de pelo menos Z_MIN vezes a
    variação habitual (MAD, que não se deixa puxar pelos próprios dias atípicos).
  - desvio = real - esperado; item sem venda numa data conta como 0 nessa data.
"""

from datetime import datetime, timedelta
from statistics import mean, median

import config as cfg
from .projecao import LIMITE_DIA_FRACO
from .utils import agrupar_por_dia, dias_entre, faixa, hora_min, min_hora
from .vendas import id_venda

# ── Regras ajustáveis ────────────────────────────────────────────────────────
MIN_DIAS_BASE = 4          # menos dias válidos que isso: não dá para avaliar o dia
PCT_MIN = 0.15             # desvio mínimo (fração do esperado) para ser anormal
Z_MIN = 2.5                # desvio mínimo, em vezes a variação habitual, para ser anormal
PONTUAL_TESTA = 2          # testa tirar a maior venda; depois as duas maiores
PARCIAL_MIN = 0.25         # a maior venda explicando isso do desvio = "pontual em parte"
TOP_VENDAS = 3             # maiores vendas mostradas
DOMINANCIA = 0.70          # um efeito com esse peso (ou mais) "define" o desvio
JANELA_FRACAO = 0.60       # a janela de horas do desvio concentra pelo menos isso dele
COBERTURA_ITENS = 0.80     # itens mostrados somam isso da movimentação (min/máx abaixo)
MIN_ITENS, MAX_ITENS = 5, 15
OPOSTO_MIN = 0.20          # efeitos de sinais opostos só são avisados se o menor chega a isso do maior
_MAD_PARA_SIGMA = 1.4826   # MAD -> desvio-padrão equivalente numa distribuição normal


# ── Resumo de um dia ─────────────────────────────────────────────────────────

def _resumir(itens, passo_min):
    """Totais de um conjunto de itens (um dia, ou um dia sem algumas vendas). "maiores" são os
    valores das PONTUAL_TESTA maiores vendas, para o teste de venda pontual.
    Itens sem hora entram nos totais e nos produtos, mas não nas faixas (como na projeção)."""
    por_venda = {}
    produtos, info, faixas, ids_faixa = {}, {}, {}, {}
    total = 0.0
    for i in itens:
        idv = id_venda(i)
        v = i["valor_total"]
        por_venda[idv] = por_venda.get(idv, 0.0) + v
        total += v
        cod = i["cod"]
        p = produtos.setdefault(cod, [0.0, 0.0])
        p[0] += v
        p[1] += i.get("qtde", 0.0)
        info[cod] = (i.get("descricao") or "", i.get("cod_depart") or cfg.DEPTO_SEM,
                     i.get("departamento") or "")
        if i.get("hora"):
            k = faixa(min_hora(i["hora"]), passo_min)
            faixas[k] = faixas.get(k, 0.0) + v
            ids_faixa.setdefault(k, set()).add(idv)
    maiores = sorted(por_venda.values(), reverse=True)[:PONTUAL_TESTA]
    return {"total": round(total, 2), "vendas": len(por_venda), "maiores": maiores,
            "produtos": produtos, "info": info, "faixas": faixas,
            "vendas_faixa": {k: len(s) for k, s in ids_faixa.items()}}


def _datas_base(data, semanas):
    """Os mesmos dias da semana das `semanas` semanas antes de `data`, do mais recente."""
    d = datetime.strptime(data, cfg.FMT_DATA)
    return [(d - timedelta(days=7 * n)).strftime(cfg.FMT_DATA) for n in range(1, semanas + 1)]


def _dias_base(resumos, datas):
    """([datas usadas], [(data, motivo)]) — a mesma regra de projecao._dias_validos: sem
    vendas fica de fora e, havendo 3 dias ou mais, também o que vendeu menos que
    LIMITE_DIA_FRACO da mediana."""
    lidos = [(d, resumos[d]["total"]) for d in datas]
    descartados = [(d, "sem vendas") for d, t in lidos if t <= 0]
    lidos = [x for x in lidos if x[1] > 0]
    if len(lidos) >= 3:
        mediana = median(t for _, t in lidos)
        fracos = {d for d, t in lidos if t < mediana * LIMITE_DIA_FRACO}
        descartados += [(d, "venda muito abaixo do normal") for d in sorted(fracos)]
        lidos = [x for x in lidos if x[0] not in fracos]
    return [d for d, _ in lidos], descartados


# ── Passo 1: o desvio ────────────────────────────────────────────────────────

def _indicador(real, base):
    """Compara `real` com `base` (um valor por dia de referência).
    Retorna {"real", "esperado", "desvio", "pct", "escala" (variação habitual, em unidades
    do indicador), "z", "anomalo", "direcao" (+1 acima, -1 abaixo, 0)}."""
    esperado = mean(base)
    mediana = median(base)
    escala = _MAD_PARA_SIGMA * median(abs(x - mediana) for x in base)
    desvio = real - esperado
    pct = desvio / esperado if esperado else None
    if escala > 0:
        z = desvio / escala
    else:                                  # base sem variação alguma: qualquer desvio é "infinito"
        z = 0.0 if desvio == 0 else float("inf") if desvio > 0 else float("-inf")
    anomalo = pct is not None and abs(pct) >= PCT_MIN and abs(z) >= Z_MIN
    return {"real": real, "esperado": esperado, "desvio": desvio, "pct": pct,
            "escala": escala, "z": z, "anomalo": anomalo,
            "direcao": (desvio > 0) - (desvio < 0)}


# ── Passo 2: venda pontual ───────────────────────────────────────────────────

def _vendas_do_dia(itens):
    """Vendas do dia, da maior para a menor:
    [{"id", "hora", "valor", "itens": [{"cod", "nome", "qtde", "valor"}]}]."""
    por_id = {}
    for i in itens:
        idv = id_venda(i)
        v = por_id.setdefault(idv, {"id": idv, "hora": i.get("hora") or "", "valor": 0.0,
                                    "itens": []})
        v["valor"] += i["valor_total"]
        v["itens"].append({"cod": i["cod"], "nome": i.get("descricao") or "",
                           "qtde": i.get("qtde", 0.0), "valor": i["valor_total"]})
    vendas = sorted(por_id.values(), key=lambda v: -v["valor"])
    for v in vendas:
        v["valor"] = round(v["valor"], 2)
        v["itens"].sort(key=lambda x: -x["valor"])
    return vendas


def _base_sem_maiores(base, k):
    """(faturamentos, nºs de vendas) dos dias da base SEM a(s) k maior(es) venda(s) de cada dia."""
    return ([r["total"] - sum(r["maiores"][:k]) for r in base],
            [r["vendas"] - min(k, r["vendas"]) for r in base])


def _sem_vendas(vendas, k, total, n_vendas, base):
    """O dia sem as k maiores vendas, contra a base também sem as k maiores de cada dia:
    (valor retirado, indicador de faturamento, indicador de nº de vendas)."""
    base_fat, base_ven = _base_sem_maiores(base, k)
    removido = round(sum(v["valor"] for v in vendas[:k]), 2)
    return (removido, _indicador(round(total - removido, 2), base_fat),
            _indicador(n_vendas - k, base_ven))


def _testar_pontual(vendas, total, n_vendas, fat, base):
    """O desvio de faturamento é uma venda só? Só faz sentido para faturamento ACIMA do
    padrão (tirar uma venda não explica um dia fraco nem um desvio só de nº de vendas).
    Retorna {"aplicavel", "motivo", "resultado": "total"|"parcial"|"nao", "k", "removido",
    "fat_sem", "vendas_sem", "explica" (fração do desvio de R$ que sai ao tirar a maior
    venda), "tentativas": [...]}.
      total   tirando as k maiores (k=1, depois 2) nada mais fica fora do padrão -> encerra
      parcial tirando a maior o desvio cai PARCIAL_MIN ou mais, mas o dia segue fora do
              padrão -> os passos seguintes usam o dia sem ela (k=1)
      nao     nenhuma venda isolada explica o desvio"""
    if not (fat["anomalo"] and fat["direcao"] > 0):
        motivo = ("o desvio de faturamento é para baixo" if fat["anomalo"]
                  else "só o número de vendas está fora do padrão")
        return {"aplicavel": False, "motivo": motivo}
    tentativas = []
    for k in range(1, PONTUAL_TESTA + 1):
        if len(vendas) <= k:                 # precisa sobrar venda para comparar
            break
        removido, f, n = _sem_vendas(vendas, k, total, n_vendas, base)
        tentativas.append({"k": k, "removido": removido, "fat": f, "vendas": n})
        if not f["anomalo"] and not n["anomalo"]:
            return {"aplicavel": True, "resultado": "total", "k": k, "removido": removido,
                    "fat_sem": f, "vendas_sem": n, "tentativas": tentativas,
                    "explica": 1 - f["desvio"] / fat["desvio"]}
    explica = 0.0
    if tentativas:
        t = tentativas[0]
        explica = 1 - t["fat"]["desvio"] / fat["desvio"]
        if explica >= PARCIAL_MIN:
            return {"aplicavel": True, "resultado": "parcial", "k": 1,
                    "removido": t["removido"], "fat_sem": t["fat"], "vendas_sem": t["vendas"],
                    "tentativas": tentativas, "explica": explica}
    return {"aplicavel": True, "resultado": "nao", "k": 0, "removido": 0.0,
            "tentativas": tentativas, "explica": explica}


def _sem_a_maior(itens):
    """Os itens sem a maior venda."""
    if not itens:
        return itens
    maior = _vendas_do_dia(itens)[0]["id"]
    return [i for i in itens if id_venda(i) != maior]


# ── Passo 3: horário ─────────────────────────────────────────────────────────

def _janela(deltas):
    """Menor janela contínua de faixas cuja soma (no sentido do desvio) chega a
    JANELA_FRACAO do desvio total. Retorna (primeira, última, fração, espalhado) ou None;
    `espalhado` = precisou do dia todo."""
    total = sum(deltas)
    if abs(total) < 1e-9:
        return None
    s = 1 if total > 0 else -1
    pref = [0.0]
    for d in deltas:
        pref.append(pref[-1] + d * s)
    m, alvo = len(deltas), JANELA_FRACAO * abs(total)
    for tam in range(1, m + 1):
        melhor = None
        for a in range(m - tam + 1):
            soma = pref[a + tam] - pref[a]
            if soma >= alvo - 1e-9 and (melhor is None or soma > melhor[2]):
                melhor = (a, a + tam - 1, soma)
        if melhor:
            return melhor[0], melhor[1], melhor[2] / abs(total), tam == m and m > 1
    return None


def _horario(dia, base, passo_min, indicador):
    """Por faixa de `passo_min`: esperado x real em R$ e em nº de vendas. A janela do
    desvio é calculada sobre `indicador` ("valor" ou "vendas")."""
    chaves = sorted(set(dia["faixas"]) | {k for r in base for k in r["faixas"]})
    if not chaves:
        return None
    faixas = []
    for k in range(chaves[0], chaves[-1] + 1, passo_min):
        esp_v = mean(r["faixas"].get(k, 0.0) for r in base)
        esp_n = mean(r["vendas_faixa"].get(k, 0) for r in base)
        v, n = dia["faixas"].get(k, 0.0), dia["vendas_faixa"].get(k, 0)
        faixas.append({"inicio": hora_min(k), "fim": hora_min(min(k + passo_min, 1439)),
                       "esp_valor": esp_v, "valor": v, "delta_valor": v - esp_v,
                       "esp_vendas": esp_n, "vendas": n, "delta_vendas": n - esp_n})
    campo = "delta_valor" if indicador == "valor" else "delta_vendas"
    j = _janela([f[campo] for f in faixas])
    janela = None
    if j:
        a, b, fracao, espalhado = j
        janela = {"inicio": faixas[a]["inicio"], "fim": faixas[b]["fim"], "primeira": a,
                  "ultima": b, "fracao": fracao, "espalhado": espalhado}
    return {"indicador": indicador, "faixas": faixas, "janela": janela}


# ── Passo 4: nº de vendas x ticket ───────────────────────────────────────────

def _opostos(a, b):
    """Dois efeitos de sinais opostos e de tamanho comparável (um se compensa com o outro)."""
    maior = max(abs(a), abs(b))
    return a * b < 0 and min(abs(a), abs(b)) >= OPOSTO_MIN * maior


def _vendas_x_ticket(dia, base):
    """Divide o desvio de faturamento em efeito do nº de vendas (a ticket esperado) e efeito
    do ticket médio (com as vendas reais). Soma exatamente o desvio.
    "define" = "vendas", "ticket" ou "ambos" (um efeito com DOMINANCIA da soma dos módulos)."""
    esp_f = mean(r["total"] for r in base)
    esp_v = mean(r["vendas"] for r in base)
    esp_t = esp_f / esp_v
    v, f = dia["vendas"], dia["total"]
    t = f / v
    ef_v = (v - esp_v) * esp_t
    ef_t = v * (t - esp_t)
    bruto = abs(ef_v) + abs(ef_t)
    if bruto == 0:
        define = "ambos"
    elif abs(ef_v) / bruto >= DOMINANCIA:
        define = "vendas"
    elif abs(ef_t) / bruto >= DOMINANCIA:
        define = "ticket"
    else:
        define = "ambos"
    return {"vendas": v, "esp_vendas": esp_v, "ticket": t, "esp_ticket": esp_t,
            "efeito_vendas": ef_v, "efeito_ticket": ef_t, "define": define,
            "opostos": _opostos(ef_v, ef_t)}


# ── Passos 5 e 6: participantes e quantidade x preço ─────────────────────────

def _linha_produto(cod, dia, base, info):
    n = len(base)
    vals = [r["produtos"].get(cod, (0.0, 0.0)) for r in base]
    esp_v = sum(v for v, _ in vals) / n
    esp_q = sum(q for _, q in vals) / n
    dias_venda = sum(1 for v, q in vals if v or q)
    v, q = dia["produtos"].get(cod, (0.0, 0.0))
    delta = v - esp_v
    esp_p = esp_v / esp_q if esp_q > 0 else None
    p = v / q if q > 0 else None
    if esp_p is not None and p is not None:       # delta = efeito qtde + efeito preço, exato
        ef_q, ef_p = (q - esp_q) * esp_p, q * (p - esp_p)
    else:                                         # novo ou ausente: tudo é quantidade
        ef_q, ef_p = delta, 0.0
    nome, cod_dep, nome_dep = info[cod]
    if dias_venda == 0:
        obs = "novo"
    elif v == 0 and q == 0:
        obs = "ausente"
    elif dias_venda < n / 2:
        obs = f"esporádico ({dias_venda}/{n})"
    else:
        obs = ""
    return {"cod": cod, "nome": nome, "cod_depart": cod_dep, "departamento": nome_dep,
            "esperado": esp_v, "real": v, "delta": delta,
            "pct": delta / esp_v if esp_v else None,
            "efeito_qtde": ef_q, "efeito_preco": ef_p,
            "esp_qtde": esp_q, "qtde": q, "esp_preco": esp_p, "preco": p,
            "dias_venda": dias_venda, "obs": obs}


def _pesos(linhas):
    """Preenche "peso" (|delta| / soma dos |delta|) e ordena do maior para o menor."""
    bruto = sum(abs(x["delta"]) for x in linhas)
    for x in linhas:
        x["peso"] = abs(x["delta"]) / bruto if bruto else 0.0
    linhas.sort(key=lambda x: (-abs(x["delta"]), x["nome"]))
    return linhas


def _participantes(dia, base):
    """{"produtos": [...], "departamentos": [...]} do maior para o menor impacto (|delta|).
    O departamento soma os efeitos de seus produtos, então delta = efeito qtde + efeito
    preço também nele, e a soma dos departamentos (ou dos produtos) é o desvio do dia."""
    info = {}
    for r in base + [dia]:
        info.update(r["info"])                    # o dia analisado, por último, prevalece
    cods = set(dia["produtos"]) | {c for r in base for c in r["produtos"]}
    produtos = _pesos([_linha_produto(c, dia, base, info) for c in cods])
    deps = {}
    for p in produtos:
        d = deps.setdefault(p["cod_depart"], {
            "cod": p["cod_depart"], "nome": p["departamento"], "esperado": 0.0, "real": 0.0,
            "delta": 0.0, "efeito_qtde": 0.0, "efeito_preco": 0.0})
        d["nome"] = d["nome"] or p["departamento"]
        for campo in ("esperado", "real", "delta", "efeito_qtde", "efeito_preco"):
            d[campo] += p[campo]
    for d in deps.values():
        d["pct"] = d["delta"] / d["esperado"] if d["esperado"] else None
    return {"produtos": produtos, "departamentos": _pesos(list(deps.values()))}


def principais(linhas):
    """(mostradas, demais): as linhas (já ordenadas por impacto) até somarem COBERTURA_ITENS da
    movimentação (soma dos |delta|), com MIN_ITENS e MAX_ITENS. `demais` é uma linha que
    resume o resto (None se não sobrou nada), para a tabela fechar com o total."""
    bruto = sum(abs(x["delta"]) for x in linhas)
    n, acum = 0, 0.0
    for x in linhas:
        if n >= MAX_ITENS or (n >= MIN_ITENS and acum >= COBERTURA_ITENS * bruto):
            break
        acum += abs(x["delta"])
        n += 1
    resto = linhas[n:]
    if not resto:
        return linhas[:n], None
    demais = {"nome": f"Demais ({len(resto)})", "cod": None, "obs": ""}
    for campo in ("esperado", "real", "delta", "efeito_qtde", "efeito_preco"):
        demais[campo] = sum(x[campo] for x in resto)
    demais["pct"] = demais["delta"] / demais["esperado"] if demais["esperado"] else None
    demais["peso"] = sum(x["peso"] for x in resto)
    return linhas[:n], demais


def _qtde_x_preco(produtos):
    """Soma dos efeitos de todos os produtos. "define" = "qtde", "preco" ou "ambos"."""
    ef_q = sum(p["efeito_qtde"] for p in produtos)
    ef_p = sum(p["efeito_preco"] for p in produtos)
    bruto = abs(ef_q) + abs(ef_p)
    if bruto == 0:
        define = "ambos"
    elif abs(ef_q) / bruto >= DOMINANCIA:
        define = "qtde"
    elif abs(ef_p) / bruto >= DOMINANCIA:
        define = "preco"
    else:
        define = "ambos"
    return {"efeito_qtde": ef_q, "efeito_preco": ef_p, "define": define,
            "opostos": _opostos(ef_q, ef_p)}


# ── Análise de um dia e do período ───────────────────────────────────────────

def _analisar_dia(data, por_dia, resumos, semanas, passo_min):
    """Análise completa de `data` (veja o fluxo no topo do módulo). `por_dia` = itens de
    cada data; `resumos` = _resumir de cada data."""
    itens_dia = por_dia.get(data, [])
    dia = resumos[data]
    usados, descartados = _dias_base(resumos, _datas_base(data, semanas))
    res = {"data": data, "dia_semana": datetime.strptime(data, cfg.FMT_DATA).weekday(),
           "total": dia["total"], "vendas": dia["vendas"],
           "base": {"semanas": semanas, "dias": len(usados), "usados": usados,
                    "descartados": descartados}}
    if dia["total"] <= 0:
        res["veredito"] = "sem_vendas"
        return res
    if len(usados) < MIN_DIAS_BASE:
        res["veredito"] = "sem_base"
        return res

    # 1. Há desvio?
    base = [resumos[d] for d in usados]
    base_fat = [r["total"] for r in base]
    base_ven = [r["vendas"] for r in base]
    fat, ven = _indicador(dia["total"], base_fat), _indicador(dia["vendas"], base_ven)
    res["faturamento"], res["num_vendas"] = fat, ven
    res["ticket"] = {"real": dia["total"] / dia["vendas"],
                     "esperado": mean(base_fat) / mean(base_ven)}
    if not (fat["anomalo"] or ven["anomalo"]):
        res["veredito"] = "normal"
        return res

    # 2. É pontual?
    vendas = _vendas_do_dia(itens_dia)
    res["maiores_vendas"] = vendas[:TOP_VENDAS]
    esp_ticket = res["ticket"]["esperado"]
    for v in res["maiores_vendas"]:
        v["x_ticket"] = v["valor"] / esp_ticket if esp_ticket else None
    pontual = _testar_pontual(vendas, dia["total"], dia["vendas"], fat, base)
    res["pontual"] = pontual
    if pontual["aplicavel"] and pontual["resultado"] == "total":
        res["veredito"], res["direcao"] = "pontual", 1
        return res

    # A partir daqui o dia analisado é o dia SEM a venda pontual (caso parcial), comparado com
    # a base também sem a maior venda de cada dia. Nos demais casos, o dia inteiro.
    if pontual["aplicavel"] and pontual["resultado"] == "parcial":
        analisado = _resumir(_sem_a_maior(itens_dia), passo_min)
        base = [_resumir(_sem_a_maior(por_dia.get(d, [])), passo_min) for d in usados]
        fat_a, ven_a = pontual["fat_sem"], pontual["vendas_sem"]
    else:
        analisado, fat_a, ven_a = dia, fat, ven
    res["veredito"] = "desvio"
    res["analisado"] = {"total": analisado["total"], "vendas": analisado["vendas"],
                        "removido": pontual.get("removido", 0.0),
                        "faturamento": fat_a, "num_vendas": ven_a}
    primario = fat_a if fat_a["anomalo"] else ven_a
    res["direcao"] = primario["direcao"]

    # 3. Quando?   4. Vendas ou ticket?   5. Quem puxou?   6. Quantidade ou preço?
    res["horario"] = _horario(analisado, base, passo_min,
                              "valor" if fat_a["anomalo"] else "vendas")
    res["ticket_vendas"] = _vendas_x_ticket(analisado, base)
    res["participantes"] = _participantes(analisado, base)
    res["qtde_preco"] = _qtde_x_preco(res["participantes"]["produtos"])
    return res


def analisar_periodo(fonte, data_ini, data_fim=None, semanas=8, passo_min=60, hoje=None):
    """Analisa cada dia de data_ini a data_fim (DD-MM-AAAA) contra os mesmos dias da semana
    das últimas `semanas` semanas. Só dias já encerrados: hoje (em andamento) e datas futuras
    ficam em "ignorados". A fonte é chamada UMA vez, para o intervalo inteiro (período mais a
    base). Retorna {"semanas", "passo_min", "dias": [análise de cada dia, em ordem],
    "ignorados": [(data, motivo)]}; veja _analisar_dia."""
    data_fim = data_fim or data_ini
    hoje = hoje or datetime.now().strftime(cfg.FMT_DATA)
    hoje_dt = datetime.strptime(hoje, cfg.FMT_DATA)
    analisaveis, ignorados = [], []
    for d in dias_entre(data_ini, data_fim):
        if datetime.strptime(d, cfg.FMT_DATA) < hoje_dt:
            analisaveis.append(d)
        else:
            ignorados.append((d, "dia em andamento (use a Projeção do dia)" if d == hoje
                              else "data futura"))
    resultado = {"semanas": semanas, "passo_min": passo_min, "dias": [], "ignorados": ignorados}
    if not analisaveis:
        return resultado
    precisam = set(analisaveis)
    for d in analisaveis:
        precisam.update(_datas_base(d, semanas))
    pontas = sorted(datetime.strptime(d, cfg.FMT_DATA) for d in precisam)
    por_dia = agrupar_por_dia(fonte(pontas[0].strftime(cfg.FMT_DATA),
                                    pontas[-1].strftime(cfg.FMT_DATA), None, None))
    resumos = {d: _resumir(por_dia.get(d, []), passo_min) for d in precisam}
    for d in analisaveis:
        resultado["dias"].append(_analisar_dia(d, por_dia, resumos, semanas, passo_min))
    return resultado


def serie_diaria(dias, indicador):
    """Números do gráfico de colunas: um item por dia analisado, na ordem dos dias, com o
    valor real e o esperado pela base ({"data", "dia_semana", "real", "esperado", "estado"};
    esperado é None nos dias sem base). `indicador`: "faturamento" ou "vendas".
    "estado" (do indicador mostrado): "alto" / "baixo" = fora do padrão para cima / para baixo,
    "pontual" = faturamento alto explicado por uma venda isolada, None = dentro do padrão."""
    chave, campo = (("faturamento", "total") if indicador == "faturamento"
                    else ("num_vendas", "vendas"))
    serie = []
    for a in dias:
        ind = a.get(chave)
        estado = None
        if ind and ind["anomalo"]:
            if a["veredito"] == "pontual" and indicador == "faturamento":
                estado = "pontual"
            else:
                estado = "alto" if ind["direcao"] > 0 else "baixo"
        serie.append({"data": a["data"], "dia_semana": a["dia_semana"], "real": a[campo],
                      "esperado": ind["esperado"] if ind else None, "estado": estado})
    return serie
