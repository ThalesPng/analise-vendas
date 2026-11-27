"""
desvios.py — gráfico de colunas da aba "Desvios do dia": cada dia do período tem 2 colunas
lado a lado, o valor real (faturamento ou vendas) e o esperado pela base. A coluna real
muda de cor nos dias fora do padrão (acima, abaixo ou venda pontual) e a legenda mostra só
os tipos que aparecem no período.

Só desenho: os números vêm prontos de relatorios.desvios.serie_diaria.
"""

from matplotlib.patches import Patch

import config as cfg

from .comum import COR_ESPERADO, COR_REAL, Grafico, eixo_milhar, eixo_reais

# Dias fora do padrão: cor da coluna real e texto na legenda (só aparece o que existe no período).
_ESTADOS = {"alto": ("#3f9b4b", "Desvio acima"),
            "baixo": ("#d9622b", "Desvio abaixo"),
            "pontual": ("#e0a800", "Venda pontual")}
_LARGURA = 0.38                 # largura de cada coluna (o dia ocupa 1.0)
_DIAS_ROTULO_EM_DUAS_LINHAS = 14   # acima disso o rótulo vai inclinado, numa linha só


class GraficoDias(Grafico):
    def mostrar(self, serie, indicador, vazio="Nenhum dia para mostrar."):
        """`serie`: lista de {"data", "dia_semana", "real", "esperado" (None sem base),
        "estado" ("alto", "baixo", "pontual" ou None)} em ordem de data. `indicador`:
        "faturamento" ou "vendas"."""
        if not self.iniciar(None if serie else vazio):
            return
        ax = self.ax
        nome = "Faturamento" if indicador == "faturamento" else "Vendas"
        xs = list(range(len(serie)))
        ax.bar([x - _LARGURA / 2 for x in xs], [d["real"] for d in serie], _LARGURA,
               color=[_ESTADOS[d["estado"]][0] if d.get("estado") else COR_REAL for d in serie])
        com_esp = [(x, d["esperado"]) for x, d in zip(xs, serie) if d["esperado"] is not None]
        ax.bar([x + _LARGURA / 2 for x, _ in com_esp], [e for _, e in com_esp], _LARGURA,
               color=COR_ESPERADO)

        duas_linhas = len(serie) <= _DIAS_ROTULO_EM_DUAS_LINHAS
        sep = "\n" if duas_linhas else " "
        ax.set_xticks(xs)
        ax.set_xticklabels([f"{d['data'][:5].replace('-', '/')}{sep}"
                            f"{cfg.DIAS_SEMANA[d['dia_semana']]}" for d in serie],
                           rotation=0 if duas_linhas else 90, fontsize=8)
        ax.set_xlim(-0.6, len(serie) - 0.4)
        ax.yaxis.set_major_formatter(eixo_reais() if indicador == "faturamento"
                                     else eixo_milhar())
        self.estilo_eixos()

        # Legenda dinâmica: o indicador, o esperado e só os tipos de desvio presentes nos dias.
        itens = [Patch(color=COR_REAL, label=nome), Patch(color=COR_ESPERADO, label="Esperado")]
        presentes = {d.get("estado") for d in serie}
        itens += [Patch(color=cor, label=texto) for est, (cor, texto) in _ESTADOS.items()
                  if est in presentes]
        self.legenda(itens)
        if len(com_esp) < len(serie):
            self.nota_rodape("Dias sem coluna de esperado: base de comparação insuficiente.")
        self.concluir()
