"""
projecao.py — aba "Projeção do dia": fechamento estimado do dia (vendido até uma
hora + perfil dos mesmos dias da semana) e curva média de vendas por hora.
Tem datas/horas próprias: não usa a barra de período. Cálculos em relatorios/projecao.py.
"""

import tkinter as tk
from datetime import datetime
from tkinter import messagebox, ttk

import config as cfg
from banco import FONTE_PADRAO
from relatorios.projecao import perfil_horario, projetar_dia
from relatorios.utils import min_hora

from .formato import brl, dkey, nome_dia, parse_data, parse_hora, pct, qtde
from .widgets import HoraEntry, campo_data


class AbaProjecao(ttk.Frame):
    def __init__(self, pai, app):
        super().__init__(pai, padding=10)
        self.app = app
        self.cache_proj = {}        # vendas de dias passados (não mudam) para a projeção
        self.proj = None            # último resultado de projetar_dia
        self.perfil = None          # último resultado de perfil_horario
        self.proj_dia = None        # dia da semana (0-6) da data projetada
        self.proj_hora = None       # hora usada na última projeção
        self._montar()

    def _montar(self):
        f = self

        topo = ttk.Frame(f)
        topo.pack(fill="x")
        ttk.Label(topo, text="Dia").pack(side="left")
        self.ent_proj_data = campo_data(topo)
        self.ent_proj_data.pack(side="left", padx=(6, 14))
        ttk.Label(topo, text="Vendido até as").pack(side="left")
        self.ent_proj_hora = HoraEntry(topo, width=6)
        self.ent_proj_hora.pack(side="left", padx=(6, 14))
        self.ent_proj_hora._var.set(datetime.now().strftime("%H:%M"))
        ttk.Label(topo, text="Base: últimas").pack(side="left")
        self.spin_semanas = ttk.Spinbox(topo, from_=cfg.SEMANAS_MIN, to=cfg.SEMANAS_MAX, width=4)
        self.spin_semanas.set(8)
        self.spin_semanas.pack(side="left", padx=4)
        ttk.Label(topo, text="semanas   Faixa").pack(side="left")
        self.spin_passo = ttk.Spinbox(topo, from_=cfg.PASSO_MIN, to=cfg.PASSO_MAX, increment=5, width=4)
        self.spin_passo.set(60)
        self.spin_passo.pack(side="left", padx=4)
        ttk.Label(topo, text="min").pack(side="left")
        self.btn_proj = ttk.Button(topo, text="Projetar (F6)", command=self.projetar)
        self.btn_proj.pack(side="right")

        self.var_proj_resumo = tk.StringVar()
        ttk.Label(f, textvariable=self.var_proj_resumo, font=("TkDefaultFont", 14, "bold")
                  ).pack(anchor="w", pady=(12, 2))
        self.var_proj_detalhe = tk.StringVar()
        ttk.Label(f, textvariable=self.var_proj_detalhe, justify="left", wraplength=820
                  ).pack(anchor="w")
        self.var_proj_aviso = tk.StringVar()
        ttk.Label(f, textvariable=self.var_proj_aviso, foreground="#b45f06",
                  justify="left", wraplength=820).pack(anchor="w", pady=(4, 0))

        sel = ttk.Frame(f)
        sel.pack(fill="x", pady=(12, 0))
        ttk.Label(sel, text="Perfil por hora de").pack(side="left")
        self.cmb_perfil = ttk.Combobox(sel, state="readonly", width=8,
                                       values=[nome_dia(n) for n in range(7)])
        self.cmb_perfil.pack(side="left", padx=6)
        self.cmb_perfil.bind("<<ComboboxSelected>>", lambda e: self._mostrar_perfil())
        self.var_perfil_info = tk.StringVar()
        ttk.Label(sel, textvariable=self.var_perfil_info, foreground="#666"
                  ).pack(side="left", padx=10)

        corpo = ttk.Frame(f)
        corpo.pack(fill="both", expand=True, pady=(6, 0))
        colunas = ("faixa", "media", "vendas", "pct", "hoje", "obs")
        self.tree_perfil = ttk.Treeview(corpo, columns=colunas, show="headings",
                                        selectmode="browse", height=8)
        cab = {"faixa": "Faixa", "media": "Média vendida", "vendas": "Vendas (média)",
               "pct": "% do dia", "hoje": "Hoje", "obs": ""}
        larg = {"faixa": 130, "media": 130, "vendas": 110, "pct": 90, "hoje": 120, "obs": 90}
        for c in colunas:
            self.tree_perfil.heading(c, text=cab[c])
            self.tree_perfil.column(c, width=larg[c], anchor="w" if c in ("faixa", "obs") else "e")
        self.tree_perfil.tag_configure("pico", background="#fff2cc")
        rolagem = ttk.Scrollbar(corpo, orient="vertical", command=self.tree_perfil.yview)
        self.tree_perfil.configure(yscrollcommand=rolagem.set)
        self.tree_perfil.pack(side="left", fill="both", expand=True)
        rolagem.pack(side="right", fill="y")

    def definir_ocupado(self, ocupado):
        self.btn_proj.configure(state="disabled" if ocupado else "normal")

    def projetar(self):
        app = self.app
        if app.ocupado:
            return
        data = parse_data(self.ent_proj_data.get())
        if data is None:
            messagebox.showwarning("Projeção", "Data inválida. Use DD/MM/AAAA.", parent=app.root)
            return
        hora = parse_hora(self.ent_proj_hora.get()) if self.ent_proj_hora.get().strip() else None
        if hora is None:
            messagebox.showwarning("Projeção", "Hora inválida. Use HH:MM.", parent=app.root)
            return
        try:
            semanas = int(self.spin_semanas.get())
            passo = int(self.spin_passo.get())
        except ValueError:
            semanas = passo = 0
        if not (cfg.SEMANAS_MIN <= semanas <= cfg.SEMANAS_MAX
                and cfg.PASSO_MIN <= passo <= cfg.PASSO_MAX):
            messagebox.showwarning("Projeção", f"Use de {cfg.SEMANAS_MIN} a {cfg.SEMANAS_MAX} "
                                   f"semanas e faixas de {cfg.PASSO_MIN} a {cfg.PASSO_MAX} "
                                   "minutos.", parent=app.root)
            return

        def tarefa():
            proj = projetar_dia(FONTE_PADRAO, data, hora, semanas, self.cache_proj, passo)
            perfil = perfil_horario(FONTE_PADRAO, data, semanas, passo, self.cache_proj)
            return proj, perfil

        def ao_terminar(res):
            self.proj, self.perfil = res
            self.proj_dia = dkey(data).weekday()
            self.proj_hora = hora
            self._mostrar_projecao(data, hora)
            self.cmb_perfil.set(nome_dia(self.proj_dia))
            self._mostrar_perfil()
            app.ocupar(False, "Projeção calculada.")

        app.ocupar(True, "Calculando projeção (lendo as últimas semanas)...")
        app.executor.rodar(tarefa, ao_terminar, lambda e: app.erro("Erro na projeção", e))

    def _mostrar_projecao(self, data, hora):
        r = self.proj
        dia = nome_dia(dkey(data).weekday())
        self.var_proj_aviso.set("\n".join(r["avisos"]))
        if r["estimativa"] is None:
            self.var_proj_resumo.set("Sem projeção para este dia/horário.")
            self.var_proj_detalhe.set(f"Vendido até {hora}: {brl(r['vendido'])}.")
            return
        base = (f"Base: {r['dias']} {dia}(s) comparável(is), média do dia "
                f"{brl(r['media_total_historico'])}.")
        if r["descartados"]:
            base += (f" {len(r['descartados'])} dia(s) ficaram fora (sem vendas ou muito "
                     "abaixo do normal).")
        if r["vendido"] <= 0:
            self.var_proj_resumo.set("Ainda sem vendas até essa hora.")
            self.var_proj_detalhe.set(base)
            return
        self.var_proj_resumo.set(f"Fechamento estimado: {brl(r['estimativa'])}")
        self.var_proj_detalhe.set(
            f"Vendido até {hora}: {brl(r['vendido'])} — costuma ser "
            f"{r['fracao'] * 100:.0f}% do dia.\n"
            f"Faixa provável: {brl(r['baixa'])} a {brl(r['alta'])}.  "
            f"Outro método (vendido + restante médio): {brl(r['aditivo'])}.\n{base}")

    def _mostrar_perfil(self):
        self.tree_perfil.delete(*self.tree_perfil.get_children())
        self.var_perfil_info.set("")
        if not self.perfil:
            return
        dia = list(self.cmb_perfil["values"]).index(self.cmb_perfil.get())
        p = self.perfil[dia]
        if not p["faixas"]:
            self.var_perfil_info.set("Sem vendas nesse dia da semana no período da base.")
            return
        self.var_perfil_info.set(
            f"{p['dias']} dia(s) na média · média do dia {brl(p['media_total'])} · "
            f"pico às {p['pico']}")
        eh_dia_projetado = dia == self.proj_dia and self.proj is not None
        self.tree_perfil.heading("hoje", text=f"Hoje (até {self.proj_hora})"
                                 if eh_dia_projetado else "Hoje")
        for fx in p["faixas"]:
            hoje = ""
            if eh_dia_projetado:
                m = min_hora(fx["inicio"])
                if m <= min_hora(self.proj_hora):
                    hoje = brl(self.proj["por_faixa"].get(m, 0.0))
            pico = fx["inicio"] == p["pico"]
            self.tree_perfil.insert(
                "", "end", tags=("pico",) if pico else (),
                values=(f"{fx['inicio']} – {fx['fim']}", brl(fx["media"]),
                        qtde(fx["vendas"]), pct(fx["pct"]), hoje, "★ pico" if pico else ""))
