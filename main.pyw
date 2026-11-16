"""
main.pyw — relatórios de vendas (participação, histórico em Excel, projeção do dia)
com acesso "tipo banco de dados" às vendas.

Camadas
-------
  FONTE (trocável)  ->  itens  ->  agrupar() / historico_vendas() / projetar_dia()  ->  janela (Tkinter)
  fonte(data_ini, data_fim, hora_ini, hora_fim)

Módulos (todos na mesma pasta; este arquivo é só o ponto de entrada):
  config.py        constantes e pasta de vendas (pasta_vendas(): o padrão é decidido aqui)
  banco.py         ÚNICO acesso a dados (banco SammiNFC + fonte provisória); exporta FONTE_PADRAO
  vendas_nfce.py   coleta PROVISÓRIA: lê os XMLs de NFC-e, grava os !vendas_*.json de cada
                   caixa e os devolve em listar_vendas(); sai quando tudo vier do banco
  relatorios/      regras de cada aba, sem I/O nem Tk: utils.py (helpers compartilhados),
                   participacao.py, historico.py (histórico por dia/faixa, grupos e estado
                   da seleção) e projecao.py (fechamento estimado e perfil por hora)
  excel.py         exportação do histórico em .xlsx com gráfico (faz I/O; fica separado)
  interface/       pacote da interface gráfica (Tkinter), um módulo por parte: barra de
                   período, aba Participação, aba Histórico em Excel e aba Projeção do dia

A FONTE é o equivalente a uma consulta ao banco: devolve as linhas de venda
(itens) do período — e da faixa de horas, se houver — de TODOS os caixas. As
funções de relatório só recebem itens e agrupam como precisarem (por produto,
por departamento...). Nada é pré-calculado nem gravado em disco: não existem
mais os !resumo_DD-MM-AAAA.json.

O contrato do item normalizado e o acesso ao banco estão documentados em banco.py.

Histórico (aba "Histórico (Excel)"): grava um .xlsx em <pasta de vendas>/Historico/
com a tabela e um gráfico de linhas (valor vendido por dia, uma linha por item,
na aba "Gráfico"), e abre o arquivo no Excel.

Projeção (aba "Projeção do dia"): fechamento estimado do dia (vendido até uma hora +
perfil dos mesmos dias da semana) e curva média de vendas por hora.

Imports: os módulos são importados pelo nome (`import config`, `from banco import ...`),
então a pasta deste arquivo precisa estar no sys.path. É aqui, no ponto de entrada, que
isso é garantido — os demais módulos não mexem no sys.path.

Dependências (instaladas uma vez por máquina, nada é instalado ao abrir o programa):
    pip install -r requirements.txt

Extensão .pyw: no Windows abre com pythonw, sem janela de console (dois cliques
ou atalho). Erros de partida aparecem numa caixa de mensagem.

Uso:
    main.pyw                          # hoje
    main.pyw 09-11-2026               # um dia
    main.pyw 01-11-2026 09-11-2026    # intervalo
"""

import os
import sys

_PASTA = os.path.dirname(os.path.abspath(__file__))
if _PASTA not in sys.path:
    sys.path.insert(0, _PASTA)

if __name__ == "__main__":
    from interface import main
    main()
