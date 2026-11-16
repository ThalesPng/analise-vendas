"""
participacao.py — aba "Participação": tabela de produtos/departamentos com valor
e % do total (clique no cabeçalho para ordenar). Recebe os itens carregados em receber().
"""

import tkinter as tk
from tkinter import ttk

from relatorios.participacao import participacao
from relatorios.utils import agrupar

from .formato import brl, pct, qtde, rotulo


class AbaParticipacao(ttk.Frame):
    def __init__(self, pai, app):
        super().__init__(pai, padding=10)
        self.app = app
        self.itens = []
        self.linhas_part = []               # linhas da tabela de participação
        self.ordem_part = ("valor", True)   # (coluna, decrescente?)
        self._montar()

    def _montar(self):
        f = self

        topo = ttk.Frame(f)
        topo.pack(fill="x")
        self.var_part = tk.StringVar(value="produto")
        ttk.Radiobutton(topo, text="Produtos", value="produto", variable=self.var_part,
                        command=self._atualizar).pack(side="left")
        ttk.Radiobutton(topo, text="Departamentos", value="departamento",
                        variable=self.var_part,
                        command=self._atualizar).pack(side="left", padx=12)

        corpo = ttk.Frame(f)
        corpo.pack(fill="both", expand=True, pady=(8, 0))
        colunas = ("item", "valor", "pct", "qtde")
        self.tree = ttk.Treeview(corpo, columns=colunas, show="headings", selectmode="browse")
        cabecalhos = {"item": "Item", "valor": "Valor", "pct": "%", "qtde": "Qtde"}
        larguras = {"item": 380, "valor": 120, "pct": 80, "qtde": 100}
        for c in colunas:
            self.tree.heading(c, text=cabecalhos[c], command=lambda c=c: self._ordenar(c))
            self.tree.column(c, width=larguras[c], anchor="w" if c == "item" else "e")
        rolagem = ttk.Scrollbar(corpo, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=rolagem.set)
        self.tree.pack(side="left", fill="both", expand=True)
        rolagem.pack(side="right", fill="y")

        self.var_total_part = tk.StringVar()
        ttk.Label(f, textvariable=self.var_total_part, font=("TkDefaultFont", 10, "bold")
                  ).pack(anchor="e", pady=(6, 0))

    def receber(self, itens):
        """Chamado pela App quando as vendas são (re)carregadas."""
        self.itens = itens
        self._atualizar()

    def _atualizar(self):
        tipo = self.var_part.get()
        grupos = agrupar(self.itens, tipo)
        total, linhas = participacao(grupos)
        self.linhas_part = [(cod, grupos[cod]["nome"], valor, p, grupos[cod]["qtde"])
                            for cod, valor, p in linhas]
        self.tree.configure(displaycolumns=("item", "valor", "pct", "qtde")
                            if tipo == "produto" else ("item", "valor", "pct"))
        self.var_total_part.set(f"TOTAL: {brl(total)}" if self.itens else "")
        self._renderizar()

    def _ordenar(self, coluna):
        atual, desc = self.ordem_part
        self.ordem_part = (coluna, not desc if coluna == atual else coluna != "item")
        self._renderizar()

    def _renderizar(self):
        chaves = {
            "item": lambda r: rotulo(r[0], {r[0]: r[1]}).lower(),
            "valor": lambda r: r[2],
            "pct": lambda r: r[3],
            "qtde": lambda r: r[4] if r[4] is not None else -1,
        }
        coluna, desc = self.ordem_part
        self.tree.delete(*self.tree.get_children())
        for cod, nome, valor, p, q in sorted(self.linhas_part, key=chaves[coluna],
                                             reverse=desc):
            self.tree.insert("", "end", values=(
                rotulo(cod, {cod: nome}), brl(valor), pct(p),
                "" if q is None else qtde(q)))
