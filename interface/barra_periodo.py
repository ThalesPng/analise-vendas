"""
barra_periodo.py — barra de período: datas, faixa de horas (opcional) e o botão
"Carregar vendas". ler() devolve (data_ini, data_fim, hora_ini, hora_fim) já validados.
"""

import tkinter as tk
from tkinter import messagebox, ttk

import config as cfg

from .formato import dkey, hoje, parse_data, parse_hora
from .widgets import HoraEntry, campo_data


class BarraPeriodo(ttk.LabelFrame):
    def __init__(self, pai, app, data_ini=None, data_fim=None):
        super().__init__(pai, text="Período", padding=8)
        self.app = app
        per = self
        ttk.Label(per, text="Data").grid(row=0, column=0, sticky="e", padx=(0, 6), pady=3)
        datas = ttk.Frame(per)
        datas.grid(row=0, column=1, columnspan=3, sticky="w", pady=3)
        self.ent_ini = campo_data(datas)
        self.ent_ini.pack(side="left")
        ttk.Label(datas, text="-").pack(side="left", padx=6)
        self.ent_fim = campo_data(datas)
        self.ent_fim.pack(side="left")
        ttk.Label(per, text="Hora").grid(row=1, column=0, sticky="e", padx=(0, 6), pady=3)
        horas = ttk.Frame(per)
        horas.grid(row=1, column=1, columnspan=3, sticky="w", pady=3)
        self.ent_hi = HoraEntry(horas, width=6)
        self.ent_hi.pack(side="left")
        ttk.Label(horas, text="-").pack(side="left", padx=6)
        self.ent_hf = HoraEntry(horas, width=6)
        self.ent_hf.pack(side="left")
        ini = dkey(data_ini or hoje())
        self.ent_ini.set_date(ini)
        self.ent_fim.set_date(dkey(data_fim) if data_fim else ini)
        # Data final nunca fica antes da inicial: ao mudar a inicial, a final acompanha.
        self.ent_ini.bind("<<DateEntrySelected>>", self._sincronizar_datas)
        self.ent_ini.bind("<FocusOut>", self._sincronizar_datas, add="+")
        self.btn_carregar = ttk.Button(per, text="Carregar vendas (F5)", command=app.carregar)
        self.btn_carregar.grid(row=0, column=4, sticky="w", padx=(16, 0))
        self.var_resumo = tk.StringVar(value="Nenhuma venda carregada.")
        ttk.Label(per, textvariable=self.var_resumo).grid(
            row=0, column=5, sticky="w", padx=(12, 0))
        ttk.Label(per, text="Horas vazias = dia inteiro.",
                  foreground="#666").grid(row=1, column=4, columnspan=2, sticky="w", padx=(16, 0))
        for e in (self.ent_ini, self.ent_fim, self.ent_hi, self.ent_hf):
            e.bind("<Return>", lambda ev: app.carregar())

    def definir_ocupado(self, ocupado):
        self.btn_carregar.configure(state="disabled" if ocupado else "normal")

    def _sincronizar_datas(self, _evento=None):
        try:
            if self.ent_fim.get_date() < self.ent_ini.get_date():
                self.ent_fim.set_date(self.ent_ini.get_date())
        except ValueError:      # texto digitado ainda inválido
            pass

    def ler(self):
        """(data_ini, data_fim, hora_ini, hora_fim) ou None (mensagem já exibida)."""
        def aviso(txt):
            messagebox.showwarning("Período", txt, parent=self.app.root)
            return None

        ini = parse_data(self.ent_ini.get())
        if ini is None:
            return aviso("Data inicial inválida. Use DD/MM/AAAA.")
        txt = self.ent_fim.get().strip()
        fim = parse_data(txt) if txt else ini
        if fim is None:
            return aviso("Data final inválida. Use DD/MM/AAAA.")
        if dkey(fim) < dkey(ini):
            return aviso("A data final é anterior à inicial.")

        hora_ini = hora_fim = None
        hi, hf = self.ent_hi.get().strip(), self.ent_hf.get().strip()
        if hi or hf:
            hora_ini = parse_hora(hi) if hi else cfg.HORA_MIN
            hora_fim = parse_hora(hf) if hf else cfg.HORA_MAX
            if hora_ini is None or hora_fim is None:
                return aviso("Hora inválida. Use HH:MM.")
            if hora_fim < hora_ini:
                return aviso("A hora final é anterior à inicial.")
        return ini, fim, hora_ini, hora_fim
