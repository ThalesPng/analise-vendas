"""
comum.py — o que todos os gráficos compartilham: classe-mãe, cores, formatadores de eixo e o
aquecimento do matplotlib.

Importar este módulo já carrega o matplotlib (pip install matplotlib), então as abas só o
importam (direto ou pelo módulo de um gráfico) ao abrir o gráfico. A aba chama pre_carregar()
numa thread logo depois de abrir, para o 1º gráfico não travar a tela.
"""

from tkinter import ttk

from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
from matplotlib.ticker import FuncFormatter

COR_REAL = "#2f6fb0"
COR_ESPERADO = "#b8bcc2"
COR_TEXTO_FRACO = "#666666"
COR_GRADE = "#e3e3e3"

TAMANHO = (6, 3.2)      # polegadas; o canvas se ajusta à janela


def milhar(v, _pos=None):
    return f"{v:,.0f}".replace(",", ".")


def reais(v, _pos=None):
    return "R$ " + milhar(v)


def eixo_milhar():
    """Formatador de eixo para números inteiros com ponto de milhar."""
    return FuncFormatter(milhar)


def eixo_reais():
    """Formatador de eixo para valores em R$."""
    return FuncFormatter(reais)


def pre_carregar():
    """Aquece o matplotlib fora da tela: a importação deste módulo já carrega a biblioteca e
    este desenho de teste carrega as fontes (o que faz o 1º gráfico demorar). Não mexe no
    Tk, então pode rodar numa thread."""
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    fig = Figure(figsize=TAMANHO, dpi=100, layout="constrained")
    ax = fig.add_subplot(111)
    ax.bar([0, 1], [1, 2], label="Esperado")
    ax.set_xticks([0, 1])
    ax.set_xticklabels(["09/11\nseg", "10/11\nter"], fontsize=8)
    ax.yaxis.set_major_formatter(eixo_reais())
    ax.legend(loc="lower left", bbox_to_anchor=(0, 1.0), ncol=2, frameon=False)
    FigureCanvasAgg(fig).draw()


class Grafico(ttk.Frame):
    """Classe-mãe dos gráficos: um Frame com a Figure e o canvas. Cada gráfico herda dela e
    escreve o seu mostrar(...); aqui ficam as partes iguais para todos."""

    def __init__(self, pai):
        super().__init__(pai)
        self.fig = Figure(figsize=TAMANHO, dpi=100, layout="constrained")
        self.ax = self.fig.add_subplot(111)
        self.canvas = FigureCanvasTkAgg(self.fig, master=self)
        self.canvas.get_tk_widget().pack(fill="both", expand=True)

    def iniciar(self, vazio=None):
        """Limpa o desenho anterior. Com `vazio` (texto), mostra só a mensagem e devolve False:
        o gráfico não tem o que desenhar. Senão, deixa o eixo pronto e devolve True."""
        ax = self.ax
        ax.clear()
        if vazio is not None:
            ax.set_axis_off()
            ax.text(0.5, 0.5, vazio, ha="center", va="center", transform=ax.transAxes,
                    color=COR_TEXTO_FRACO)
            self.canvas.draw_idle()
            return False
        ax.set_axis_on()
        return True

    def estilo_eixos(self):
        """Estilo comum: grade só na horizontal, atrás das colunas, sem bordas em cima/direita."""
        ax = self.ax
        ax.grid(axis="y", color=COR_GRADE)
        ax.set_axisbelow(True)
        for lado in ("top", "right"):
            ax.spines[lado].set_visible(False)

    def legenda(self, itens):
        """Legenda numa linha só, fora da área das colunas. `itens`: lista de Patch/handles."""
        self.ax.legend(handles=itens, loc="lower left", bbox_to_anchor=(0, 1.0),
                       ncol=len(itens), frameon=False, fontsize=8, columnspacing=1.2,
                       handlelength=1.2)

    def nota_rodape(self, texto):
        self.ax.set_xlabel(texto, fontsize=8, color=COR_TEXTO_FRACO)

    def concluir(self):
        self.canvas.draw_idle()
