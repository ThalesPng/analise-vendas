"""
historico.py — relatório da aba Histórico (Excel), sem I/O e sem Tk: nada de banco, tela
ou arquivo. A exportação para .xlsx fica em excel.py (na raiz), de propósito separada.

Duas partes:
  Cálculo   historico_vendas (valor vendido por item em cada dia ou faixa de minutos) e
            aplicar_grupos (acrescenta, para cada grupo, uma linha com a soma dos membros;
            os membros continuam nos dados, então grupo e itens do grupo podem ir juntos
            para o mesmo gráfico).
            historico_vendas recebe a FONTE por parâmetro, então pode ser testada com
            dados falsos.
  Estado    classe Grupos: o que está marcado na lista e os grupos criados pelo usuário
            (vários itens somados numa linha só). A aba só mostra e repassa os cliques,
            então tudo aqui pode ser testado sem janela.

Tudo é separado por tipo ("produtos" / "departamentos"). Chaves da lista: o código do
item, ou cfg.PREFIXO_GRUPO + nome para um grupo.
"""

from datetime import datetime

import config as cfg

from .utils import agrupar, agrupar_por_dia, dias_entre, faixa, hora_min, min_hora


# ── Cálculo do histórico ─────────────────────────────────────────────────────

def historico_vendas(fonte, data_ini, data_fim=None, hora_ini=None, hora_fim=None,
                     intervalo_min=None):
    """Valor vendido de cada produto e de cada departamento, lendo as vendas
    direto da `fonte` (callable fonte(data_ini, data_fim, hora_ini, hora_fim) -> itens).

    Sem intervalo_min: uma coluna POR DIA, de data_ini a data_fim (DD-MM-AAAA,
    inclusive). A fonte é chamada UMA vez para o período inteiro; os itens são
    agrupados por dia (item["data"]) em memória.
    Com intervalo_min: uma coluna por faixa de intervalo_min minutos em CADA dia
    do período, da hora_ini (padrão 00:00) à hora_fim (padrão 23:59), em ordem
    cronológica; a coluna é rotulada com a hora em que a faixa começa (com o
    dia, se o período tiver mais de um).

    hora_ini/hora_fim (opcionais) filtram a faixa de horas de cada dia. Retorna:
        "datas":           [chaves das colunas, da mais antiga à mais recente]
                           (datas DD-MM-AAAA, ou "DD-MM-AAAA HH:MM" com intervalo_min)
        "rotulos":         {chave: texto do cabeçalho da coluna}
        "produtos":        {cod: {chave: total}}   (só as colunas com venda)
        "departamentos":   {cod_depart: {chave: total}}
        "nomes":           {"produtos": {cod: nome}, "departamentos": {cod: nome}}
        "dias_sem_vendas": [colunas sem vendas]
        "unidade":         "dia" ou "faixa"
        "periodo_txt":     texto do período para títulos
        "arquivo_txt":     texto do período para nome de arquivo
    Erros de coleta propagam."""
    data_fim = data_fim or data_ini
    if datetime.strptime(data_fim, cfg.FMT_DATA) < datetime.strptime(data_ini, cfg.FMT_DATA):
        raise ValueError("data_fim anterior a data_ini")
    if intervalo_min and intervalo_min < cfg.INTERVALO_MIN:
        raise ValueError(f"intervalo deve ser >= {cfg.INTERVALO_MIN} minuto")
    dias = dias_entre(data_ini, data_fim)
    itens_dia = agrupar_por_dia(fonte(dias[0], dias[-1], hora_ini, hora_fim))
    if intervalo_min:
        return _historico_por_faixa(dias, itens_dia, hora_ini, hora_fim, intervalo_min)
    return _historico_por_dia(dias, itens_dia)


def _acumular(hist, nomes, itens, chave):
    """Soma os itens por produto e por departamento na coluna `chave`."""
    for tipo, por in (("produtos", "produto"), ("departamentos", "departamento")):
        for cod, g in agrupar(itens, por).items():
            hist[tipo].setdefault(cod, {})[chave] = g["valor"]
            if g["nome"]:
                nomes[tipo].setdefault(cod, g["nome"])


def _resultado_historico(datas, rotulos, hist, nomes, sem_vendas, unidade,
                         periodo_txt, arquivo_txt):
    return {"datas": datas, "rotulos": rotulos, "produtos": hist["produtos"],
            "departamentos": hist["departamentos"], "nomes": nomes,
            "dias_sem_vendas": sem_vendas, "unidade": unidade,
            "periodo_txt": periodo_txt, "arquivo_txt": arquivo_txt}


def _historico_por_dia(dias, itens_dia):
    """Uma coluna por dia (ver historico_vendas)."""
    hist = {"produtos": {}, "departamentos": {}}
    nomes = {"produtos": {}, "departamentos": {}}
    sem_vendas = []
    for data in dias:
        itens = itens_dia.get(data, [])
        if not itens:
            sem_vendas.append(data)
            continue
        _acumular(hist, nomes, itens, data)
    rotulos = {d: f"{cfg.DIAS_SEMANA[datetime.strptime(d, cfg.FMT_DATA).weekday()]} "
                  f"{d[:5].replace('-', '/')}" for d in dias}
    return _resultado_historico(dias, rotulos, hist, nomes, sem_vendas, "dia",
                                f"{dias[0]} a {dias[-1]}", f"{dias[0]}_a_{dias[-1]}")


def _historico_por_faixa(dias, itens_dia, hora_ini, hora_fim, intervalo_min):
    """Uma coluna por faixa de intervalo_min minutos em cada dia (ver historico_vendas)."""
    hist = {"produtos": {}, "departamentos": {}}
    nomes = {"produtos": {}, "departamentos": {}}
    sem_vendas = []
    h0 = min_hora(hora_ini or cfg.HORA_MIN)
    h1 = min_hora(hora_fim or cfg.HORA_MAX)
    datas, rotulos = [], {}
    for data in dias:
        faixas = {}
        for i in itens_dia.get(data, []):
            if not i.get("hora"):
                continue
            m = min_hora(i["hora"])
            if m >= h0:
                faixas.setdefault(faixa(m, intervalo_min, h0), []).append(i)
        for m in range(h0, h1 + 1, intervalo_min):
            chave = f"{data} {hora_min(m)}"
            datas.append(chave)
            rotulos[chave] = (hora_min(m) if len(dias) == 1
                              else f"{data[:5].replace('-', '/')} {hora_min(m)}")
            if m in faixas:
                _acumular(hist, nomes, faixas[m], chave)
            else:
                sem_vendas.append(chave)
    passo = f"de {intervalo_min} em {intervalo_min} min"
    dias_txt = dias[0] if len(dias) == 1 else f"{dias[0]} a {dias[-1]}"
    periodo_txt = f"{dias_txt} | {hora_min(h0)} às {hora_min(h1)}, {passo}"
    arquivo_txt = (f"{dias_txt.replace(' a ', '_a_')}_{hora_min(h0).replace(':', 'h')}_a_"
                   f"{hora_min(h1).replace(':', 'h')}_{intervalo_min}min")
    return _resultado_historico(datas, rotulos, hist, nomes, sem_vendas, "faixa",
                                periodo_txt, arquivo_txt)


def aplicar_grupos(hist, tipo, grupos):
    """Acrescenta, em hist[tipo], UMA linha por grupo com a soma dos membros, coluna a
    coluna (as colunas já têm o intervalo escolhido: dia ou faixa de minutos). O grupo é
    uma visão EXTRA: os membros continuam em hist[tipo] e um item pode estar em mais de
    um grupo. `grupos` = {nome: códigos}. A linha do grupo usa a chave
    cfg.PREFIXO_GRUPO + nome (o nome vai em hist["nomes"][tipo]); quem soma os itens
    (ex.: TOTAL DO DIA) deve ignorar as chaves de grupo, senão conta em dobro. Grupo sem
    nenhum membro com venda no período não aparece. Retorna um novo hist (o original não
    muda), com "composicao_grupos": {chave do grupo: [nomes dos itens]}."""
    dados = {c: dict(v) for c, v in hist[tipo].items()}
    nomes = dict(hist["nomes"][tipo])
    composicao = {}
    for nome, cods in grupos.items():
        membros = [c for c in cods if c in hist[tipo]]
        if not membros:
            continue
        chave = cfg.PREFIXO_GRUPO + nome
        soma = {}
        for c in membros:
            for col, v in hist[tipo][c].items():
                soma[col] = soma.get(col, 0.0) + v
        dados[chave] = {col: round(v, 2) for col, v in soma.items()}
        composicao[chave] = sorted(nomes.get(c) or c for c in membros)
        nomes[chave] = nome
    novo = dict(hist)
    novo[tipo] = dados
    novo["nomes"] = {**hist["nomes"], tipo: nomes}
    novo["composicao_grupos"] = composicao
    return novo


# ── Estado da seleção e dos grupos (sem Tk) ──────────────────────────────────

TIPOS = ("produtos", "departamentos")
_POR = {"produtos": "produto", "departamentos": "departamento"}


class Grupos:
    def __init__(self):
        self.nomes = {t: {} for t in TIPOS}       # código -> nome (dados carregados)
        self.valores = {t: {} for t in TIPOS}     # código -> arrecadado
        self.selecao = {t: set() for t in TIPOS}  # chaves marcadas (itens e grupos)
        self.grupos = {t: {} for t in TIPOS}      # nome do grupo -> {códigos}

    # ── Dados carregados ─────────────────────────────────────────────────────

    def receber(self, itens):
        """Atualiza nomes e valores com as vendas (re)carregadas. Grupo sem nenhum
        membro nos dados novos é removido; a seleção descarta o que sumiu."""
        for tipo in TIPOS:
            dados = agrupar(itens, _POR[tipo])
            self.nomes[tipo] = {c: g["nome"] for c, g in dados.items()}
            self.valores[tipo] = {c: g["valor"] for c, g in dados.items()}
            for nome in [n for n, cods in self.grupos[tipo].items() if not cods & set(dados)]:
                del self.grupos[tipo][nome]
            self.selecao[tipo] &= set(dados) | {cfg.PREFIXO_GRUPO + n for n in self.grupos[tipo]}

    def itens_lista(self, tipo, rotulo):
        """Itens da lista de filtro: TODOS os itens (os que estão em grupo ganham, no fim do
        texto, o nome do(s) grupo(s)) + um item por grupo. `rotulo(cod, nomes)` dá o texto
        de um item. Retorna ({chave: texto}, {chave: arrecadado})."""
        nomes, valores = self.nomes[tipo], self.valores[tipo]
        em_grupo = {}                                  # código -> nomes dos grupos dele
        for nome, cods in self.grupos[tipo].items():
            for c in cods:
                em_grupo.setdefault(c, []).append(nome)
        textos, totais = {}, {}
        for c in nomes:
            textos[c], totais[c] = rotulo(c, nomes), valores.get(c, 0.0)
            if c in em_grupo:
                textos[c] += "  · " + ", ".join(sorted(em_grupo[c], key=str.lower))
        for nome, cods in self.grupos[tipo].items():
            chave = cfg.PREFIXO_GRUPO + nome
            n = sum(1 for c in cods if c in nomes)
            textos[chave] = f"Σ {nome} ({n} {'item' if n == 1 else 'itens'})"
            totais[chave] = sum(valores.get(c, 0.0) for c in cods)
        return textos, totais

    # ── Seleção ──────────────────────────────────────────────────────────────

    def atualizar_selecao(self, tipo, visiveis, marcados):
        """`visiveis`: chaves mostradas na lista, na ordem; `marcados`: posições
        marcadas nela. O que está fora da lista (filtrado pela busca) não muda."""
        marcados = set(marcados)
        for i, c in enumerate(visiveis):
            if i in marcados:
                self.selecao[tipo].add(c)
            else:
                self.selecao[tipo].discard(c)

    def marcar_todos(self, tipo, chaves):
        self.selecao[tipo].update(chaves)

    def limpar_selecao(self, tipo):
        self.selecao[tipo].clear()

    # ── Agrupar / desagrupar ─────────────────────────────────────────────────

    def pode_agrupar(self, tipo):
        return len(self.selecao[tipo]) >= 2

    def nomes_para_novo_grupo(self, tipo):
        """(nome padrão, nomes em uso em minúsculas) para pedir o nome do novo grupo.
        Grupos marcados continuam existindo, então seus nomes também estão em uso."""
        usados = {n.lower() for n in self.grupos[tipo]}
        n = 1
        while f"grupo_{n}" in usados:
            n += 1
        return f"Grupo_{n}", usados

    def agrupar(self, tipo, nome):
        """Cria o grupo `nome` com os itens marcados e os itens dos grupos marcados; os
        grupos marcados continuam existindo. O novo grupo fica como única marcação."""
        pref = cfg.PREFIXO_GRUPO
        membros = set()
        for k in set(self.selecao[tipo]):
            if k.startswith(pref):
                membros |= self.grupos[tipo].get(k[len(pref):], set())
            else:
                membros.add(k)
        self.grupos[tipo][nome] = membros
        self.selecao[tipo] = {pref + nome}

    def tem_grupo_marcado(self, tipo):
        return any(k.startswith(cfg.PREFIXO_GRUPO) for k in self.selecao[tipo])

    def desagrupar(self, tipo):
        """Desfaz os grupos marcados; os itens deles (que nunca saem da lista) ficam marcados."""
        pref = cfg.PREFIXO_GRUPO
        for k in [k for k in self.selecao[tipo] if k.startswith(pref)]:
            membros = self.grupos[tipo].pop(k[len(pref):], set())
            self.selecao[tipo].discard(k)
            self.selecao[tipo] |= {c for c in membros if c in self.nomes[tipo]}

    # ── Para gerar o histórico ───────────────────────────────────────────────

    def para_exportar(self, tipo):
        """(cópia dos grupos {nome: {códigos}}, cópia da seleção) do tipo."""
        return ({n: set(c) for n, c in self.grupos[tipo].items()},
                set(self.selecao[tipo]))
