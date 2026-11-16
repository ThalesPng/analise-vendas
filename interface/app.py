"""
app.py — janela principal (Tkinter) do relatório de vendas e ponto de partida (main).

A App só monta a janela: barra de período, abas e barra de status. Cada aba é uma
classe própria (participacao.py, historico.py, projecao.py) e usa da App apenas:
root, executor, ocupado, ocupar(), erro() e ler_periodo(). O botão "Carregar vendas" (F5) lê as vendas uma vez e entrega
os itens às abas Participação e Histórico via receber(itens).
"""

import importlib.util
import sys
import tkinter as tk
from datetime import datetime
from tkinter import font as tkfont
from tkinter import messagebox, ttk

from banco import FONTE_PADRAO

from .barra_periodo import BarraPeriodo
from .formato import brl, dkey, parse_data
from .historico import AbaHistorico
from .participacao import AbaParticipacao
from .projecao import AbaProjecao
from .widgets import Executor


class App:
    def __init__(self, root, data_ini=None, data_fim=None):
        self.root = root
        root.title("Relatório de Vendas")
        root.minsize(860, 600)
        tkfont.nametofont("TkDefaultFont").configure(size=10)
        estilo = ttk.Style()
        for tema in ("vista", "clam"):
            if tema in estilo.theme_names():
                estilo.theme_use(tema)
                break

        self.executor = Executor(root)
        self.ocupado = False

        self._montar(data_ini, data_fim)
        root.bind("<F5>", lambda e: self.carregar())
        root.bind("<F6>", lambda e: self.projecao.projetar())

    # ── Montagem da janela ───────────────────────────────────────────────────

    def _montar(self, data_ini, data_fim):
        raiz = ttk.Frame(self.root, padding=10)
        raiz.pack(fill="both", expand=True)

        self.barra = BarraPeriodo(raiz, self, data_ini, data_fim)
        self.barra.pack(fill="x")

        # Abas
        self.abas = ttk.Notebook(raiz)
        self.abas.pack(fill="both", expand=True, pady=(10, 0))
        self.participacao = AbaParticipacao(self.abas, self)
        self.historico = AbaHistorico(self.abas, self)
        self.projecao = AbaProjecao(self.abas, self)
        self.abas.add(self.participacao, text="  Participação  ")
        self.abas.add(self.historico, text="  Histórico (Excel)  ")
        self.abas.add(self.projecao, text="  Projeção do dia  ")

        # Barra de status
        barra = ttk.Frame(raiz)
        barra.pack(fill="x", pady=(8, 0))
        self.var_status = tk.StringVar(value="Pronto.")
        ttk.Label(barra, textvariable=self.var_status).pack(side="left")

    # ── Estado ocupado / mensagens (usados pelas abas) ───────────────────────

    def ocupar(self, ocupado, mensagem=None):
        self.ocupado = ocupado
        for parte in (self.barra, self.historico, self.projecao):
            parte.definir_ocupado(ocupado)
        if mensagem is not None:
            self.var_status.set(mensagem)

    def erro(self, titulo, e):
        self.ocupar(False, "Erro.")
        messagebox.showerror(titulo, str(e), parent=self.root)

    def ler_periodo(self):
        """(data_ini, data_fim, hora_ini, hora_fim) ou None (mensagem já exibida)."""
        return self.barra.ler()

    # ── Carregar vendas (Participação e lista de filtro do Histórico) ────────

    def carregar(self):
        if self.ocupado:
            return
        periodo = self.ler_periodo()
        if periodo is None:
            return
        self.ocupar(True, "Carregando vendas...")

        def ao_terminar(itens):
            self.participacao.receber(itens)
            self.historico.receber(itens)
            if itens:
                total = sum(i["valor_total"] for i in itens)
                self.barra.var_resumo.set(f"Total vendido: {brl(total)}  "
                                          f"(lido às {datetime.now():%H:%M:%S})")
            else:
                self.barra.var_resumo.set("Nenhuma venda encontrada neste período.")
            self.ocupar(False, "Vendas carregadas.")

        self.executor.rodar(lambda: FONTE_PADRAO(*periodo), ao_terminar,
                            lambda e: self.erro("Erro ao coletar as vendas", e))


# Módulos de terceiros que o programa usa (os mesmos do requirements.txt).
DEPENDENCIAS = ("tkcalendar", "openpyxl", "pyodbc")


def _erro_fatal(msg):
    """Sem console (main.pyw) um erro na partida seria invisível: mostra numa janela."""
    r = tk.Tk()
    r.withdraw()
    messagebox.showerror("Relatório de Vendas", msg, parent=r)
    r.destroy()


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    faltam = [m for m in DEPENDENCIAS if importlib.util.find_spec(m) is None]
    if faltam:
        _erro_fatal(f"Faltam pacotes do Python: {', '.join(faltam)}.\n\n"
                    "Instale uma vez nesta máquina com:\npip install -r requirements.txt")
        return
    ini = fim = None
    if argv:
        ini = parse_data(argv[0])
        fim = parse_data(argv[1]) if len(argv) > 1 else ini
        if ini is None or fim is None or dkey(fim) < dkey(ini):
            _erro_fatal("Datas inválidas. Use DD-MM-AAAA [DD-MM-AAAA].")
            return
    try:                                   # nitidez em telas com escala (Windows)
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass
    root = tk.Tk()
    try:
        App(root, ini, fim)
    except Exception as e:  # noqa: BLE001 — ex.: falha ao instalar tkcalendar
        root.destroy()
        _erro_fatal(f"Não foi possível iniciar o programa:\n{e}")
        return
    root.mainloop()
