"""
texto_desvios.py — textos da aba "Desvios do dia": a linha de cada dia na lista e o resumo
em frases, na ordem do fluxo da análise (relatorios/desvios.py). Sem Tkinter: entra a
análise, saem textos e estilos ("titulo", "passo", "texto", "ok", "alerta", "cinza"); a aba
só pinta cada pedaço com o estilo.
"""

import config as cfg
from relatorios import desvios as dv
from relatorios.desvios import principais

from .formato import brl, qtde

_DIAS = ["segunda", "terça", "quarta", "quinta", "sexta", "sábado", "domingo"]
_PLURAL = ["segundas", "terças", "quartas", "quintas", "sextas", "sábados", "domingos"]

_PRECO_MIN = 1.00      # só cita o efeito de preço de um produto a partir de R$ 1,00


# ── Formatação ───────────────────────────────────────────────────────────────

def data_br(data):
    return data.replace("-", "/")


def rs(v):
    """Valor com sinal: +R$ 1.600,00 / -R$ 300,00."""
    return ("+" if v >= 0 else "-") + brl(abs(v))


def pct_s(p):
    """Percentual inteiro com sinal: +32%. Sem base de comparação: —."""
    return "—" if p is None else f"{p * 100:+.0f}%"


def do_esperado(p):
    """'14% acima do esperado' / '8% abaixo do esperado' (p é fração com sinal)."""
    return f"{abs(p) * 100:.0f}% {'acima' if p > 0 else 'abaixo'} do esperado"


def n1(v):
    """Número com 1 casa e vírgula decimal (média de vendas, que pode ser fracionária)."""
    return f"{v:.1f}".replace(".", ",")


def n1s(v):
    """Número com sinal e 1 casa, vírgula decimal: +2,5."""
    return f"{v:+.1f}".replace(".", ",")


def nome_de(linha):
    if linha["nome"]:
        return linha["nome"]
    return "Sem departamento" if linha.get("cod") == cfg.DEPTO_SEM else "Sem nome"


# ── Linha de cada dia na lista ───────────────────────────────────────────────

def _indicadores_fora(a):
    """Nomes e direção dos indicadores fora do padrão: [("faturamento", +1), ...]."""
    fora = []
    for chave, nome in (("faturamento", "faturamento"), ("num_vendas", "vendas")):
        ind = a.get(chave)
        if ind and ind["anomalo"]:
            fora.append((nome, ind["direcao"]))
    return fora


def resultado_dia(a):
    """(texto, tag) do resultado do dia na lista."""
    v = a["veredito"]
    if v == "sem_vendas":
        return "Sem vendas", "semdados"
    if v == "sem_base":
        return f"Sem base ({a['base']['dias']} dias)", "semdados"
    if v == "normal":
        return "Normal", ""
    if v == "pontual":
        k = a["pontual"]["k"]
        return f"Pontual: {k} venda{'s' if k > 1 else ''}", "destaque"
    partes = [f"{'▲' if d > 0 else '▼'} {nome}" for nome, d in _indicadores_fora(a)]
    texto = "Desvio " + ", ".join(partes)
    if a["pontual"]["aplicavel"] and a["pontual"]["resultado"] == "parcial":
        texto += " (parte pontual)"
    return texto, "alto" if a["direcao"] > 0 else "baixo"


def linha_lista(a):
    """(valores das colunas, tag) de um dia na lista."""
    texto, tag = resultado_dia(a)
    fat, ven = a.get("faturamento"), a.get("num_vendas")
    valores = (data_br(a["data"]), cfg.DIAS_SEMANA[a["dia_semana"]], brl(a["total"]),
               brl(fat["esperado"]) if fat else "",
               str(a["vendas"]), n1(ven["esperado"]) if ven else "", texto)
    return valores, tag


# ── Resumo em frases ─────────────────────────────────────────────────────────

def _lista_datas(descartados):
    return ", ".join(f"{data_br(d)[:5]} ({motivo})" for d, motivo in descartados)


def _venda_curta(v):
    hora = f" às {v['hora']}" if v["hora"] else ""
    x = f", {n1(v['x_ticket'])}× o ticket esperado" if v.get("x_ticket") else ""
    return f"{brl(v['valor'])}{hora}{x}"


def _itens_da_venda(v, limite=6):
    itens = [f"{i['nome'] or i['cod']} ({qtde(i['qtde'])} → {brl(i['valor'])})"
             for i in v["itens"][:limite]]
    if len(v["itens"]) > limite:
        itens.append(f"e mais {len(v['itens']) - limite}")
    return ", ".join(itens)


def linhas_resumo(a):
    """Resumo do dia como [(estilo, texto)], uma seção por passo, na ordem em que a análise
    roda (e para quando uma etapa encerra)."""
    s = []

    def add(estilo, texto):
        s.append((estilo, texto))

    wd = a["dia_semana"]
    add("titulo", f"{_DIAS[wd].capitalize()}, {data_br(a['data'])}\n")
    base = a["base"]

    if a["veredito"] == "sem_vendas":
        add("alerta", "Sem vendas neste dia (loja fechada?). Não há o que comparar.\n")
        return s
    if a["veredito"] == "sem_base":
        add("alerta", f"Poucos dias comparáveis: só {base['dias']} de {base['semanas']} "
            f"{_PLURAL[wd]} entram na base (mínimo {dv.MIN_DIAS_BASE}). Aumente as semanas da "
            "base ou analise outro dia.\n")
        if base["descartados"]:
            add("cinza", f"Fora da base: {_lista_datas(base['descartados'])}.\n")
        return s

    fat, ven, tkt = a["faturamento"], a["num_vendas"], a["ticket"]

    # Veredito em uma linha
    if a["veredito"] == "normal":
        add("ok", "Dentro do padrão.\n")
    elif a["veredito"] == "pontual":
        add("alerta", "Faturamento acima do padrão, explicado por uma venda.\n")
    else:
        nomes = {"faturamento": "faturamento", "vendas": "nº de vendas"}
        fora = [f"{nomes[nome]} {'acima' if d > 0 else 'abaixo'} do padrão"
                for nome, d in _indicadores_fora(a)]
        add("alerta", "Desvio: " + " e ".join(fora) + ".\n")

    # Há desvio?
    add("passo", "\nHá desvio?\n")
    for ind, linha in (
            (fat, f"  Faturamento: {brl(fat['real'])} · esperado {brl(fat['esperado'])} "
                  f"({rs(fat['desvio'])}, {pct_s(fat['pct'])})"
                  + (f" · variação habitual ±{brl(fat['escala'])}" if fat["escala"] > 0 else "")),
            (ven, f"  Nº de vendas: {ven['real']} · esperado {n1(ven['esperado'])} "
                  f"({n1s(ven['desvio'])}, {pct_s(ven['pct'])})"
                  + (f" · variação habitual ±{n1(ven['escala'])}" if ven["escala"] > 0 else ""))):
        add("alerta" if ind["anomalo"] else "texto",
            linha + (" → FORA do padrão\n" if ind["anomalo"] else " → dentro do padrão\n"))
    add("texto", f"  Ticket médio: {brl(tkt['real'])} · esperado {brl(tkt['esperado'])} "
        f"({pct_s(tkt['real'] / tkt['esperado'] - 1)})\n")
    txt_base = (f"  Base: {base['dias']} {_PLURAL[wd]} comparáveis (últimas {base['semanas']} "
                "semanas).")
    if base["descartados"]:
        txt_base += f" Fora da base: {_lista_datas(base['descartados'])}."
    add("cinza", txt_base + "\n")
    add("cinza", f"  Fora do padrão = desvio de pelo menos {dv.PCT_MIN * 100:.0f}% do esperado "
        f"E de pelo menos {f'{dv.Z_MIN:g}'.replace('.', ',')} vezes a variação habitual.\n")
    if a["veredito"] == "normal":
        add("ok", "\nAnálise encerrada: nada fora do padrão.\n")
        return s

    # É pontual?
    add("passo", "\nÉ pontual (uma venda)?\n")
    p = a["pontual"]
    maiores = a["maiores_vendas"]
    if not p["aplicavel"]:
        add("texto", f"  Não se aplica: {p['motivo']}.\n")
    elif p["resultado"] == "total":
        k = p["k"]
        quais = ("a maior venda do dia (" + _venda_curta(maiores[0]) + ")" if k == 1 else
                 f"as {k} maiores vendas do dia ({'; '.join(_venda_curta(v) for v in maiores[:k])})")
        add("texto", f"  Sim. Sem {quais} — e sem a maior venda de cada dia da base, para "
            f"comparar em igualdade — o faturamento fica {do_esperado(p['fat_sem']['pct'])}, "
            "dentro do padrão.\n")
        for v in maiores[:k]:
            add("cinza", f"  Itens da venda de {brl(v['valor'])}: {_itens_da_venda(v)}.\n")
        add("ok", "\nAnálise encerrada: o desvio é uma venda pontual.\n")
        return s
    elif p["resultado"] == "parcial":
        add("texto", f"  Em parte. A maior venda do dia ({_venda_curta(maiores[0])}) responde por "
            f"{p['explica'] * 100:.0f}% do desvio, mas sem ela (e sem a maior venda de cada dia da "
            f"base) o faturamento ainda fica {do_esperado(p['fat_sem']['pct'])}.\n")
        add("cinza", f"  Itens dessa venda: {_itens_da_venda(maiores[0])}.\n")
        add("texto", "  Os passos a seguir consideram o dia SEM essa venda.\n")
    else:
        add("texto", f"  Não. Nem a maior venda do dia ({_venda_curta(maiores[0])}) explica o "
            f"desvio: tirando-a, ele cai só {max(0.0, p['explica']) * 100:.0f}%.\n")

    # Quando?
    add("passo", "\nQuando aconteceu?\n")
    h = a["horario"]
    if h is None:
        add("texto", "  Sem horário de venda para analisar.\n")
    else:
        ind = "faturamento" if h["indicador"] == "valor" else "número de vendas"
        j = h["janela"]
        if j is None:
            add("texto", "  Nenhuma faixa de horário se destaca.\n")
        elif j["espalhado"]:
            add("texto", f"  O desvio de {ind} está espalhado pelo dia: nenhuma janela menor "
                f"concentra {dv.JANELA_FRACAO * 100:.0f}% dele.\n")
        else:
            add("texto", f"  O desvio de {ind} se concentra entre {j['inicio']} e {j['fim']} "
                f"({j['fracao'] * 100:.0f}% do desvio).\n")

    # Vendas ou ticket?
    add("passo", "\nVieram mais vendas ou um ticket diferente?\n")
    t = a["ticket_vendas"]
    add("texto", f"  Nº de vendas: {t['vendas']} contra {n1(t['esp_vendas'])} esperadas → efeito "
        f"{rs(t['efeito_vendas'])}\n")
    add("texto", f"  Ticket médio: {brl(t['ticket'])} contra {brl(t['esp_ticket'])} esperado → "
        f"efeito {rs(t['efeito_ticket'])}\n")
    sentido = "mais" if t["efeito_vendas"] > 0 else "menos"
    sentido_t = "mais" if t["efeito_ticket"] > 0 else "menos"
    conclusao = {"vendas": f"O desvio vem do número de vendas ({sentido} clientes).",
                 "ticket": f"O desvio vem do ticket médio (cada venda valeu {sentido_t}).",
                 "ambos": "O desvio vem dos dois efeitos."}[t["define"]]
    if t["opostos"]:
        conclusao += " Eles têm sinais opostos e se compensam em parte."
    add("alerta", f"  {conclusao}\n")

    # Quem puxou?
    add("passo", "\nQuais departamentos e produtos mais pesaram?\n")
    P = a["participantes"]
    deps, _ = principais(P["departamentos"])
    prods, _ = principais(P["produtos"])
    for d in deps[:3]:
        add("texto", f"  • {nome_de(d)}: {rs(d['delta'])} (peso {d['peso'] * 100:.0f}%)\n")
    add("texto", "\n")
    for pr in prods[:5]:
        dep = nome_de({"nome": pr["departamento"], "cod": pr["cod_depart"]})
        if pr["obs"] == "novo":
            det = f"produto sem venda na base; vendeu {qtde(pr['qtde'])}"
        elif pr["obs"] == "ausente":
            det = f"não vendeu (esperado {n1(pr['esp_qtde'])})"
        else:
            det = f"{qtde(pr['qtde'])} contra {n1(pr['esp_qtde'])} esperados"
        add("texto", f"  • {nome_de(pr)} ({dep}): {rs(pr['delta'])} — {det}\n")
    add("cinza", "  Peso = parcela de cada um na movimentação do dia (soma dos módulos dos "
        "desvios).\n")
    removido = a["analisado"]["removido"]
    if removido:
        add("cinza", f"  Fora desta conta: a venda pontual de {brl(removido)}, já retirada.\n")

    # Quantidade ou preço?
    add("passo", "\nÉ quantidade vendida ou preço?\n")
    q = a["qtde_preco"]
    add("texto", f"  Somando os produtos: quantidade vendida {rs(q['efeito_qtde'])} e preço "
        f"médio praticado {rs(q['efeito_preco'])} (o preço inclui descontos).\n")
    conclusao = {"qtde": "O desvio vem da quantidade vendida.",
                 "preco": "O desvio vem do preço praticado.",
                 "ambos": "O desvio vem dos dois efeitos."}[q["define"]]
    if q["opostos"]:
        conclusao += " Eles têm sinais opostos e se compensam em parte."
    add("alerta", f"  {conclusao}\n")
    com_preco = sorted((x for x in P["produtos"] if abs(x["efeito_preco"]) >= _PRECO_MIN),
                       key=lambda x: -abs(x["efeito_preco"]))[:3]
    for x in com_preco:
        add("texto", f"  • {nome_de(x)}: preço {rs(x['efeito_preco'])} "
            f"({brl(x['esp_preco'])} → {brl(x['preco'])} por unidade)\n")
    return s
