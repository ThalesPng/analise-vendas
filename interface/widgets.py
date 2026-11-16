"""
widgets.py — peças reutilizáveis da interface: campo de hora, campo de data com
calendário, pop-up para pedir um nome e o executor que roda tarefas numa thread.
"""

import queue
import threading
import tkinter as tk
from tkinter import ttk


def campo_data(pai):
    """Campo de data com calendário (tkcalendar), formato DD/MM/AAAA."""
    from tkcalendar import DateEntry
    return DateEntry(pai, width=11, locale="pt_BR", date_pattern="dd/mm/yyyy",
                     firstweekday="sunday", showweeknumbers=False)


class HoraEntry(ttk.Entry):
    """Campo de hora HH:MM: só aceita dígitos e põe o ':' sozinho (digite 1430 -> 14:30).
    Apagar com Backspace também leva o ':' junto."""

    def __init__(self, pai, **kw):
        self._var = tk.StringVar()
        super().__init__(pai, textvariable=self._var, **kw)
        self._anterior = ""
        self._var.trace_add("write", self._formatar)

    def _formatar(self, *_):
        texto = self._var.get()
        digitos = "".join(c for c in texto if c.isdigit())[:4]
        novo = digitos
        if len(digitos) > 2 or (len(digitos) == 2 and len(texto) >= len(self._anterior)):
            novo = digitos[:2] + ":" + digitos[2:]      # ":" logo após o 2º dígito digitado
        self._anterior = novo
        if novo != texto:
            self._var.set(novo)
            self.icursor(tk.END)


def pedir_nome(raiz, titulo, rotulo, padrao, usados=(), msg_usado="Esse nome já existe.",
               normalizar=str.strip):
    """Pop-up modal que pede um nome (centralizado sobre `raiz`). Vazio = `padrao`.
    `usados`: nomes em minúsculas que não podem repetir (mostra `msg_usado` e não
    fecha). `normalizar(texto)` limpa o que foi digitado antes de usar.
    Retorna o nome, ou None se cancelado."""
    janela = tk.Toplevel(raiz)
    janela.title(titulo)
    janela.transient(raiz)
    janela.resizable(False, False)
    corpo = ttk.Frame(janela, padding=12)
    corpo.pack()
    ttk.Label(corpo, text=rotulo).pack(anchor="w")
    var = tk.StringVar()
    entrada = ttk.Entry(corpo, textvariable=var, width=30)
    entrada.pack(fill="x", pady=(4, 0))
    var_dica = tk.StringVar(value=f"Vazio = {padrao}")
    dica = ttk.Label(corpo, textvariable=var_dica, foreground="#666")
    dica.pack(anchor="w", pady=(2, 8))
    resultado = {"nome": None}

    def confirmar(_e=None):
        nome = normalizar(var.get()) or padrao
        if nome.lower() in usados:
            var_dica.set(msg_usado)
            dica.configure(foreground="#b00020")
            return
        resultado["nome"] = nome
        janela.destroy()

    botoes = ttk.Frame(corpo)
    botoes.pack(anchor="e")
    ttk.Button(botoes, text="OK", command=confirmar).pack(side="left")
    ttk.Button(botoes, text="Cancelar", command=janela.destroy).pack(side="left", padx=(6, 0))
    janela.bind("<Return>", confirmar)
    janela.bind("<Escape>", lambda _e: janela.destroy())

    janela.update_idletasks()                  # centraliza sobre a janela principal
    x = raiz.winfo_rootx() + (raiz.winfo_width() - janela.winfo_width()) // 2
    y = raiz.winfo_rooty() + (raiz.winfo_height() - janela.winfo_height()) // 3
    janela.geometry(f"+{max(x, 0)}+{max(y, 0)}")
    entrada.focus_set()
    janela.wait_visibility()                   # grab_set exige janela visível (Linux/Mac)
    janela.grab_set()
    janela.wait_window()
    return resultado["nome"]


class Executor:
    """Roda uma função numa thread e devolve o resultado na thread da interface."""

    def __init__(self, root):
        self.root = root
        self.fila = queue.Queue()
        root.after(100, self._poll)

    def rodar(self, func, ao_terminar, ao_falhar):
        def alvo():
            try:
                self.fila.put((ao_terminar, func()))
            except Exception as e:  # noqa: BLE001 — qualquer erro vira mensagem
                self.fila.put((ao_falhar, e))
        threading.Thread(target=alvo, daemon=True).start()

    def _poll(self):
        try:
            while True:
                callback, valor = self.fila.get_nowait()
                callback(valor)
        except queue.Empty:
            pass
        self.root.after(100, self._poll)
