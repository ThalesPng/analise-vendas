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
        self._dicas = []            # [(coluna, texto)] do desenho atual
        self._dica = None           # anotação que mostra o texto ao passar o mouse
        self._dica_atual = None     # texto visível agora (None = escondida)
        self.canvas.mpl_connect("motion_notify_event", self._ao_mover)
        self.canvas.mpl_connect("figure_leave_event", self._ao_sair)

    def iniciar(self, vazio=None):
        """Limpa o desenho anterior. Com `vazio` (texto), mostra só a mensagem e devolve False:
        o gráfico não tem o que desenhar. Senão, deixa o eixo pronto e devolve True."""
        ax = self.ax
        ax.clear()
        self._dicas = []
        self._dica_atual = None
        self._dica = ax.annotate(
            "", xy=(0, 0), xytext=(10, 10), textcoords="offset points", fontsize=8, zorder=10,
            visible=False, annotation_clip=False,
            bbox={"boxstyle": "round,pad=0.4", "fc": "white", "ec": COR_TEXTO_FRACO})
        self._dica.set_in_layout(False)     # aparecer/sumir não pode mexer no layout do gráfico
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

    def registrar_dicas(self, colunas, textos):
        """Texto que aparece ao passar o mouse sobre cada coluna (`colunas`: os retângulos de
        ax.bar(...).patches, na mesma ordem de `textos`). Chamar depois de desenhar."""
        self._dicas.extend(zip(colunas, textos, strict=True))

    def _ao_mover(self, evento):
        texto = None
        if evento.inaxes is self.ax:
            texto = next((t for coluna, t in self._dicas if coluna.contains(evento)[0]), None)
        if texto is None:
            self._esconder_dica()
            return
        # Perto da borda direita/superior a caixa abre para o outro lado, para não cortar.
        caixa = self.ax.bbox
        direita = (evento.x - caixa.x0) / caixa.width > 0.6
        topo = (evento.y - caixa.y0) / caixa.height > 0.75
        dica = self._dica
        dica.set_text(texto)
        dica.xy = (evento.xdata, evento.ydata)
        dica.xyann = (-10 if direita else 10, -10 if topo else 10)
        dica.set_horizontalalignment("right" if direita else "left")
        dica.set_verticalalignment("top" if topo else "bottom")
        dica.set_visible(True)
        self._dica_atual = texto
        self.canvas.draw_idle()

    def _ao_sair(self, _evento):
        self._esconder_dica()

    def _esconder_dica(self):
        if self._dica_atual is not None:
            self._dica.set_visible(False)
            self._dica_atual = None
            self.canvas.draw_idle()

    def nota_rodape(self, texto):
        self.ax.set_xlabel(texto, fontsize=8, color=COR_TEXTO_FRACO)

    def concluir(self):
        self.canvas.draw_idle()
