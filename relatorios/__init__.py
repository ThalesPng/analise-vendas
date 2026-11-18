"""
relatorios — regras de cada relatório/aba (sem I/O: nada de banco, tela ou arquivo).
Recebem itens normalizados (ver banco) ou a FONTE por parâmetro e devolvem estruturas
de dados, então podem ser testadas com dados falsos.

  utils.py         helpers usados por mais de uma aba (agrupar, datas, horas, faixas)
  participacao.py  aba Participação: percentual de cada item no total
  historico.py     aba Histórico: histórico por dia/faixa, aplicação de grupos e o
                   estado da seleção e dos grupos (classe Grupos)
  projecao.py      aba Projeção do dia: fechamento estimado e perfil por hora
  vendas.py        id_venda do item (a projeção conta vendas com ele)

A exportação do histórico para .xlsx (excel.py) fica na raiz, fora daqui: faz I/O e
tem escopo próprio, que tende a crescer.

Os módulos não são reexportados aqui de propósito: `participacao` é ao mesmo tempo
nome de módulo e de função. Importe do módulo: `from relatorios.participacao import participacao`.
"""
