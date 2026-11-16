"""
excel.py — exportação do histórico para .xlsx (mesma tabela da tela + gráfico de
linhas, uma linha por item, na aba "Gráfico") e abertura do arquivo no Excel.
"""

import os
import subprocess
import sys
from datetime import datetime
from types import SimpleNamespace

import config as cfg


# ── Exportação do histórico para Excel (.xlsx com gráfico) ───────────────────

MAX_SERIES_GRAFICO = 10   # itens do gráfico quando nenhum é escolhido (top N); a planilha traz TODOS
_FONTE_XLSX = "Arial"


def _pasta_historico_padrao():
    return os.path.join(cfg.pasta_vendas(), "Historico")


def _rotulo_completo(cod, nomes):
    if cod.startswith(cfg.PREFIXO_GRUPO):      # grupo: só o nome dado pelo usuário
        return nomes.get(cod) or cod[len(cfg.PREFIXO_GRUPO):]
    nome = nomes.get(cod)
    return f"{cod} - {nome}" if nome else cod


def _estilos():
    """Fontes, preenchimento, borda e formato numérico usados nas duas abas."""
    from openpyxl.styles import Border, Font, PatternFill, Side
    return SimpleNamespace(
        fmt_valor='#,##0.00;-#,##0.00;"-"',
        f_norm=Font(name=_FONTE_XLSX, size=10),
        f_neg=Font(name=_FONTE_XLSX, size=10, bold=True),
        f_cab=Font(name=_FONTE_XLSX, size=10, bold=True, color="FFFFFF"),
        f_titulo=Font(name=_FONTE_XLSX, size=12, bold=True),
        preench_cab=PatternFill("solid", start_color="305496"),
        borda_topo=Border(top=Side(style="thin")),
    )


def _escrever_tabela(ws, tipo, hist, ordem, est):
    """Aba Histórico: título, cabeçalho, uma linha por item (na ordem `ordem`), TOTAL por
    item e TOTAL DO DIA, tudo com fórmulas; depois as notas (dias sem vendas e a
    composição dos grupos). Retorna as posições que o gráfico precisa:
    {"lin_cab", "lin_ini", "n_dias"}."""
    from openpyxl.styles import Alignment
    from openpyxl.utils import get_column_letter as letra

    datas = hist["datas"]
    dados = hist[tipo]
    nomes = hist["nomes"][tipo]

    n_dias = len(datas)
    col_total = n_dias + 2
    lin_cab = 2
    lin_ini = lin_cab + 1
    lin_fim = lin_ini + len(ordem) - 1
    lin_total = lin_fim + 1

    ws["A1"] = (f"Histórico de vendas - {cfg.TITULOS[tipo]} - "
                f"{hist['periodo_txt'].replace('-', '/')}")
    ws["A1"].font = est.f_titulo

    # Cabeçalho
    ws.cell(lin_cab, 1, "Produto" if tipo == "produtos" else "Departamento")
    for j, d in enumerate(datas, start=2):
        ws.cell(lin_cab, j, hist["rotulos"][d])
    ws.cell(lin_cab, col_total, "TOTAL")
    for j in range(1, col_total + 1):
        c = ws.cell(lin_cab, j)
        c.font, c.fill = est.f_cab, est.preench_cab
        c.alignment = Alignment(horizontal="left" if j == 1 else "right")

    # Linhas de itens (dia sem venda do item = célula vazia)
    for i, cod in enumerate(ordem):
        lin = lin_ini + i
        ws.cell(lin, 1, _rotulo_completo(cod, nomes)).font = est.f_norm
        for j, d in enumerate(datas, start=2):
            v = dados[cod].get(d)
            c = ws.cell(lin, j, None if v is None else round(v, 2))
            c.number_format, c.font = est.fmt_valor, est.f_norm
        c = ws.cell(lin, col_total, f"=SUM({letra(2)}{lin}:{letra(col_total - 1)}{lin})")
        c.number_format, c.font = est.fmt_valor, est.f_neg

    # TOTAL DO DIA (considera todos os itens) e total geral
    ws.cell(lin_total, 1, "TOTAL DO DIA" if hist["unidade"] == "dia" else "TOTAL DA FAIXA")
    for j in range(2, col_total + 1):
        ws.cell(lin_total, j, f"=SUM({letra(j)}{lin_ini}:{letra(j)}{lin_fim})")
    for j in range(1, col_total + 1):
        c = ws.cell(lin_total, j)
        c.font, c.border = est.f_neg, est.borda_topo
        if j > 1:
            c.number_format = est.fmt_valor

    lin_nota = lin_total + 2
    if hist["dias_sem_vendas"]:
        ws.cell(lin_nota, 1,
                ("Dias sem vendas: " if hist["unidade"] == "dia" else "Faixas sem vendas: ")
                + ", ".join(hist["rotulos"][d] for d in hist["dias_sem_vendas"])
                ).font = est.f_norm
        lin_nota += 1
    for chave, membros in hist.get("composicao_grupos", {}).items():   # o que há em cada grupo
        ws.cell(lin_nota, 1, f"{_rotulo_completo(chave, nomes)} = " + ", ".join(membros)
                ).font = est.f_norm
        lin_nota += 1

    ws.column_dimensions["A"].width = min(60, max(len(_rotulo_completo(c, nomes))
                                                  for c in ordem) + 2)
    for j in range(2, col_total + 1):
        ws.column_dimensions[letra(j)].width = 14 if j == col_total else 13
    ws.freeze_panes = ws.cell(lin_ini, 2)
    return {"lin_cab": lin_cab, "lin_ini": lin_ini, "n_dias": n_dias}


def _montar_grafico(wb, ws, tipo, hist, ordem, selecionados, pos, est):
    """Aba Gráfico: uma linha por item ligando o valor vendido em cada dia, lendo as
    células da aba `ws` (posições em `pos`, de _escrever_tabela). Itens: os de
    `selecionados`; sem seleção, os MAX_SERIES_GRAFICO maiores. Deixa o gráfico
    como aba ativa ao abrir."""
    from openpyxl.chart import LineChart, Reference, Series
    from openpyxl.chart.data_source import StrRef
    from openpyxl.chart.series import SeriesLabel

    lin_cab, lin_ini, n_dias = pos["lin_cab"], pos["lin_ini"], pos["n_dias"]
    escolhidos = [c for c in ordem if selecionados and c in selecionados]
    if escolhidos:
        linhas_graf = [lin_ini + ordem.index(c) for c in escolhidos]
    else:
        linhas_graf = list(range(lin_ini, lin_ini + min(MAX_SERIES_GRAFICO, len(ordem))))
    n_series = len(linhas_graf)
    wg = wb.create_sheet("Gráfico")
    tit = cfg.TITULOS[tipo].capitalize()
    if n_series < len(ordem):
        tit += f" - {n_series} selecionados" if escolhidos else f" - {n_series} maiores"
    graf = LineChart()
    graf.title = f"Vendas por {'dia' if hist['unidade'] == 'dia' else 'faixa de horário'} - {tit}"
    graf.y_axis.title = "Valor vendido (R$)"
    graf.y_axis.number_format = "#,##0"
    graf.x_axis.delete = False      # sem isto, versões novas do Excel escondem os eixos
    graf.y_axis.delete = False
    graf.legend.position = "r"
    for lin in linhas_graf:          # uma série por linha escolhida (não precisam ser vizinhas)
        serie = Series(Reference(ws, min_col=2, max_col=n_dias + 1, min_row=lin),
                       title_from_data=False)
        graf.series.append(serie)
        serie.tx = SeriesLabel(strRef=StrRef(f"'{ws.title}'!$A${lin}"))
    graf.set_categories(Reference(ws, min_col=2, max_col=n_dias + 1, min_row=lin_cab))
    for serie in graf.series:        # uma linha por item, com marcador em cada dia
        serie.marker.symbol = "circle"
        serie.marker.size = 6
        serie.smooth = False
    graf.display_blanks = "span"     # dia sem venda do item: a linha liga o dia anterior ao seguinte
    graf.width, graf.height = 32, 16
    wg.add_chart(graf, "A3")
    if n_series < len(ordem):
        wg["A1"] = ((f"Gráfico com os {n_series} itens selecionados; " if escolhidos
                     else f"Gráfico com os {n_series} maiores itens do período; ")
                    + f"a aba Histórico tem todos os {len(ordem)}.")
        wg["A1"].font = est.f_norm

    # Abre direto no gráfico (e sem deixar as duas abas "agrupadas")
    ws.sheet_view.tabSelected = False
    wb.active = wb.index(wg)


def _salvar(wb, tipo, hist, pasta):
    """Grava em <pasta>/historico_<tipo>_<período>.xlsx; com o arquivo aberto no Excel,
    grava com um sufixo de hora em vez de falhar. Retorna o caminho."""
    pasta = pasta or _pasta_historico_padrao()
    os.makedirs(pasta, exist_ok=True)
    base = os.path.join(pasta, f"historico_{tipo}_{hist['arquivo_txt']}")
    caminho = base + ".xlsx"
    try:
        wb.save(caminho)
    except PermissionError:          # arquivo aberto no Excel
        caminho = f"{base}_{datetime.now():%H%M%S}.xlsx"
        wb.save(caminho)
    return caminho


def exportar_historico_xlsx(tipo, hist, pasta=None, selecionados=None):
    """Gera um .xlsx com a MESMA tabela do histórico (uma linha por produto/
    departamento, uma coluna por dia, TOTAL por item e TOTAL DO DIA, tudo com
    fórmulas) e, na aba "Gráfico", um gráfico de linhas (uma por item, ligando o
    valor vendido de dia para dia) com os itens de `selecionados` (códigos); sem
    seleção, os MAX_SERIES_GRAFICO maiores. A aba Histórico traz sempre todos os
    itens. Retorna o caminho do arquivo.

    Grava em <pasta>/historico_<tipo>_<data ini>_a_<data fim>.xlsx (padrão de
    pasta: <pasta de vendas>/Historico). Se o arquivo estiver aberto no Excel,
    grava com um sufixo de hora em vez de falhar."""
    import openpyxl

    dados = hist[tipo]
    if not dados:
        raise ValueError("histórico sem vendas")
    ordem = sorted(dados, key=lambda c: sum(dados[c].values()), reverse=True)

    est = _estilos()
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Histórico"
    pos = _escrever_tabela(ws, tipo, hist, ordem, est)
    _montar_grafico(wb, ws, tipo, hist, ordem, selecionados, pos, est)
    return _salvar(wb, tipo, hist, pasta)


def abrir_arquivo(caminho):
    """Abre o arquivo no programa padrão (Excel). Falha em silêncio."""
    try:
        if os.name == "nt":
            os.startfile(caminho)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", caminho])
        else:
            subprocess.Popen(["xdg-open", caminho])
    except Exception:
        pass
