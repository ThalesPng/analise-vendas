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
  widgets.py          HoraEntry, campo_data, pedir_nome (pop-up), Executor (thread).
  formato.py          helpers puros de formatação e leitura de datas/horas.

A coleta e a geração do xlsx rodam numa thread, então a janela não trava.
Cálculos e estado dos grupos em relatorios/ (utils, participação, histórico, projeção
do dia); a exportação do histórico, em excel.py; a coleta, em banco.py.
"""

from .app import main

__all__ = ["main"]
