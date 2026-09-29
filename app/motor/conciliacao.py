"""
Decisão 4 — tolerância na conciliação (nota fiscal × aquisição combinada).

A linha entre "aceitável" e "divergência" é traçada em três camadas:
  1. Arredondamento (mecânico): diferença que a representação decimal explica.
     Preço combinado tem 2 casas; a nota pode ter até 10 no unitário.
     → < R$ 0,01 no unitário e ≤ R$ 0,005 por unidade no total = conforme.
  2. Materialidade (econômica): diferença real, mas pequena demais para valer
     a contestação → registrada em âmbar, sem alarme.
     Limite = maior entre R$ 10 e 1% do valor da linha.
  3. Acúmulo (padrão): diferenças pequenas do mesmo fornecedor somam. Passou de
     R$ 50 em 90 dias → vira alerta. Ninguém "vaza" dinheiro de centavo em centavo.

Quantidade de item contável: tolerância zero. Falta dentro do prazo é entrega
parcial (âmbar); fora do prazo é faltante (vermelho). Excesso é sempre vermelho.

Formato lido: subconjunto do layout NF-e 4.00 (det/prod com qCom, vUnCom, vProd
e xPed = número do pedido de compra). A NFS-e municipal (ABRASF) não tem
quantidade estruturada; no MVP, notas de serviço seguem o mesmo layout
simplificado. O parser fica isolado aqui para ser trocado pelo layout real.
"""
import re
import xml.etree.ElementTree as ET
from datetime import date, timedelta

from app import config
from app.motor.capacidade import prazo_entrega, recebido_por_aquisicao, situacao
from app.motor.formato import num, pct

ORDEM = {"ok": 0, "atencao": 1, "divergencia": 2}


class NotaInvalida(Exception):
    pass


def brl(v: float) -> str:
    s = f"{abs(v):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{'-' if v < 0 else ''}R$ {s}"


def so_digitos(s: str) -> str:
    return re.sub(r"\D", "", s or "")


def digito_verificador_chave(chave43: str) -> int:
    """Módulo 11 com pesos 2 a 9 da direita para a esquerda (padrão da chave de acesso NF-e)."""
    soma, peso = 0, 2
    for d in reversed(chave43):
        soma += int(d) * peso
        peso = 2 if peso == 9 else peso + 1
    dv = 11 - soma % 11
    return 0 if dv >= 10 else dv


def chave_valida(chave: str) -> bool:
    return len(chave) == 44 and chave.isdigit() and digito_verificador_chave(chave[:43]) == int(chave[43])


# ---------------------------------------------------------------------------
# Leitura do XML
# ---------------------------------------------------------------------------
def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _achar(el, nome):
    for filho in el.iter():
        if _local(filho.tag) == nome:
            return filho
    return None


def _texto(el, nome, obrigatorio=True):
    alvo = _achar(el, nome)
    if alvo is None or alvo.text is None or not alvo.text.strip():
        if obrigatorio:
            raise NotaInvalida(f"Campo obrigatório ausente: <{nome}>.")
        return None
    return alvo.text.strip()


def _numero(el, nome):
    try:
        return float(_texto(el, nome))
    except ValueError:
        raise NotaInvalida(f"Valor não numérico em <{nome}>.")


def ler_nota(conteudo: bytes) -> dict:
    if len(conteudo) > config.TAMANHO_MAXIMO_XML:
        raise NotaInvalida("Arquivo maior que 2 MB: não parece uma nota fiscal.")
    # Nota fiscal nunca declara DOCTYPE/ENTITY. Recusar evita ataques de expansão
    # de entidades (billion laughs) e leitura de arquivos locais (XXE).
    if re.search(rb"<!DOCTYPE|<!ENTITY", conteudo, re.IGNORECASE):
        raise NotaInvalida("XML com DOCTYPE ou ENTITY recusado por segurança.")
    try:
        raiz = ET.fromstring(conteudo)
    except ET.ParseError as e:
        raise NotaInvalida(f"XML malformado: {e}.")
    inf = _achar(raiz, "infNFe")
    if inf is None:
        raise NotaInvalida("Não encontrei o grupo <infNFe>: o arquivo não parece uma NF-e.")
    chave = so_digitos(inf.get("Id", "")) or so_digitos(_texto(raiz, "chNFe", obrigatorio=False) or "")
    emit = _achar(inf, "emit")
    if emit is None:
        raise NotaInvalida("Nota sem emitente (<emit>).")
    itens = []
    for det in (e for e in inf.iter() if _local(e.tag) == "det"):
        prod = _achar(det, "prod")
        if prod is None:
            raise NotaInvalida("Item sem grupo <prod>.")
        itens.append({
            "n": int(det.get("nItem", len(itens) + 1)),
            "codigo_produto": _texto(prod, "cProd", obrigatorio=False),
            "descricao": _texto(prod, "xProd"),
            "quantidade": _numero(prod, "qCom"),
            "preco_unitario": _numero(prod, "vUnCom"),
            "valor_total": _numero(prod, "vProd"),
            "pedido": _texto(prod, "xPed", obrigatorio=False),
        })
    if not itens:
        raise NotaInvalida("Nota sem itens (<det>).")
    return {
        "chave": chave,
        "numero": _texto(inf, "nNF"),
        "emissao": _texto(inf, "dhEmi")[:10],
        "emitente_cnpj": so_digitos(_texto(emit, "CNPJ")),
        "emitente_nome": _texto(emit, "xNome"),
        "itens": itens,
    }


# ---------------------------------------------------------------------------
# Regras
# ---------------------------------------------------------------------------
def _check(tipo, status, titulo, detalhe, **valores):
    return {"tipo": tipo, "status": status, "titulo": titulo, "detalhe": detalhe, "valores": valores}


def _pior(checks) -> str:
    return max((c["status"] for c in checks), key=ORDEM.get, default="ok")


def avaliar_preco(qtd: float, unit_nota: float, total_nota: float, unit_combinado: float,
                  acumulado_antes: float) -> tuple[dict, str, float]:
    """Devolve (verificação, status_preco para gravar, diferença em R$)."""
    esperado = round(qtd * unit_combinado, 2)
    du = unit_nota - unit_combinado
    dt = round(total_nota - esperado, 2)
    tol = max(0.01, config.MEIO_CENTAVO * qtd)
    vals = dict(unit_nota=unit_nota, unit_combinado=unit_combinado, total_nota=total_nota,
                total_esperado=esperado, diferenca=dt, tolerancia=round(tol, 2))
    if abs(du) < config.TOLERANCIA_UNITARIO and abs(dt) <= tol + 1e-9:
        det = ("Valores idênticos ao combinado." if dt == 0 else
               f"Diferença de {brl(dt)} no total, dentro do arredondamento possível ({brl(tol)} para {qtd:g} un.).")
        return _check("preco", "ok", "Preço conforme", det, **vals), "conforme", dt
    if dt < 0:
        return (_check("preco", "atencao", "Cobrado abaixo do combinado",
                       f"{brl(-dt)} a menos. Confirme com o fornecedor: pode ser item trocado ou cobrança posterior.", **vals),
                "a_favor", dt)
    limite = max(config.MATERIALIDADE_MINIMA, config.MATERIALIDADE_PERCENTUAL * esperado)
    vals["limite_material"] = round(limite, 2)
    if dt > limite:
        return (_check("preco", "divergencia", "Diferença material de preço",
                       f"{brl(dt)} acima do combinado ({pct(du / unit_combinado)} no unitário), maior que o limite de "
                       f"{brl(limite)}. Conteste antes de pagar.", **vals), "material", dt)
    acumulado = round(acumulado_antes + dt, 2)
    vals["acumulado_fornecedor"] = acumulado
    if acumulado > config.LIMITE_ACUMULADO_FORNECEDOR:
        return (_check("preco", "divergencia", "Diferenças pequenas recorrentes",
                       f"Esta nota traz {brl(dt)} a mais — sozinha seria tolerável, mas o fornecedor já soma "
                       f"{brl(acumulado)} em diferenças pequenas nos últimos {config.JANELA_ACUMULO_DIAS} dias "
                       f"(limite {brl(config.LIMITE_ACUMULADO_FORNECEDOR)}).", **vals), "menor", dt)
    return (_check("preco", "atencao", "Diferença pequena registrada",
                   f"{brl(dt)} acima do combinado, abaixo do limite de materialidade ({brl(limite)}). "
                   f"Fica registrada e somada ao histórico do fornecedor ({brl(acumulado)} em "
                   f"{config.JANELA_ACUMULO_DIAS} dias).", **vals), "menor", dt)


def conciliar(ctx, nota: dict, hoje: date) -> dict:
    cabecalho = {k: nota[k] for k in ("chave", "numero", "emissao", "emitente_cnpj", "emitente_nome")}
    if nota["chave"] in ctx.chaves_importadas:
        return {**cabecalho, "status": "rejeitada", "rejeitada": True,
                "motivo": "Esta nota já foi importada. Importar de novo contaria a mesma mercadoria duas vezes.",
                "verificacoes": [], "itens": []}
    if not chave_valida(nota["chave"]):
        return {**cabecalho, "status": "rejeitada", "rejeitada": True,
                "motivo": "Chave de acesso inválida (44 dígitos com dígito verificador). Confira se o arquivo é o original.",
                "verificacoes": [], "itens": []}

    recebido = recebido_por_aquisicao(ctx.recebimentos)
    ja_nesta_nota: dict[int, float] = {}
    menores_nesta_nota: dict[int, float] = {}
    inicio_acumulo = hoje - timedelta(days=config.JANELA_ACUMULO_DIAS)
    aq_por_id = {a.id: a for a in ctx.aquisicoes}

    itens = []
    for it in nota["itens"]:
        checks = []
        calc = round(it["quantidade"] * it["preco_unitario"], 2)
        if abs(calc - it["valor_total"]) > 0.01 + 1e-9:
            checks.append(_check("consistencia", "divergencia", "Nota inconsistente",
                                 f"Na própria nota, {it['quantidade']:g} × {it['preco_unitario']:.4f} = {brl(calc)}, "
                                 f"mas o total do item diz {brl(it['valor_total'])}."))
        aq = ctx.aquisicao_por_codigo(it["pedido"]) if it["pedido"] else None
        if aq is None:
            checks.append(_check("vinculo", "divergencia", "Pedido não encontrado",
                                 f"O campo de pedido (xPed) traz '{it['pedido'] or 'vazio'}', que não corresponde a "
                                 f"nenhuma aquisição. Vincule manualmente antes de aceitar."))
            itens.append({**it, "aquisicao": None, "status": _pior(checks), "verificacoes": checks,
                          "importavel": False})
            continue

        f, s = ctx.fornecedor(aq.fornecedor_id), ctx.servico(aq.servico_id)
        checks.insert(0, _check("vinculo", "ok", "Pedido localizado",
                                f"{aq.codigo}: {aq.quantidade:g} × {s.nome} com {f.nome}, pedido em {aq.data_pedido:%d/%m/%Y}."))
        if so_digitos(f.cnpj) != nota["emitente_cnpj"]:
            checks.append(_check("emitente", "divergencia", "Emitente diferente do fornecedor",
                                 f"A nota foi emitida por {nota['emitente_nome']} (CNPJ {nota['emitente_cnpj']}), "
                                 f"mas o pedido {aq.codigo} é com {f.nome}."))

        antes = recebido.get(aq.id, 0) + ja_nesta_nota.get(aq.id, 0)
        total = antes + it["quantidade"]
        ja_nesta_nota[aq.id] = ja_nesta_nota.get(aq.id, 0) + it["quantidade"]
        sit = situacao(aq, f, total, hoje, s.tipo_quantidade)
        prazo = prazo_entrega(aq, f)
        qv = dict(pedido=aq.quantidade, recebido_antes=antes, nesta_nota=it["quantidade"], total=total,
                  prazo=prazo.isoformat())
        if sit == "recebida":
            checks.append(_check("quantidade", "ok", "Quantidade confere",
                                 f"Total recebido {total:g} de {aq.quantidade:g}"
                                 + (f" ({antes:g} em notas anteriores)." if antes else "."), **qv))
        elif sit == "excedente":
            checks.append(_check("quantidade", "divergencia", "Veio mais do que o pedido",
                                 f"{total - aq.quantidade:g} {s.unidade}(s) além das {aq.quantidade:g} combinadas. "
                                 f"Recuse o excesso ou formalize um novo pedido.", **qv))
        elif sit == "parcial":
            checks.append(_check("quantidade", "atencao", "Entrega parcial",
                                 f"Faltam {aq.quantidade - total:g}. Ainda dentro do prazo (até {prazo:%d/%m}).", **qv))
        else:  # faltante
            checks.append(_check("quantidade", "divergencia", "Quantidade faltante",
                                 f"Faltam {aq.quantidade - total:g} e o prazo acabou em {prazo:%d/%m}.", **qv))

        acumulado = sum(r.diferenca_valor for r in ctx.recebimentos
                        if r.status_preco == "menor" and r.data_recebimento >= inicio_acumulo
                        and aq_por_id[r.aquisicao_id].fornecedor_id == f.id)
        acumulado += menores_nesta_nota.get(f.id, 0)
        check_preco, status_preco, dif = avaliar_preco(it["quantidade"], it["preco_unitario"], it["valor_total"],
                                                       aq.preco_unitario, acumulado)
        if status_preco == "menor":
            menores_nesta_nota[f.id] = menores_nesta_nota.get(f.id, 0) + dif
        checks.append(check_preco)
        itens.append({**it, "aquisicao": aq.codigo, "aquisicao_id": aq.id, "servico": s.nome,
                      "fornecedor": f.nome, "status": _pior(checks), "verificacoes": checks,
                      "status_preco": status_preco, "diferenca_valor": dif, "importavel": True})

    status = max((i["status"] for i in itens), key=ORDEM.get)
    return {**cabecalho, "status": status, "rejeitada": False, "motivo": None, "itens": itens,
            "valor_total": round(sum(i["valor_total"] for i in itens), 2)}
