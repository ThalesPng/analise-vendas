"""
interface/graficos — gráficos (matplotlib dentro do Tkinter) das abas.

  comum.py     o que todos os gráficos compartilham: a classe-mãe Grafico (Figure + canvas,
               estado vazio, estilo dos eixos, legenda), cores, formatadores de eixo e
               pre_carregar().
  desvios.py   GraficoDias — colunas real x esperado por dia, da aba "Desvios do dia".

Um módulo por gráfico novo. Só desenho: os números vêm prontos de relatorios/.

Este __init__ não importa nada de propósito: o matplotlib é opcional, e cada aba importa o
módulo do seu gráfico só ao abri-lo (ImportError = biblioteca não instalada), para o resto do
programa funcionar mesmo sem ela.
"""
