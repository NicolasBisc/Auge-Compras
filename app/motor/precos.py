"""
Decisão 3 — preço fora do padrão.

Duas perguntas diferentes, duas métricas separadas:
  1. "Este fornecedor mudou o preço dele?"  → variação contra a PRÓPRIA história
  2. "Este fornecedor é mais caro que os outros?" → comparação entre fornecedores

Referência = mediana, não média: um preço isolado errado não arrasta a mediana,
e quando o preço novo se repete (vira patamar), a mediana passa a ser ele.
Dispersão = MAD (desvio absoluto mediano), que também não é arrastado por outliers.
"""
from datetime import date, timedelta
from statistics import median

from app import config
from app.motor.formato import brl, num, pct

CONSTANTE_Z = 0.6745  # torna o MAD comparável ao desvio padrão numa distribuição normal


def mad(valores: list[float], centro: float) -> float:
    return median(abs(v - centro) for v in valores) if valores else 0.0


def _compras_do_par(aquisicoes, servico_id, fornecedor_id):
    return sorted((a for a in aquisicoes
                   if a.servico_id == servico_id and a.fornecedor_id == fornecedor_id),
                  key=lambda a: (a.data_pedido, a.id))


def precos_anteriores(aquisicoes, aq) -> list[float]:
    """Últimos N preços do mesmo par, antes desta compra, dentro da janela."""
    inicio = aq.data_pedido - timedelta(days=config.JANELA_PRECO_DIAS)
    anteriores = [a for a in _compras_do_par(aquisicoes, aq.servico_id, aq.fornecedor_id)
                  if inicio <= a.data_pedido <= aq.data_pedido and a.id != aq.id
                  and (a.data_pedido, a.id) < (aq.data_pedido, aq.id)]
    return [a.preco_unitario for a in anteriores[-config.N_PRECOS_REFERENCIA:]]


def avaliar_preco(preco: float, anteriores: list[float]) -> dict:
    """Classifica um preço contra a história do par. Níveis: sem_base, normal, nota, alerta, queda."""
    if len(anteriores) < config.MIN_PRECOS_REFERENCIA:
        return {"nivel": "sem_base", "referencia": None, "variacao": None, "z": None, "rebaixado": False,
                "motivo": f"Ainda sem comparação: {len(anteriores)} compra(s) anterior(es) deste fornecedor, "
                          f"e são precisas {config.MIN_PRECOS_REFERENCIA} para existir um padrão."}
    ref = median(anteriores)
    var = (preco - ref) / ref
    disp = mad(anteriores, ref)
    z = CONSTANTE_Z * (preco - ref) / disp if disp > 0 else None

    if var >= config.LIMIAR_ALERTA:
        nivel = "alerta"
    elif var >= config.LIMIAR_NOTA:
        nivel = "nota"
    elif var <= -config.LIMIAR_NOTA:
        nivel = "queda"
    else:
        nivel = "normal"

    motivo = f"{pct(var)} sobre o preço habitual de {brl(ref)} (mediana das últimas {len(anteriores)} compras)."
    rebaixado = False
    if nivel in ("alerta", "nota", "queda") and z is not None and abs(z) < config.LIMIAR_Z_MODIFICADO:
        rebaixado = True
        motivo += (f" Esse fornecedor costuma oscilar assim, então o aviso foi rebaixado "
                   f"(z modificado de {num(z)}, limite {num(config.LIMIAR_Z_MODIFICADO)}).")
        nivel = {"alerta": "nota", "nota": "normal", "queda": "normal"}[nivel]
    elif z is None and nivel != "normal":
        motivo += " Esse fornecedor mantinha o preço fixo, então a mudança chama atenção."
    return {"nivel": nivel, "referencia": round(ref, 4), "variacao": round(var, 6),
            "z": None if z is None else round(z, 2), "motivo": motivo, "rebaixado": rebaixado}


def avaliar_aquisicao(aquisicoes, aq) -> dict:
    return avaliar_preco(aq.preco_unitario, precos_anteriores(aquisicoes, aq))


def referencia_atual(aquisicoes, servico_id, fornecedor_id, hoje: date) -> dict | None:
    """
    Preço esperado para a próxima compra deste par.
    Regra: mediana das últimas N compras. Exceção conservadora: se a ÚLTIMA compra
    foi um aumento em nível de alerta, usa o último preço — pode ser um novo
    patamar, e orçar pela mediana subestimaria o custo.
    """
    inicio = hoje - timedelta(days=config.JANELA_PRECO_DIAS)
    par = [a for a in _compras_do_par(aquisicoes, servico_id, fornecedor_id)
           if inicio <= a.data_pedido <= hoje]
    if not par:
        return None
    ultimas = par[-config.N_PRECOS_REFERENCIA:]
    ref = median(a.preco_unitario for a in ultimas)
    ultima = par[-1]
    aval = avaliar_aquisicao(aquisicoes, ultima)
    usa_ultimo = aval["nivel"] == "alerta"
    return {
        "fornecedor_id": fornecedor_id,
        "preco_esperado": ultima.preco_unitario if usa_ultimo else round(ref, 4),
        "mediana": round(ref, 4),
        "ultimo_preco": ultima.preco_unitario,
        "n_compras": len(par),
        "base": "forte" if len(par) >= config.MIN_PRECOS_REFERENCIA else "fraca",
        "usa_ultimo_preco": usa_ultimo,
    }


def melhor_fornecedor(ctx, servico_id: int, hoje: date) -> dict | None:
    """Fornecedor recomendado: menor preço esperado entre os de base forte; empate → menor lead time."""
    refs = []
    for f in ctx.fornecedores:
        r = referencia_atual(ctx.aquisicoes, servico_id, f.id, hoje)
        if r:
            refs.append({**r, "fornecedor": f.nome, "lead_time_cadastrado": f.lead_time_dias})
    if not refs:
        # nenhuma compra na janela: cai para o último fornecedor que já vendeu este item
        antigas = sorted((a for a in ctx.aquisicoes if a.servico_id == servico_id),
                         key=lambda a: a.data_pedido)
        if not antigas:
            return None
        a = antigas[-1]
        f = ctx.fornecedor(a.fornecedor_id)
        return {"fornecedor_id": f.id, "fornecedor": f.nome, "preco_esperado": a.preco_unitario,
                "mediana": a.preco_unitario, "ultimo_preco": a.preco_unitario, "n_compras": 1,
                "base": "fraca", "usa_ultimo_preco": True, "lead_time_cadastrado": f.lead_time_dias}
    fortes = [r for r in refs if r["base"] == "forte"] or refs
    return min(fortes, key=lambda r: (r["preco_esperado"], r["lead_time_cadastrado"]))


def comparacao_fornecedores(ctx, servico_id: int, hoje: date) -> dict:
    inicio = hoje - timedelta(days=config.JANELA_PRECO_DIAS)
    linhas = []
    for f in ctx.fornecedores:
        r = referencia_atual(ctx.aquisicoes, servico_id, f.id, hoje)
        if not r:
            continue
        compras = [a for a in ctx.aquisicoes if a.servico_id == servico_id
                   and a.fornecedor_id == f.id and inicio <= a.data_pedido <= hoje]
        linhas.append({"fornecedor_id": f.id, "fornecedor": f.nome, "lead_time": f.lead_time_dias,
                       "compras": compras, **r})
    if not linhas:
        return {"linhas": [], "melhor": None}
    fortes = [l for l in linhas if l["base"] == "forte"] or linhas
    melhor = min(fortes, key=lambda l: l["preco_esperado"])
    saida = []
    for l in sorted(linhas, key=lambda l: l["preco_esperado"]):
        dif = (l["preco_esperado"] - melhor["preco_esperado"]) / melhor["preco_esperado"]
        e_o_melhor = l["fornecedor_id"] == melhor["fornecedor_id"]
        extra = 0.0 if e_o_melhor else sum(max(0.0, a.preco_unitario - melhor["preco_esperado"]) * a.quantidade
                                           for a in l["compras"])
        saida.append({
            "fornecedor_id": l["fornecedor_id"], "fornecedor": l["fornecedor"],
            "lead_time": l["lead_time"], "preco_esperado": l["preco_esperado"],
            "mediana": l["mediana"], "ultimo_preco": l["ultimo_preco"],
            "n_compras": l["n_compras"], "base": l["base"],
            "diferenca_para_melhor": round(dif, 6),
            "acima_do_limiar": dif > config.LIMIAR_DIFERENCA_FORNECEDOR,
            "custo_extra_estimado": round(extra, 2),
            "e_o_melhor": e_o_melhor,
        })
    return {"linhas": saida, "melhor": melhor["fornecedor"]}


def evolucao(ctx, servico_id: int, inicio: date, fim: date) -> dict:
    series = []
    for f in ctx.fornecedores:
        compras = [a for a in _compras_do_par(ctx.aquisicoes, servico_id, f.id)
                   if inicio <= a.data_pedido <= fim]
        if not compras:
            continue
        pontos = []
        for a in compras:
            av = avaliar_aquisicao(ctx.aquisicoes, a)
            pontos.append({"data": a.data_pedido.isoformat(), "preco": a.preco_unitario,
                           "quantidade": a.quantidade, "codigo": a.codigo,
                           "nivel": av["nivel"], "motivo": av["motivo"], "rebaixado": av["rebaixado"]})
        precos = [p["preco"] for p in pontos]
        series.append({
            "fornecedor_id": f.id, "fornecedor": f.nome, "pontos": pontos,
            "resumo": {"n": len(precos), "primeiro": precos[0], "ultimo": precos[-1],
                       "variacao": round((precos[-1] - precos[0]) / precos[0], 4),
                       "mediana": round(median(precos), 4), "minimo": min(precos),
                       "maximo": max(precos)},
        })
    return {"inicio": inicio.isoformat(), "fim": fim.isoformat(), "series": series}


def anomalias(ctx, inicio: date, fim: date) -> list[dict]:
    """Toda compra do período que merece nota, alerta, registro de queda — ou que foi rebaixada
    por caber na oscilação do fornecedor (mostrada para o usuário ver que o sistema olhou)."""
    saida = []
    for a in ctx.aquisicoes:
        if not (inicio <= a.data_pedido <= fim):
            continue
        av = avaliar_aquisicao(ctx.aquisicoes, a)
        if av["nivel"] in ("nota", "alerta", "queda") or av["rebaixado"]:
            saida.append({"aquisicao": a.codigo, "data": a.data_pedido.isoformat(),
                          "servico_id": a.servico_id, "servico": ctx.servico(a.servico_id).nome,
                          "fornecedor": ctx.fornecedor(a.fornecedor_id).nome,
                          "preco": a.preco_unitario, **av})
    ordem = {"alerta": 0, "nota": 1, "queda": 2, "normal": 3}
    saida.sort(key=lambda x: x["data"], reverse=True)   # mais recentes primeiro...
    saida.sort(key=lambda x: ordem[x["nivel"]])          # ...dentro de cada nível
    return saida
