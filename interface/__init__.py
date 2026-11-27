"""
interface — interface gráfica (Tkinter) do relatório de vendas.

Ligação das camadas:
    FONTE_PADRAO (banco) -> itens -> relatorios -> telas / excel

Módulos
-------
  app.py              janela principal (barra de período + abas + status) e main()
  barra_periodo.py    datas e faixa de horas (opcional) + "Carregar vendas".
  participacao.py     tabela de produtos/departamentos com valor e % (clique no
                      cabeçalho para ordenar).
  historico.py        sem tela de resultado: gera a planilha .xlsx com o gráfico.
                      Aqui só se escolhe o que entra (tipo, soma por dia ou faixa,
                      itens do gráfico, grupos — o estado deles fica em relatorios/historico.py).
  projecao.py         fechamento estimado do dia + curva média de vendas por hora.
                      Tem datas/horas próprias: não usa a barra de período.
  desvios.py          dias do período fora do padrão e, para o dia escolhido, o resumo
                      da análise + horário, departamentos/produtos e maiores vendas.
                      Usa as datas da barra de período (ignora as horas).
  texto_desvios.py    sem Tkinter: linha de cada dia na lista e resumo em frases.
  graficos/           gráficos (matplotlib dentro do Tkinter), um módulo por gráfico:
                      comum.py (classe-mãe, cores, formatadores) e desvios.py (colunas
                      real x esperado por dia, da aba Desvios do dia, com cor por desvio).
  widgets.py          HoraEntry, campo_data, pedir_nome (pop-up), Executor (thread).
  formato.py          helpers puros de formatação e leitura de datas/horas.

A coleta e a geração do xlsx rodam numa thread, então a janela não trava.
Cálculos e estado dos grupos em relatorios/ (utils, participação, histórico, projeção
do dia, desvios do dia); a exportação do histórico, em excel.py; a coleta, em banco.py.
"""

from .app import main

__all__ = ["main"]
