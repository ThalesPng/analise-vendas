"""
historico.py — aba "Histórico (Excel)": sem tela de resultado própria; o resultado
é a planilha .xlsx com o gráfico (o Excel mostra a tabela e o gráfico). Aqui só se
escolhe o que entra: produtos ou departamentos, soma por dia ou por faixa de minutos e
quais itens entram no gráfico (seleção individual ou "Marcar todos" os itens da busca;
sem seleção, os 10 maiores). Os itens marcados podem ser agrupados: o grupo vira um item
da lista que soma seus membros no mesmo intervalo (dia ou faixa de minutos).
Recebe os itens carregados em receber() para montar a lista de filtro. O estado
(seleção e grupos) fica em relatorios.historico.Grupos, sem Tk; aqui só se desenha e se repassam os cliques.
"""

import tkinter as tk
from tkinter import messagebox, ttk

import config as cfg
from banco import FONTE_PADRAO
from excel import abrir_arquivo, exportar_historico_xlsx
from relatorios.historico import Grupos, aplicar_grupos, historico_vendas

from .formato import dkey, rotulo
from .widgets import pedir_nome


class AbaHistorico(ttk.Frame):
    def __init__(self, pai, app):
        super().__init__(pai, padding=10)
        self.app = app
        self.estado = Grupos()      # seleção, grupos e totais por item (sem Tk)
        self.visiveis = []          # códigos mostrados na lista de filtro
        self._montar()

    def _montar(self):
        f = self

        ttk.Label(f, text="O histórico é gerado como planilha .xlsx com gráfico de linhas "
                          "e aberto no Excel.", foreground="#666").pack(anchor="w")

        opcoes = ttk.Frame(f)
        opcoes.pack(fill="x", pady=(8, 0))

        # Tipo
        lf = ttk.LabelFrame(opcoes, text="Relatório", padding=8)
        lf.pack(side="left", fill="y")
        self.var_hist = tk.StringVar(value="produtos")
        ttk.Radiobutton(lf, text="Produtos", value="produtos", variable=self.var_hist,
                        command=self._preencher_lista).pack(anchor="w")
        ttk.Radiobutton(lf, text="Departamentos", value="departamentos",
                        variable=self.var_hist,
                        command=self._preencher_lista).pack(anchor="w")

        # Soma
        lf = ttk.LabelFrame(opcoes, text="Soma", padding=8)
        lf.pack(side="left", fill="y", padx=10)
        self.var_modo = tk.StringVar(value="dia")
        ttk.Radiobutton(lf, text="Por dia", value="dia", variable=self.var_modo
                        ).grid(row=0, column=0, columnspan=3, sticky="w")
        ttk.Radiobutton(lf, text="Por faixa de", value="faixa", variable=self.var_modo
                        ).grid(row=1, column=0, sticky="w")
        self.spin_min = ttk.Spinbox(lf, from_=cfg.INTERVALO_MIN, to=cfg.INTERVALO_MAX, width=6)
        self.spin_min.set(60)
        self.spin_min.grid(row=1, column=1, padx=4)
        ttk.Label(lf, text="minutos").grid(row=1, column=2, sticky="w")
        ttk.Label(lf, text="Com um único dia, \"Por dia\" soma de hora em hora.",
                  foreground="#666").grid(row=2, column=0, columnspan=3, sticky="w", pady=(4, 0))

        # Filtro individual
        flt = ttk.LabelFrame(f, text="Itens do gráfico", padding=8)
        flt.pack(fill="both", expand=True, pady=(10, 0))
        linha = ttk.Frame(flt)
        linha.pack(fill="x")
        ttk.Label(linha, text="Buscar").pack(side="left")
        self.var_busca = tk.StringVar()
        self.var_busca.trace_add("write", self._preencher_lista)
        ttk.Entry(linha, textvariable=self.var_busca, width=30).pack(side="left", padx=6)
        ttk.Button(linha, text="Marcar todos", command=self._marcar_todos).pack(side="left")
        ttk.Button(linha, text="Limpar seleção", command=self._limpar_selecao,
                   ).pack(side="left", padx=(6, 0))
        ttk.Button(linha, text="Agrupar", command=self._agrupar).pack(side="left", padx=(6, 0))
        ttk.Button(linha, text="Desagrupar", command=self._desagrupar
                   ).pack(side="left", padx=(6, 0))
        self.var_contagem = tk.StringVar()
        ttk.Label(linha, textvariable=self.var_contagem, foreground="#666"
                  ).pack(side="right")

        corpo = ttk.Frame(flt)
        corpo.pack(fill="both", expand=True, pady=(6, 0))
        self.lista = tk.Listbox(corpo, selectmode="multiple", exportselection=False, height=8)
        rolagem = ttk.Scrollbar(corpo, orient="vertical", command=self.lista.yview)
        self.lista.configure(yscrollcommand=rolagem.set)
        self.lista.pack(side="left", fill="both", expand=True)
        rolagem.pack(side="right", fill="y")
        self.lista.bind("<<ListboxSelect>>", self._ao_selecionar)
        self._atualizar_contagem()

        self.btn_hist = ttk.Button(f, text="Gerar histórico em Excel",
                                   command=self.gerar_historico)
        self.btn_hist.pack(anchor="e", pady=(10, 0))

    def definir_ocupado(self, ocupado):
        self.btn_hist.configure(state="disabled" if ocupado else "normal")

    # ── Filtro individual ────────────────────────────────────────────────────

    def receber(self, itens):
        """Chamado pela App quando as vendas são (re)carregadas."""
        self.estado.receber(itens)
        self._preencher_lista()

    def _preencher_lista(self, *_):
        tipo = self.var_hist.get()
        termo = self.var_busca.get().strip().lower()
        textos, totais = self.estado.itens_lista(tipo, rotulo)
        # Ordem de participação no arrecadado (maior primeiro), como na tabela.
        cods = sorted(textos, key=lambda c: (-totais.get(c, 0.0), textos[c].lower()))
        self.visiveis = [c for c in cods if termo in textos[c].lower()]
        self.lista.delete(0, tk.END)
        for i, c in enumerate(self.visiveis):
            self.lista.insert(tk.END, textos[c])
            if c in self.estado.selecao[tipo]:
                self.lista.selection_set(i)
        self._atualizar_contagem()

    def _ao_selecionar(self, _evento=None):
        self.estado.atualizar_selecao(self.var_hist.get(), self.visiveis,
                                      self.lista.curselection())
        self._atualizar_contagem()

    def _marcar_todos(self):
        """Marca todos os itens que aparecem na lista (respeitando a busca atual);
        o que já estava marcado fora da busca continua marcado."""
        if not self.visiveis:
            return
        self.estado.marcar_todos(self.var_hist.get(), self.visiveis)
        self.lista.selection_set(0, tk.END)
        self._atualizar_contagem()

    # ── Grupos ───────────────────────────────────────────────────────────────

    def _agrupar(self):
        """Junta os itens marcados (e grupos marcados) num único grupo."""
        tipo = self.var_hist.get()
        if not self.estado.pode_agrupar(tipo):
            messagebox.showinfo("Agrupar", "Marque 2 ou mais itens.", parent=self.app.root)
            return
        padrao, usados = self.estado.nomes_para_novo_grupo(tipo)
        nome = pedir_nome(self.app.root, "Agrupar", "Nome do grupo", padrao, usados,
                          msg_usado="Já existe um grupo com esse nome.",
                          normalizar=lambda t: t.strip().lstrip("=").strip())
        if nome is None:
            return
        self.estado.agrupar(tipo, nome)
        self._preencher_lista()

    def _desagrupar(self):
        """Desfaz os grupos marcados; os itens voltam à lista, marcados."""
        tipo = self.var_hist.get()
        if not self.estado.tem_grupo_marcado(tipo):
            messagebox.showinfo("Desagrupar", "Marque um grupo.", parent=self.app.root)
            return
        self.estado.desagrupar(tipo)
        self._preencher_lista()

    def _limpar_selecao(self):
        self.estado.limpar_selecao(self.var_hist.get())
        self.lista.selection_clear(0, tk.END)
        self._atualizar_contagem()

    def _atualizar_contagem(self):
        n = len(self.estado.selecao[self.var_hist.get()])
        self.var_contagem.set(f"{n} selecionado(s)" if n else "")

    # ── Gerar histórico (xlsx) ───────────────────────────────────────────────

    def gerar_historico(self):
        app = self.app
        if app.ocupado:
            return
        periodo = app.ler_periodo()
        if periodo is None:
            return
        ini, fim, hora_ini, hora_fim = periodo
        multi = ini != fim
        if multi and (dkey(fim) - dkey(ini)).days + 1 > cfg.MAX_DIAS_HISTORICO:
            messagebox.showwarning("Período", f"O histórico aceita no máximo "
                                   f"{cfg.MAX_DIAS_HISTORICO} dias.", parent=app.root)
            return

        if self.var_modo.get() == "faixa":
            try:
                intervalo = int(self.spin_min.get())
            except ValueError:
                intervalo = 0
            if not cfg.INTERVALO_MIN <= intervalo <= cfg.INTERVALO_MAX:
                messagebox.showwarning("Soma", f"Intervalo inválido ({cfg.INTERVALO_MIN} a "
                                       f"{cfg.INTERVALO_MAX} minutos).", parent=app.root)
                return
        else:
            intervalo = None if multi else 60

        tipo = self.var_hist.get()
        grupos, selecionados = self.estado.para_exportar(tipo)

        def tarefa():
            hist = historico_vendas(FONTE_PADRAO, ini, fim, hora_ini, hora_fim, intervalo)
            if not hist[tipo]:
                return None
            hist = aplicar_grupos(hist, tipo, grupos)      # soma de cada grupo, por coluna
            return exportar_historico_xlsx(tipo, hist, selecionados=selecionados)

        def ao_terminar(caminho):
            if caminho is None:
                app.ocupar(False, "Nenhuma venda para os critérios escolhidos.")
                messagebox.showinfo("Histórico", "Nenhuma venda neste período "
                                    "para os itens escolhidos.", parent=app.root)
                return
            app.ocupar(False, f"Planilha salva em: {caminho}")
            try:
                abrir_arquivo(caminho)
            except Exception as e:  # noqa: BLE001
                messagebox.showwarning("Histórico", f"Planilha salva em:\n{caminho}\n\n"
                                       f"Não foi possível abri-la: {e}", parent=app.root)

        app.ocupar(True, "Gerando histórico...")
        app.executor.rodar(tarefa, ao_terminar,
                           lambda e: app.erro("Erro ao gerar o histórico", e))
