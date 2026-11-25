"""
config.py — configuração compartilhada do relatório de vendas.
Os outros módulos usam `import config as cfg` e leem cfg.PASTA_VENDAS etc. na hora
do uso, então trocar um valor aqui (ou em tempo de execução) vale para todos.

A pasta de vendas é resolvida SÓ aqui: quem precisa dela chama pasta_vendas().
"""

import os

# None = usar o padrão (OneDrive\Documentos\Vendas, ver pasta_vendas_padrao()).
PASTA_VENDAS = None


def pasta_vendas_padrao():
    """OneDrive\\Documentos\\Vendas da máquina (variável de ambiente do OneDrive, ou
    ~/OneDrive quando ela não existe)."""
    caminho = os.environ.get("OneDrive") or os.environ.get("OneDriveConsumer")
    if not (caminho and os.path.isdir(caminho)):
        caminho = os.path.join(os.path.expanduser("~"), "OneDrive")
    return os.path.join(caminho, "Documentos", "Vendas")


def pasta_vendas():
    """Pasta de vendas em uso: PASTA_VENDAS, se foi definida, senão o padrão."""
    return PASTA_VENDAS or pasta_vendas_padrao()


# Chave usada nos agrupamentos para itens sem departamento conhecido.
DEPTO_SEM = "SEM_DEPTO"

# Prefixo da chave dos grupos criados pelo usuário no Histórico (nunca colide com
# código de produto/departamento).
PREFIXO_GRUPO = "@grupo:"

DIAS_SEMANA = ["seg", "ter", "qua", "qui", "sex", "sáb", "dom"]

# Formato ÚNICO das datas que trafegam como texto (fonte, cache, JSONs, entradas da tela).
FMT_DATA = "%d-%m-%Y"

# Faixa de horas quando não há filtro (comparação por minuto, inclusive).
HORA_MIN, HORA_MAX = "00:00", "23:59"

# Títulos dos relatórios do histórico (chaves = tipo: "produtos" / "departamentos").
TITULOS = {"produtos": "PRODUTOS", "departamentos": "DEPARTAMENTOS"}

# ── Limites de entrada (a interface e o cálculo leem daqui) ──────────────────

# Histórico: período máximo (dias) e intervalo da soma por faixa (minutos).
MAX_DIAS_HISTORICO = 31
INTERVALO_MIN, INTERVALO_MAX = 1, 1440

# Desvios do dia: período máximo analisado de uma vez (dias).
MAX_DIAS_DESVIOS = 31

# Projeção e Desvios do dia: semanas da base e tamanho da faixa horária (minutos).
SEMANAS_MIN, SEMANAS_MAX = 2, 26
PASSO_MIN, PASSO_MAX = 5, 240
