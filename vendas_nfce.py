"""
vendas_nfce.py — coleta de vendas a partir dos XMLs de NFC-e.

Arquitetura (por que está dividido assim)
-----------------------------------------
  COLETA  ->  ARMAZENAMENTO  ->  LEITURA  ->  RELATÓRIOS
  (XML hoje,   (JSON por dia,    listar_vendas()   (qualquer função
   banco      formato único)     é a ÚNICA porta    que consuma vendas)
   amanhã)                       de entrada
                                 dos consumidores

Os relatórios só conhecem o formato da venda (abaixo) e a função
listar_vendas(). Quando o acesso ao banco existir, basta trocar a coleta
(importar_xmls) por outra que grave vendas no MESMO formato — ou fazer
listar_vendas() ler direto do banco — sem mexer em nenhum relatório.

Formato de uma venda (dict)
---------------------------
{
  "id":         "<chave de acesso de 44 dígitos>",   # único; usado p/ evitar duplicar
  "origem":     "xml_nfce",                           # de onde veio (depois: "banco")
  "modelo":     "65", "serie": "4", "numero": "152071",
  "data":       "09-11-2026",                         # DD-MM-AAAA (mesmo padrão do app)
  "hora":       "15:56:02",
  "data_hora":  "2026-11-09T15:56:02-03:00",
  "total":      14.05,
  "troco":      0.0,
  "pagamentos": [{"forma": "Cartão de Débito", "codigo": "04", "valor": 14.05}],
  "cstat":      "100" | None,                         # status da SEFAZ (None = sem retorno ainda)
  "protocolo":  "253260645007525" | "",
  "valida":     True,                                 # False = rejeitada/denegada
  "itens": [{
      "cod": "1", "descricao": "PAO FRANCES - KG", "ean": "",
      "ncm": "19059090", "cfop": "5405",
      "qtde": 0.416, "unidade": "KG",
      "valor_unit": 22.99, "desconto": 0.0, "valor_total": 9.56,
      "cod_depart": "", "departamento": ""            # opcional; ver 'resolver_departamento'
  }]
}

Atenção: o SammiNFC SOBRESCREVE sempre o mesmo par de arquivos
(1-env-lot.xml / 1-pro-lot.xml) a cada venda. Por isso a coleta precisa
rodar continuamente: iniciar_escutador() faz isso numa thread. Vendas que
acontecerem com o escutador parado (app fechado) não são recuperáveis.

Vários caixas: cada máquina grava só os SEUS arquivos
(!vendas_DD-MM-AAAA_<PC>.json), então não há conflito de gravação quando a
pasta de vendas é compartilhada (OneDrive). listar_vendas() junta tudo.

Uso rápido
----------
    import vendas_nfce as v
    v.iniciar_escutador(resolver_departamento=buscar_departamentos_por_codigo)  # no caixa
    vendas = v.listar_vendas("01-11-2026", "09-11-2026")                        # nos relatórios
"""

import glob
import json
import os
import re
import socket
import sys
import threading
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta

import config as cfg

# ── Configuração ─────────────────────────────────────────────────────────────

# Pasta onde o SammiNFC grava o lote da última venda (mesma do Controle_Caixa).
PASTA_XML_NFCE = r"C:\SammiNFC\#NFC_XML"

# Identifica esta máquina nos arquivos gravados (um conjunto de arquivos por caixa).
CAIXA_ID = re.sub(r"[^A-Za-z0-9_-]", "_", socket.gethostname()) or "caixa"

# Quantos dias o índice lembra das notas já gravadas (só serve para casar um
# retorno da SEFAZ que chegue depois do envio — na prática, segundos).
_DIAS_MEMORIA_INDICE = 7


# Onde as vendas normalizadas são guardadas: MM-AA/DD-MM-AAAA/!vendas_DD-MM-AAAA.json
# (mesma estrutura de pastas usada pelos pedidos). O padrão é decidido em config.py.
PASTA_VENDAS = cfg.pasta_vendas_padrao()

_CSTAT_VALIDOS = {"100", "150"}          # autorizada / autorizada fora de prazo

_FORMAS_PAGAMENTO = {
    "01": "Dinheiro", "02": "Cheque", "03": "Cartão de Crédito",
    "04": "Cartão de Débito", "05": "Crédito Loja", "10": "Vale Alimentação",
    "11": "Vale Refeição", "12": "Vale Presente", "13": "Vale Combustível",
    "15": "Boleto", "16": "Depósito", "17": "PIX", "18": "Transferência",
    "19": "Fidelidade/Cashback", "90": "Sem pagamento", "99": "Outros",
}


# ── Utilidades ───────────────────────────────────────────────────────────────

def _num(txt, padrao=0.0):
    try:
        return float(txt)
    except (TypeError, ValueError):
        return padrao


def _ler_json(caminho, padrao):
    if not os.path.isfile(caminho):
        return padrao
    try:
        with open(caminho, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return padrao


def _gravar_json(caminho, dados):
    """Grava de forma atômica (arquivo temporário + replace)."""
    os.makedirs(os.path.dirname(caminho), exist_ok=True)
    tmp = caminho + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, indent=2)
    os.replace(tmp, caminho)


def _caminho_dia(pasta_vendas, data_str, caixa=None):
    """Arquivo do dia DESTA máquina: MM-AA/DD-MM-AAAA/!vendas_DD-MM-AAAA_<PC>.json"""
    dt = datetime.strptime(data_str, cfg.FMT_DATA)
    return os.path.join(pasta_vendas, dt.strftime("%m-%y"), data_str,
                        f"!vendas_{data_str}_{caixa or CAIXA_ID}.json")


def _caminho_indice(pasta_vendas, caixa=None):
    return os.path.join(pasta_vendas, f"!indice_importacao_{caixa or CAIXA_ID}.json")


# ── Leitura do XML ───────────────────────────────────────────────────────────
# Usa o curinga de namespace "{*}" para funcionar com ou sem xmlns.

def _achar(root, tag):
    """Todos os elementos <tag> do arquivo (inclusive a raiz), ignorando namespace.
    (Element.iter() não aceita o curinga '{*}', por isso o iterfind.)"""
    if root.tag.split("}")[-1] == tag:
        yield root
    yield from root.iterfind(".//{*}" + tag)


def _parse_nfe(nfe):
    """Converte um elemento <NFe> no formato de venda. None se não for válido."""
    inf = nfe.find("{*}infNFe")
    if inf is None:
        return None
    chave = (inf.get("Id") or "")[3:]            # remove o prefixo "NFe"
    if len(chave) != 44:
        return None

    ide = inf.find("{*}ide")
    dh = ide.findtext("{*}dhEmi", "") if ide is not None else ""
    try:
        dt = datetime.fromisoformat(dh)
    except ValueError:
        return None

    itens = []
    for det in inf.findall("{*}det"):
        prod = det.find("{*}prod")
        if prod is None:
            continue
        v_prod = _num(prod.findtext("{*}vProd"))
        v_desc = _num(prod.findtext("{*}vDesc"))
        ean = (prod.findtext("{*}cEAN") or "").strip()
        itens.append({
            "cod": (prod.findtext("{*}cProd") or "").strip(),
            "descricao": (prod.findtext("{*}xProd") or "").strip(),
            "ean": "" if ean.upper() == "SEM GTIN" else ean,
            "ncm": (prod.findtext("{*}NCM") or "").strip(),
            "cfop": (prod.findtext("{*}CFOP") or "").strip(),
            "qtde": round(_num(prod.findtext("{*}qCom")), 4),
            "unidade": (prod.findtext("{*}uCom") or "UN").strip().upper(),
            "valor_unit": round(_num(prod.findtext("{*}vUnCom")), 4),
            "desconto": round(v_desc, 2),
            "valor_total": round(v_prod - v_desc, 2),
            "cod_depart": "",
            "departamento": "",
        })

    pagamentos = []
    for dp in inf.findall("{*}pag/{*}detPag"):
        cod = (dp.findtext("{*}tPag") or "").strip()
        pagamentos.append({
            "forma": _FORMAS_PAGAMENTO.get(cod, f"Outros ({cod})"),
            "codigo": cod,
            "valor": round(_num(dp.findtext("{*}vPag")), 2),
        })

    return {
        "id": chave,
        "origem": "xml_nfce",
        "modelo": ide.findtext("{*}mod", ""),
        "serie": ide.findtext("{*}serie", ""),
        "numero": ide.findtext("{*}nNF", ""),
        "data": dt.strftime(cfg.FMT_DATA),         # data local de emissão (como no XML)
        "hora": dt.strftime("%H:%M:%S"),
        "data_hora": dh,
        "total": round(_num(inf.findtext("{*}total/{*}ICMSTot/{*}vNF")), 2),
        "troco": round(_num(inf.findtext("{*}pag/{*}vTroco")), 2),
        "pagamentos": pagamentos,
        "cstat": None,
        "protocolo": "",
        "valida": True,
        "itens": itens,
    }


def _parse_protocolos(root):
    """{chave: {cstat, protocolo, valida}} de todos os <protNFe> do arquivo."""
    resultado = {}
    for prot in _achar(root, "protNFe"):
        inf = prot.find("{*}infProt")
        if inf is None:
            continue
        chave = inf.findtext("{*}chNFe", "")
        cstat = (inf.findtext("{*}cStat") or "").strip()
        if chave:
            resultado[chave] = {
                "cstat": cstat,
                "protocolo": (inf.findtext("{*}nProt") or "").strip(),
                "valida": cstat in _CSTAT_VALIDOS,
            }
    return resultado


def _listar_xmls(pasta, recursivo=True):
    if not os.path.isdir(pasta):
        return []
    if not recursivo:
        return sorted(os.path.join(pasta, n) for n in os.listdir(pasta)
                      if n.lower().endswith(".xml"))
    achados = []
    for raiz, _, arquivos in os.walk(pasta):
        for n in arquivos:
            if n.lower().endswith(".xml"):
                achados.append(os.path.join(raiz, n))
    return sorted(achados)


# ── COLETA (hoje: XML; depois: trocar por banco) ─────────────────────────────

def importar_xmls(pasta_xml=None, pasta_vendas=None, resolver_departamento=None,
                  recursivo=True, caixa=None):
    """Lê os XMLs novos/alterados de 'pasta_xml' e grava as vendas em
    'pasta_vendas'. Pode ser chamada quantas vezes quiser: arquivos já
    lidos são pulados e a mesma nota nunca é gravada duas vezes (a chave
    de acesso é o identificador).

    Funciona com os dois arquivos de cada lote (envio '*-env-lot.xml' e
    retorno '*-pro-lot.xml', em qualquer ordem/momento) e também com
    XMLs de distribuição (<nfeProc>), que já trazem nota + protocolo.

    'resolver_departamento' é opcional: função que recebe uma lista de
    códigos de produto e devolve {cod: (cod_depart, departamento, unidade)}
    — exatamente o que buscar_departamentos_por_codigo() do app devolve.
    Se informada, o departamento é gravado junto com a venda (foto do
    momento da importação). Se falhar, a importação segue sem departamento.

    Retorna um resumo: {lidos, ignorados, novas, atualizadas, erros}.
    """
    pasta_xml = pasta_xml or PASTA_XML_NFCE
    pasta_vendas = pasta_vendas or PASTA_VENDAS
    caixa = caixa or CAIXA_ID

    indice = _ler_json(_caminho_indice(pasta_vendas, caixa), {})
    arquivos_idx = indice.setdefault("arquivos", {})      # caminho -> [mtime, tamanho]
    chaves_idx = indice.setdefault("chaves", {})          # chave -> data DD-MM-AAAA
    pendentes = indice.setdefault("protocolos_pendentes", {})

    resumo = {"lidos": 0, "ignorados": 0, "novas": 0, "atualizadas": 0, "erros": []}
    notas, protocolos = {}, dict(pendentes)

    for caminho in _listar_xmls(pasta_xml, recursivo):
        try:
            st = os.stat(caminho)
            assinatura = [st.st_mtime_ns, st.st_size]
            if arquivos_idx.get(caminho) == assinatura:
                resumo["ignorados"] += 1
                continue
            root = ET.parse(caminho).getroot()
        except Exception as e:
            # Pode ser um arquivo ainda sendo escrito: não indexa, tenta de novo depois.
            resumo["erros"].append((caminho, str(e)))
            continue
        for nfe in _achar(root, "NFe"):
            venda = _parse_nfe(nfe)
            if venda:
                notas[venda["id"]] = venda
        protocolos.update(_parse_protocolos(root))
        arquivos_idx[caminho] = assinatura
        resumo["lidos"] += 1

    # Une o protocolo às notas lidas agora
    for chave, venda in notas.items():
        if chave in protocolos:
            venda.update(protocolos[chave])

    # Departamento (uma única consulta para todos os produtos novos)
    if resolver_departamento and notas:
        cods = {i["cod"] for v in notas.values() for i in v["itens"] if i["cod"]}
        try:
            mapa = resolver_departamento(sorted(cods)) or {}
        except Exception:
            mapa = {}
        for venda in notas.values():
            for item in venda["itens"]:
                info = mapa.get(item["cod"])
                if info:
                    item["cod_depart"], item["departamento"] = info[0], info[1]

    # Dias afetados: notas novas + protocolos de notas já gravadas antes
    por_dia = {}
    for venda in notas.values():
        por_dia.setdefault(venda["data"], {"novas": [], "protocolos": {}})["novas"].append(venda)
    for chave, prot in protocolos.items():
        if chave not in notas and chave in chaves_idx:
            por_dia.setdefault(chaves_idx[chave], {"novas": [], "protocolos": {}}
                               )["protocolos"][chave] = prot

    for data, mudancas in por_dia.items():
        caminho_dia = _caminho_dia(pasta_vendas, data, caixa)
        lista = _ler_json(caminho_dia, [])
        por_id = {v["id"]: v for v in lista}
        for venda in mudancas["novas"]:
            existente = por_id.get(venda["id"])
            if existente is None:
                venda["caixa"] = caixa
                lista.append(venda)
                por_id[venda["id"]] = venda
                resumo["novas"] += 1
            elif venda["cstat"] and existente.get("cstat") != venda["cstat"]:
                existente.update({k: venda[k] for k in ("cstat", "protocolo", "valida")})
                resumo["atualizadas"] += 1
            chaves_idx[venda["id"]] = data
        for chave, prot in mudancas["protocolos"].items():
            existente = por_id.get(chave)
            if existente is not None and existente.get("cstat") != prot["cstat"]:
                existente.update(prot)
                resumo["atualizadas"] += 1
        lista.sort(key=lambda v: v.get("data_hora") or "")
        _gravar_json(caminho_dia, lista)

    # Protocolos ainda sem nota correspondente ficam esperando (máx. 200)
    pendentes_novos = {c: p for c, p in protocolos.items() if c not in chaves_idx}
    indice["protocolos_pendentes"] = dict(list(pendentes_novos.items())[-200:])

    # Poda: só lembra das notas dos últimos dias (o índice não cresce sem limite)
    if resumo["lidos"] or notas:
        limite = (datetime.now() - timedelta(days=_DIAS_MEMORIA_INDICE)).strftime("%Y%m%d")
        indice["chaves"] = {
            c: d for c, d in chaves_idx.items()
            if d[6:] + d[3:5] + d[:2] >= limite          # DD-MM-AAAA -> AAAAMMDD
        }
        _gravar_json(_caminho_indice(pasta_vendas, caixa), indice)
    return resumo


# ── LEITURA (única porta de entrada dos relatórios) ──────────────────────────

def _preferir(a, b):
    """Entre duas cópias da mesma venda, fica a que já tem o retorno da SEFAZ."""
    if a is None:
        return b
    return b if (b.get("cstat") and not a.get("cstat")) else a


def listar_vendas(data_de=None, data_ate=None, incluir_invalidas=False,
                  pasta_vendas=None):
    """Retorna as vendas entre data_de e data_ate (inclusive, DD-MM-AAAA).
    Qualquer ponta pode ser None (sem limite). Por padrão exclui notas
    rejeitadas/denegadas ('valida' == False). Ordenadas por data/hora.

    ESTA é a função que os relatórios devem usar. Quando a fonte passar a
    ser o banco, só o corpo dela muda — o formato de retorno é o mesmo.
    """
    pasta_vendas = pasta_vendas or PASTA_VENDAS
    dt_de = datetime.strptime(data_de, cfg.FMT_DATA) if data_de else None
    dt_ate = datetime.strptime(data_ate, cfg.FMT_DATA) if data_ate else None

    por_id = {}                       # junta os arquivos de todos os caixas, sem duplicar
    if not os.path.isdir(pasta_vendas):
        return []
    for pasta_mes in os.listdir(pasta_vendas):
        caminho_mes = os.path.join(pasta_vendas, pasta_mes)
        if not os.path.isdir(caminho_mes):
            continue
        for pasta_dia in os.listdir(caminho_mes):
            try:
                dt = datetime.strptime(pasta_dia, cfg.FMT_DATA)
            except ValueError:
                continue
            if (dt_de and dt < dt_de) or (dt_ate and dt > dt_ate):
                continue
            pasta_do_dia = os.path.join(caminho_mes, pasta_dia)
            for arq in glob.glob(os.path.join(pasta_do_dia, f"!vendas_{pasta_dia}*.json")):
                for venda in _ler_json(arq, []):
                    if incluir_invalidas or venda.get("valida", True):
                        por_id[venda["id"]] = _preferir(por_id.get(venda["id"]), venda)
    vendas = sorted(por_id.values(), key=lambda v: v.get("data_hora") or "")
    return vendas


# ── ESCUTADOR (roda no app que já fica aberto no caixa) ──────────────────────

_escutador_ativo = False
ultimo_erro = None          # último erro do escutador (para diagnóstico)


def iniciar_escutador(pasta_xml=None, pasta_vendas=None, resolver_departamento=None,
                      intervalo=0.5):
    """Inicia (uma única vez por processo) uma thread que vigia a pasta do
    SammiNFC e chama importar_xmls() sempre que algum XML mudar.

    Como o SammiNFC reescreve o mesmo arquivo a cada venda, o escutador
    compara a assinatura (nome, data de modificação, tamanho) dos XMLs a
    cada 'intervalo' segundos — barato (só 'stat' nos arquivos). Se um
    arquivo estiver sendo escrito no momento, a leitura falha, nada é
    marcado como lido e a próxima rodada tenta de novo.

    Devolve a thread, ou None se já havia um escutador rodando aqui.
    """
    global _escutador_ativo
    if _escutador_ativo:
        return None
    _escutador_ativo = True
    pasta_xml = pasta_xml or PASTA_XML_NFCE

    def assinatura_pasta():
        try:
            itens = []
            for nome in os.listdir(pasta_xml):
                if nome.lower().endswith(".xml"):
                    st = os.stat(os.path.join(pasta_xml, nome))
                    itens.append((nome, st.st_mtime_ns, st.st_size))
            return tuple(sorted(itens))
        except OSError:
            return None

    def laco():
        global ultimo_erro
        ultima = "inicio"            # força a primeira importação ao iniciar
        while True:
            try:
                atual = assinatura_pasta()
                if atual is not None and atual != ultima:
                    time.sleep(0.3)                  # deixa o arquivo "assentar"
                    r = importar_xmls(pasta_xml, pasta_vendas, resolver_departamento,
                                      recursivo=False)
                    # Se algum arquivo falhou (em escrita), repete na próxima volta
                    ultima = atual if not r["erros"] else "inicio"
            except Exception as e:
                ultimo_erro = repr(e)
            time.sleep(intervalo)

    t = threading.Thread(target=laco, name="escutador_vendas_nfce", daemon=True)
    t.start()
    return t


if __name__ == "__main__":
    # python vendas_nfce.py [pasta_xml]  -> importa uma vez e mostra o resumo
    r = importar_xmls(sys.argv[1] if len(sys.argv) > 1 else None, recursivo=False)
    print(f"Lidos: {r['lidos']}  Ignorados: {r['ignorados']}  "
          f"Novas: {r['novas']}  Atualizadas: {r['atualizadas']}  "
          f"Erros: {len(r['erros'])}")
    for caminho, erro in r["erros"]:
        print("  ERRO:", caminho, "-", erro)
