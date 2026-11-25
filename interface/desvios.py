"""
desvios.py — aba "Desvios do dia": analisa cada dia do período da barra contra os mesmos
dias da semana das últimas semanas e, para o dia escolhido na lista, mostra: se há desvio,
se é uma venda pontual, quando aconteceu, se vieram mais vendas ou um ticket diferente,
quem puxou (departamentos e produtos, em abas separadas) e se foi quantidade ou preço.

Dois estados: depois de Analisar só a tabela de dias aparece; ao escolher um dia, a tabela
encolhe para a linha dele, aparecem os detalhes e o botão "Selecionar dia" (ao lado do
Analisar) volta ao estado anterior.

Usa as DATAS da barra de período (as horas são ignoradas: o passo "quando" acha sozinho o
horário do desvio) e não depende do "Carregar vendas": lê o que precisa por conta própria.
Cálculos em relatorios/desvios.py; os textos em texto_desvios.py.
"""

import tkinter as tk
from tkinter import font as tkfont
from tkinter import messagebox, ttk

import config as cfg
from banco import FONTE_PADRAO
from relatorios.desvios import analisar_periodo, principais

from .formato import brl, dkey, qtde
from .texto_desvios import linha_lista, linhas_resumo, n1, n1s, nome_de, rs

_COR = {"alto": "#e2f0d9", "baixo": "#fce4d6", "destaque": "#fff2cc"}

_LISTA_COL = ("data", "dia", "fat", "fat_esp", "vendas", "ven_esp", "resultado")
_LISTA_CAB = {"data": "Data", "dia": "Dia", "fat": "Faturamento", "fat_esp": "Esperado",
              "vendas": "Vendas", "ven_esp": "Esperado", "resultado": "Resultado"}
_LISTA_LARG = {"data": 90, "dia": 50, "fat": 110, "fat_esp": 110, "vendas": 70,
               "ven_esp": 80, "resultado": 300}

_HOR_COL = ("faixa", "esp_valor", "valor", "delta_valor", "esp_vendas", "vendas",
            "delta_vendas", "obs")
_HOR_CAB = {"faixa": "Faixa", "esp_valor": "Esperado", "valor": "Real", "delta_valor": "Δ R$",
            "esp_vendas": "Vendas esp.", "vendas": "Vendas", "delta_vendas": "Δ vendas",
            "obs": ""}
_HOR_LARG = {"faixa": 120, "esp_valor": 110, "valor": 110, "delta_valor": 110,
             "esp_vendas": 90, "vendas": 80, "delta_vendas": 90, "obs": 150}

_DEP_COL = ("nome", "esperado", "real", "delta", "qtde", "preco", "peso")
_DEP_CAB = {"nome": "Departamento", "esperado": "Esperado", "real": "Real", "delta": "Δ R$",
            "qtde": "Por quantidade", "preco": "Por preço", "peso": "Peso"}
_DEP_LARG = {"nome": 200, "esperado": 100, "real": 100, "delta": 100,
             "qtde": 110, "preco": 100, "peso": 60}

_PROD_COL = ("nome", "dep", "esperado", "real", "delta", "qtde", "preco", "peso",
             "qtds", "precos", "obs")
_PROD_CAB = {"nome": "Produto", "dep": "Departamento", "esperado": "Esperado", "real": "Real",
             "delta": "Δ R$", "qtde": "Por quantidade", "preco": "Por preço",
             "peso": "Peso", "qtds": "Qtde (esp. → real)", "precos": "Preço unit. (esp. → real)",
             "obs": ""}
_PROD_LARG = {"nome": 200, "dep": 120, "esperado": 90, "real": 90, "delta": 90,
              "qtde": 100, "preco": 90, "peso": 55, "qtds": 130, "precos": 170, "obs": 130}


_ALTURA_LISTA = 5       # linhas visíveis da lista de dias (com um dia escolhido, 1)


def _tabela(pai, colunas, cabecalhos, larguras, esquerda=("nome",), altura=8, mostrar="headings"):
    """Treeview com barras de rolagem. Retorna (quadro, tree); o quadro é quem se posiciona."""
    quadro = ttk.Frame(pai)
    tree = ttk.Treeview(quadro, columns=colunas, show=mostrar, selectmode="browse",
                        height=altura)
    for c in colunas:
        tree.heading(c, text=cabecalhos[c])
        tree.column(c, width=larguras[c], anchor="w" if c in esquerda else "e")
    vert = ttk.Scrollbar(quadro, orient="vertical", command=tree.yview)
    horiz = ttk.Scrollbar(quadro, orient="horizontal", command=tree.xview)
    tree.configure(yscrollcommand=vert.set, xscrollcommand=horiz.set)
    tree.grid(row=0, column=0, sticky="nsew")
    vert.grid(row=0, column=1, sticky="ns")
    horiz.grid(row=1, column=0, sticky="ew")
    quadro.rowconfigure(0, weight=1)
    quadro.columnconfigure(0, weight=1)
    for tag, cor in _COR.items():
        tree.tag_configure(tag, background=cor)
    tree.tag_configure("semdados", foreground="#888888")
    tree.tag_configure("demais", foreground="#666666")
    return quadro, tree


def _limpar(tree):
    tree.delete(*tree.get_children())


def _tag_delta(v):
    return ("alto",) if v > 0 else ("baixo",) if v < 0 else ()


class AbaDesvios(ttk.Frame):
    def __init__(self, pai, app):
        super().__init__(pai, padding=10)
        self.app = app
        self.resultado = None       # último resultado de analisar_periodo
        self.por_data = {}          # {data: análise do dia}
        self.dia = None             # análise do dia selecionado na lista
        self.filtro_dep = None      # departamento escolhido na tabela de participantes
        self._ordem = []            # datas na ordem da lista (para reexibir as linhas escondidas)
        self._trocando = False      # True enquanto o código mexe na lista/seleção
        self._montar()

    # ── Montagem ─────────────────────────────────────────────────────────────

    def _montar(self):
        topo = ttk.Frame(self)
        topo.pack(fill="x")
        ttk.Label(topo, text="Base: últimas").pack(side="left")
        self.spin_semanas = ttk.Spinbox(topo, from_=cfg.SEMANAS_MIN, to=cfg.SEMANAS_MAX, width=4)
        self.spin_semanas.set(8)
        self.spin_semanas.pack(side="left", padx=4)
        ttk.Label(topo, text="semanas   Faixa").pack(side="left")
        self.spin_passo = ttk.Spinbox(topo, from_=cfg.PASSO_MIN, to=cfg.PASSO_MAX, increment=5,
                                      width=4)
        self.spin_passo.set(60)
        self.spin_passo.pack(side="left", padx=4)
        ttk.Label(topo, text="min").pack(side="left")
        self.btn = ttk.Button(topo, text="Analisar (F7)", command=self.analisar)
        self.btn.pack(side="right")
        # Só aparece com um dia escolhido; empacotado depois do Analisar, fica à esquerda dele.
        self.btn_sel = ttk.Button(topo, text="Selecionar dia", command=self._modo_lista)
        ttk.Label(self, foreground="#666666", wraplength=820, justify="left",
                  text="Analisa cada dia do período da barra (horas ignoradas) contra os "
                       "mesmos dias da semana. Escolha um dia na lista para ver os detalhes."
                  ).pack(anchor="w", pady=(6, 6))

        # Lista de dias em cima; os detalhes só entram (embaixo) com um dia escolhido.
        self.cima = ttk.Frame(self)
        self.cima.pack(fill="both", expand=True)
        self.quadro_lista, self.tree = _tabela(
            self.cima, _LISTA_COL, _LISTA_CAB, _LISTA_LARG,
            esquerda=("data", "dia", "resultado"), altura=_ALTURA_LISTA)
        self.quadro_lista.pack(fill="both", expand=True)
        self.tree.bind("<<TreeviewSelect>>", self._selecionar)
        self.var_ignorados = tk.StringVar()
        self.lbl_ignorados = ttk.Label(self.cima, textvariable=self.var_ignorados,
                                       foreground="#b45f06", wraplength=820, justify="left")
        self.lbl_ignorados.pack(anchor="w", pady=(4, 6))
        self.det = ttk.Notebook(self)       # empacotado só em _modo_detalhe
        self._montar_resumo()
        self._montar_horario()
        self._montar_participantes()
        self._montar_vendas()

    def _montar_resumo(self):
        quadro = ttk.Frame(self.det, padding=4)
        base = tkfont.nametofont("TkDefaultFont")
        self._fonte_passo = tkfont.Font(font=base)
        self._fonte_passo.configure(weight="bold")
        self._fonte_titulo = tkfont.Font(font=base)
        self._fonte_titulo.configure(weight="bold", size=base.cget("size") + 3)
        self.txt = tk.Text(quadro, wrap="word", height=10, font=base, padx=8, pady=6,
                           relief="flat", borderwidth=0, state="disabled")
        self.txt.tag_configure("titulo", font=self._fonte_titulo)
        self.txt.tag_configure("passo", font=self._fonte_passo)
        self.txt.tag_configure("ok", foreground="#2e7d32")
        self.txt.tag_configure("alerta", foreground="#b45f06")
        self.txt.tag_configure("cinza", foreground="#666666")
        rolagem = ttk.Scrollbar(quadro, orient="vertical", command=self.txt.yview)
        self.txt.configure(yscrollcommand=rolagem.set)
        self.txt.pack(side="left", fill="both", expand=True)
        rolagem.pack(side="right", fill="y")
        self.det.add(quadro, text="  Resumo  ")
        self._aba_resumo = quadro

    def _montar_horario(self):
        quadro = ttk.Frame(self.det, padding=6)
        self.var_hor_info = tk.StringVar()
        ttk.Label(quadro, textvariable=self.var_hor_info, foreground="#666666",
                  wraplength=820, justify="left").pack(anchor="w", pady=(0, 4))
        tabela, self.tree_hor = _tabela(quadro, _HOR_COL, _HOR_CAB, _HOR_LARG,
                                        esquerda=("faixa", "obs"))
        tabela.pack(fill="both", expand=True)
        self.det.add(quadro, text="  Horário  ")
        self._aba_horario = quadro

    def _montar_participantes(self):
        """Duas abas independentes: Departamentos e Produtos. O filtro de produtos por
        departamento é um seletor na própria aba Produtos."""
        self.var_part_info = tk.StringVar()      # a mesma explicação nas duas abas
        # Departamentos
        quadro = ttk.Frame(self.det, padding=6)
        ttk.Label(quadro, textvariable=self.var_part_info, foreground="#666666",
                  wraplength=820, justify="left").pack(anchor="w", pady=(0, 4))
        tab_dep, self.tree_dep = _tabela(quadro, _DEP_COL, _DEP_CAB, _DEP_LARG, altura=8)
        tab_dep.pack(fill="both", expand=True)
        self.det.add(quadro, text="  Departamentos  ")
        self._aba_dep = quadro
        # Produtos
        quadro = ttk.Frame(self.det, padding=6)
        ttk.Label(quadro, textvariable=self.var_part_info, foreground="#666666",
                  wraplength=820, justify="left").pack(anchor="w", pady=(0, 4))
        sel = ttk.Frame(quadro)
        sel.pack(fill="x", pady=(2, 4))
        ttk.Label(sel, text="Departamento:").pack(side="left")
        self.combo_dep = ttk.Combobox(sel, state="readonly", width=34, values=[])
        self.combo_dep.pack(side="left", padx=6)
        self.combo_dep.bind("<<ComboboxSelected>>", self._filtrar_produtos)
        self._cods_combo = []        # código do departamento de cada opção (após "Todos")
        tab_prod, self.tree_prod = _tabela(quadro, _PROD_COL, _PROD_CAB, _PROD_LARG,
                                           esquerda=("nome", "dep", "obs"))
        tab_prod.pack(fill="both", expand=True)
        self.det.add(quadro, text="  Produtos  ")
        self._aba_prod = quadro

    def _montar_vendas(self):
        quadro = ttk.Frame(self.det, padding=6)
        self.var_vendas_info = tk.StringVar()
        ttk.Label(quadro, textvariable=self.var_vendas_info, foreground="#666666",
                  wraplength=820, justify="left").pack(anchor="w", pady=(0, 4))
        cab = {"hora": "Hora", "valor": "Valor", "x": "× ticket esperado", "qtde": "Qtde"}
        larg = {"hora": 70, "valor": 110, "x": 130, "qtde": 80}
        tabela, self.tree_vendas = _tabela(quadro, ("hora", "valor", "x", "qtde"), cab, larg,
                                           esquerda=(), mostrar="tree headings")
        self.tree_vendas.heading("#0", text="Venda / item")
        self.tree_vendas.column("#0", width=380, anchor="w")
        tabela.pack(fill="both", expand=True)
        self.det.add(quadro, text="  Maiores vendas  ")
        self._aba_vendas = quadro

    def definir_ocupado(self, ocupado):
        estado = "disabled" if ocupado else "normal"
        self.btn.configure(state=estado)
        self.btn_sel.configure(state=estado)

    # ── Análise ──────────────────────────────────────────────────────────────

    def analisar(self):
        app = self.app
        if app.ocupado:
            return
        periodo = app.ler_periodo()
        if periodo is None:
            return
        ini, fim = periodo[0], periodo[1]
        if (dkey(fim) - dkey(ini)).days + 1 > cfg.MAX_DIAS_DESVIOS:
            messagebox.showwarning("Desvios do dia", f"Use no máximo {cfg.MAX_DIAS_DESVIOS} "
                                   "dias no período.", parent=app.root)
            return
        try:
            semanas = int(self.spin_semanas.get())
            passo = int(self.spin_passo.get())
        except ValueError:
            semanas = passo = 0
        if not (cfg.SEMANAS_MIN <= semanas <= cfg.SEMANAS_MAX
                and cfg.PASSO_MIN <= passo <= cfg.PASSO_MAX):
            messagebox.showwarning("Desvios do dia", f"Use de {cfg.SEMANAS_MIN} a "
                                   f"{cfg.SEMANAS_MAX} semanas e faixas de {cfg.PASSO_MIN} a "
                                   f"{cfg.PASSO_MAX} minutos.", parent=app.root)
            return

        def tarefa():
            return analisar_periodo(FONTE_PADRAO, ini, fim, semanas, passo)

        def ao_terminar(res):
            self.resultado = res
            self._mostrar_lista()
            app.ocupar(False, "Análise de desvios concluída.")

        app.ocupar(True, "Analisando desvios (lendo o período e as semanas da base)...")
        app.executor.rodar(tarefa, ao_terminar, lambda e: app.erro("Erro na análise de desvios", e))

    # ── Lista de dias ────────────────────────────────────────────────────────

    def _mostrar_lista(self):
        res = self.resultado
        self._trocando = True
        if self._ordem:
            self.tree.delete(*self._ordem)  # inclui as linhas escondidas (get_children não as vê)
        self._trocando = False
        self.por_data = {a["data"]: a for a in res["dias"]}
        self._ordem = [a["data"] for a in res["dias"]]
        for a in res["dias"]:
            valores, tag = linha_lista(a)
            self.tree.insert("", "end", iid=a["data"], values=valores, tags=(tag,) if tag else ())
        aviso = ("Fora da análise: " + "; ".join(
            f"{d[:5].replace('-', '/')} ({motivo})" for d, motivo in res["ignorados"])
            if res["ignorados"] else "")
        if not res["dias"]:
            aviso = " ".join(x for x in ("Nenhum dia encerrado no período.", aviso) if x)
        self.var_ignorados.set(aviso)
        # Depois de Analisar, só a tabela de dias: nenhum dia vem escolhido.
        self._modo_lista()

    # ── Estados da tela: lista de dias x detalhes de um dia ──────────────────

    def _modo_lista(self):
        """Estado inicial: tabela de dias inteira; detalhes e botão "Selecionar dia" saem."""
        self._trocando = True
        try:
            self.det.pack_forget()
            self.btn_sel.pack_forget()
            for n, data in enumerate(self._ordem):
                self.tree.move(data, "", n)             # reexibe as linhas escondidas
            self.tree.selection_remove(*self.tree.selection())
            self.tree.configure(height=_ALTURA_LISTA)
            self.quadro_lista.pack_configure(fill="both", expand=True)
            self.cima.pack_configure(fill="both", expand=True)
            self.lbl_ignorados.pack(anchor="w", pady=(4, 6))
        finally:
            self._trocando = False
        self.dia = None
        self.filtro_dep = None
        self._limpar_detalhes()

    def _modo_detalhe(self, data):
        """Dia escolhido: a tabela encolhe para a linha dele e os detalhes aparecem."""
        self._trocando = True
        try:
            for outra in self._ordem:
                if outra != data:
                    self.tree.detach(outra)
            self.tree.selection_remove(*self.tree.selection())   # sem o azul da seleção
            self.tree.configure(height=1)
            self.quadro_lista.pack_configure(fill="x", expand=False)
            self.cima.pack_configure(fill="x", expand=False)
            self.lbl_ignorados.pack_forget()
            self.det.pack(fill="both", expand=True)
            self.btn_sel.pack(side="right", padx=(0, 6))
        finally:
            self._trocando = False

    def _selecionar(self, _evento=None):
        if self._trocando:
            return
        sel = self.tree.selection()
        if not sel or sel[0] not in self.por_data:
            return
        self.dia = self.por_data[sel[0]]
        self.filtro_dep = None
        self._escrever(linhas_resumo(self.dia))
        self._mostrar_horario(self.dia)
        self._mostrar_participantes(self.dia)
        self._mostrar_vendas(self.dia)
        self._ajustar_abas(self.dia)
        self._modo_detalhe(sel[0])

    def _ajustar_abas(self, a):
        """Esconde as abas sem conteúdo no dia (só teriam uma mensagem; o Resumo já explica
        por que a análise parou). O Resumo nunca some."""
        com_conteudo = {self._aba_horario: bool(a.get("horario")),
                        self._aba_dep: bool(a.get("participantes")),
                        self._aba_prod: bool(a.get("participantes")),
                        self._aba_vendas: bool(a.get("maiores_vendas"))}
        for aba, tem in com_conteudo.items():
            self.det.tab(aba, state="normal" if tem else "hidden")
        if self.det.tab(self.det.select(), "state") != "normal":
            self.det.select(self._aba_resumo)

    def _limpar_detalhes(self, mensagem=""):
        self._escrever([("cinza", mensagem)] if mensagem else [])
        for tree in (self.tree_hor, self.tree_dep, self.tree_prod, self.tree_vendas):
            _limpar(tree)
        for var in (self.var_hor_info, self.var_part_info, self.var_vendas_info):
            var.set("")
        self._preencher_combo([])

    def _escrever(self, segmentos):
        self.txt.configure(state="normal")
        self.txt.delete("1.0", "end")
        for estilo, texto in segmentos:
            self.txt.insert("end", texto, estilo)
        self.txt.configure(state="disabled")
        self.txt.yview_moveto(0)

    @staticmethod
    def _sem_analise(a):
        """Por que as abas de detalhe estão vazias neste dia."""
        return {"sem_vendas": "Dia sem vendas.",
                "sem_base": "Poucos dias comparáveis na base: não dá para avaliar este dia.",
                "normal": "Dia dentro do padrão: a análise terminou no primeiro passo.",
                "pontual": "O desvio é uma venda pontual: a análise terminou no segundo passo."
                }.get(a["veredito"], "")

    # ── Horário ──────────────────────────────────────────────────────────────

    def _mostrar_horario(self, a):
        _limpar(self.tree_hor)
        h = a.get("horario")
        if not h:
            self.var_hor_info.set(self._sem_analise(a) or "Sem horário de venda para analisar.")
            return
        j = h["janela"]
        ind = "faturamento" if h["indicador"] == "valor" else "número de vendas"
        info = f"Faixas de {self.resultado['passo_min']} min · desvio medido em {ind}"
        if j is None:
            info += " · nenhuma faixa se destaca."
        elif j["espalhado"]:
            info += " · desvio espalhado pelo dia (nenhuma janela menor concentra a maior parte)."
        else:
            info += (f" · o desvio se concentra entre {j['inicio']} e {j['fim']} "
                     f"({j['fracao'] * 100:.0f}% dele).")
        if a["analisado"]["removido"]:
            info += " Dia sem a venda pontual."
        self.var_hor_info.set(info)
        for n, f in enumerate(h["faixas"]):
            na_janela = j is not None and j["primeira"] <= n <= j["ultima"]
            self.tree_hor.insert("", "end", tags=("destaque",) if na_janela else (), values=(
                f"{f['inicio']} – {f['fim']}", brl(f["esp_valor"]), brl(f["valor"]),
                rs(f["delta_valor"]), n1(f["esp_vendas"]), str(f["vendas"]),
                n1s(f["delta_vendas"]), "◄ janela do desvio" if na_janela else ""))

    # ── Departamentos e produtos ─────────────────────────────────────────────

    def _mostrar_participantes(self, a):
        _limpar(self.tree_dep)
        _limpar(self.tree_prod)
        self._preencher_combo([])
        P = a.get("participantes")
        if not P:
            self.var_part_info.set(self._sem_analise(a))
            return
        self._preencher_combo(P["departamentos"])
        info = (f"Esperado = média de {a['base']['dias']} dias da base · Δ = real − esperado · "
                "Peso = parcela de cada linha na movimentação do dia")
        if a["analisado"]["removido"]:
            info += (f" · dia SEM a venda pontual de {brl(a['analisado']['removido'])} "
                     "(comparado com a base também sem a maior venda de cada dia)")
        self.var_part_info.set(info + ".")
        # Todos os departamentos, um por linha: os que entram no desvio levam a cor do sinal
        # (verde/laranja); os demais (fora do corte de `principais`) ficam sem cor.
        mostradas, _ = principais(P["departamentos"])
        for n, d in enumerate(P["departamentos"]):
            tags = _tag_delta(d["delta"]) if n < len(mostradas) else ()
            self.tree_dep.insert("", "end", iid=str(d["cod"]), tags=tags,
                                 values=self._valores_agregados(d))
        self._mostrar_produtos()

    def _preencher_combo(self, departamentos):
        """Opções do seletor da aba Produtos: "Todos os departamentos" e, em ordem alfabética,
        os departamentos do dia. Sempre volta a "Todos"."""
        opcoes = sorted(((nome_de(d), str(d["cod"])) for d in departamentos),
                        key=lambda x: x[0].casefold())
        self._cods_combo = [cod for _, cod in opcoes]
        self.filtro_dep = None
        if departamentos:
            self.combo_dep.configure(values=["Todos os departamentos"] + [n for n, _ in opcoes],
                                     state="readonly")
            self.combo_dep.current(0)
        else:
            self.combo_dep.configure(values=[], state="disabled")
            self.combo_dep.set("")

    @staticmethod
    def _valores_agregados(x):
        return (nome_de(x), brl(x["esperado"]), brl(x["real"]), rs(x["delta"]),
                rs(x["efeito_qtde"]), rs(x["efeito_preco"]),
                f"{x['peso'] * 100:.0f}%")

    def _mostrar_produtos(self):
        _limpar(self.tree_prod)
        a = self.dia
        P = a.get("participantes") if a else None
        if not P:
            return
        linhas = [p for p in P["produtos"]
                  if self.filtro_dep is None or str(p["cod_depart"]) == self.filtro_dep]
        mostradas, demais = principais(linhas)
        for p in mostradas:
            esp_p = brl(p["esp_preco"]) if p["esp_preco"] is not None else ""
            preco = brl(p["preco"]) if p["preco"] is not None else ""
            self.tree_prod.insert("", "end", tags=_tag_delta(p["delta"]), values=(
                nome_de(p), nome_de({"nome": p["departamento"], "cod": p["cod_depart"]}),
                brl(p["esperado"]), brl(p["real"]), rs(p["delta"]),
                rs(p["efeito_qtde"]), rs(p["efeito_preco"]), f"{p['peso'] * 100:.0f}%",
                f"{n1(p['esp_qtde'])} → {qtde(p['qtde'])}",
                f"{esp_p} → {preco}" if esp_p or preco else "", p["obs"]))
        if demais:
            self.tree_prod.insert("", "end", tags=("demais",), values=(
                demais["nome"], "", brl(demais["esperado"]), brl(demais["real"]),
                rs(demais["delta"]), rs(demais["efeito_qtde"]),
                rs(demais["efeito_preco"]), f"{demais['peso'] * 100:.0f}%", "", "", ""))

    def _filtrar_produtos(self, _evento=None):
        n = self.combo_dep.current()          # 0 = "Todos os departamentos"
        self.filtro_dep = self._cods_combo[n - 1] if n > 0 else None
        self._mostrar_produtos()

    # ── Maiores vendas ───────────────────────────────────────────────────────

    def _mostrar_vendas(self, a):
        _limpar(self.tree_vendas)
        vendas = a.get("maiores_vendas")
        if not vendas:
            self.var_vendas_info.set(self._sem_analise(a))
            return
        p = a["pontual"]
        retiradas = p["k"] if p["aplicavel"] and p["resultado"] in ("total", "parcial") else 0
        self.var_vendas_info.set(
            f"As {len(vendas)} maiores vendas do dia (ticket médio esperado "
            f"{brl(a['ticket']['esperado'])})."
            + (" As destacadas foram retiradas no teste de venda pontual." if retiradas else ""))
        for n, v in enumerate(vendas):
            x = f"{n1(v['x_ticket'])}×" if v.get("x_ticket") else ""
            titulo = f"{n + 1}ª maior venda" + (" — retirada na análise" if n < retiradas else "")
            pai = self.tree_vendas.insert(
                "", "end", text=titulo, open=True, tags=("destaque",) if n < retiradas else (),
                values=(v["hora"], brl(v["valor"]), x, ""))
            for i in v["itens"]:
                self.tree_vendas.insert(pai, "end", text="    " + (i["nome"] or str(i["cod"])),
                                        values=("", brl(i["valor"]), "", qtde(i["qtde"])))
