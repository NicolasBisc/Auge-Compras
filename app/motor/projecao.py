"""
Decisão 1 — cold start — e a projeção de compra.

Regra central: o sistema nunca inventa um número.
  • Pouco dado (confiança insuficiente) → modo cold start: não extrapola ritmo.
    Usa só FATOS: o estoque mínimo que o usuário declarou e as renovações de
    certificados que já se sabe que vão vencer.
  • Dado suficiente → modo projeção, com fórmula clássica de ponto de reposição
    e o nível de confiança exibido junto de cada sugestão.

Fórmulas (demanda de contagem, aproximação de Poisson):
  ritmo d          = unidades alocadas na janela / dias observados
  estoque segur.   = z × √(d × L)
  ponto reposição  = d × L + estoque de segurança      (nunca abaixo do mínimo declarado)
  alvo             = max(d × (L + H), renovações previstas) + estoque de segurança
  sugestão         = alvo − posição, arredondado para cima
"""
import calendar
from datetime import date, timedelta
from math import ceil, floor, sqrt
from statistics import median

from app import config
from app.motor.capacidade import (capacidade, em_transito, prazo_entrega, recebido_por_aquisicao,
                                   situacao)
from app.motor.formato import brl, num, pct, unidade
from app.motor.precos import melhor_fornecedor, referencia_atual


def somar_meses(d: date, meses: int) -> date:
    ano = d.year + (d.month - 1 + meses) // 12
    mes = (d.month - 1 + meses) % 12 + 1
    return date(ano, mes, min(d.day, calendar.monthrange(ano, mes)[1]))


def nivel_confianca(eventos: int, dias_acompanhamento: int) -> str:
    if dias_acompanhamento < config.MIN_DIAS_ACOMPANHAMENTO or eventos < config.EVENTOS_CONFIANCA["baixa"]:
        return "insuficiente"
    if eventos < config.EVENTOS_CONFIANCA["media"]:
        return "baixa"
    if eventos < config.EVENTOS_CONFIANCA["alta"]:
        return "media"
    return "alta"


def lead_time_efetivo(ctx, fornecedor_id: int, hoje: date) -> tuple[float, str, int]:
    """Lead time depende de quem entrega: mediana observada no fornecedor (todas as suas entregas)."""
    primeira_entrega: dict[int, date] = {}
    for r in ctx.recebimentos:
        if r.data_recebimento <= hoje:
            atual = primeira_entrega.get(r.aquisicao_id)
            primeira_entrega[r.aquisicao_id] = min(atual, r.data_recebimento) if atual else r.data_recebimento
    observados = [(primeira_entrega[a.id] - a.data_pedido).days
                  for a in ctx.aquisicoes if a.fornecedor_id == fornecedor_id and a.id in primeira_entrega]
    if len(observados) >= config.MIN_ENTREGAS_LEAD_TIME:
        return float(median(observados)), "observado", len(observados)
    return float(ctx.fornecedor(fornecedor_id).lead_time_dias), "cadastrado", len(observados)


def renovacoes_previstas(servico, alocacoes, hoje: date, ate: date) -> tuple[float, int]:
    """
    Fato conhecido, não estimativa: a última alocação de cada cliente vence em
    data + validade. Se vence dentro do período, aquele cliente vai precisar de outro.
    Premissa assumida: todo cliente renova (taxa real de renovação fica para depois).
    """
    if not servico.validade_meses:
        return 0.0, 0
    ultima: dict[int, object] = {}
    for a in alocacoes:
        if a.servico_id == servico.id and a.data <= hoje:
            if a.cliente_id not in ultima or a.data > ultima[a.cliente_id].data:
                ultima[a.cliente_id] = a
    vencendo = [a for a in ultima.values() if hoje <= somar_meses(a.data, servico.validade_meses) <= ate]
    return float(sum(a.quantidade for a in vencendo)), len(vencendo)


def _n(v, casas=1):
    return None if v is None else round(v, casas)


def projetar(ctx, servico, hoje: date, horizonte: int | None = None) -> dict:
    H = horizonte or config.HORIZONTE_DIAS
    cap = capacidade(servico.id, ctx.aquisicoes, ctx.recebimentos, ctx.alocacoes, hoje)
    transito, pedidos = em_transito(servico.id, ctx, hoje)
    posicao = cap + transito
    atrasados = [p for p in pedidos if p["situacao"] == "atrasada"]

    alocs = [a for a in ctx.alocacoes if a.servico_id == servico.id and a.data <= hoje]
    datas = [a.data for a in alocs] + [a.data_pedido for a in ctx.aquisicoes
                                       if a.servico_id == servico.id and a.data_pedido <= hoje]
    inicio = min(datas) if datas else None
    dias_acomp = (hoje - inicio).days if inicio else 0
    dias_obs = min(config.JANELA_RITMO_DIAS, dias_acomp)
    corte = hoje - timedelta(days=dias_obs)
    na_janela = [a for a in alocs if a.data > corte]
    eventos = len(na_janela)
    unidades = sum(a.quantidade for a in na_janela)
    ritmo = unidades / dias_obs if dias_obs > 0 else 0.0
    confianca = nivel_confianca(eventos, dias_acomp)
    erro = 1 / sqrt(eventos) if eventos else None

    base = {
        "servico_id": servico.id, "servico": servico.nome, "unidade": servico.unidade,
        "capacidade": cap, "em_transito": transito, "posicao": posicao,
        "pedidos_abertos": pedidos, "pedidos_atrasados": atrasados,
        "eventos_janela": eventos, "unidades_janela": unidades, "dias_observados": dias_obs,
        "dias_acompanhamento": dias_acomp, "ritmo_diario": _n(ritmo, 3),
        "confianca": confianca, "erro_relativo": _n(erro, 2),
        "estoque_minimo": servico.estoque_minimo, "horizonte": H,
    }

    forn = melhor_fornecedor(ctx, servico.id, hoje)
    if forn is None:
        return {**base, "modo": "sem_dados", "status": "sem_regra", "sugestao": 0,
                "resumo": "Nenhuma aquisição registrada: cadastre a primeira compra deste item.",
                "passos": []}

    L, fonte_L, n_L = lead_time_efetivo(ctx, forn["fornecedor_id"], hoje)
    renov, n_renov = renovacoes_previstas(servico, ctx.alocacoes, hoje, hoje + timedelta(days=int(L + H)))

    passos = [
        {"rotulo": "Disponível agora", "valor": num(cap),
         "detalhe": "O que chegou nas notas menos o que já foi entregue a clientes."},
        {"rotulo": "A caminho no prazo", "valor": num(transito),
         "detalhe": ("Pedidos dentro do prazo: " + ", ".join(f"{p['codigo']} (faltam {num(p['falta'])})"
                     for p in pedidos if p["situacao"] != "atrasada")) if transito else
                    "Nenhum pedido aberto dentro do prazo."},
    ]
    if atrasados:
        passos.append({"rotulo": "Pedido fora da conta", "valor": ", ".join(p["codigo"] for p in atrasados),
                       "detalhe": "Pedido atrasado não entra no cálculo: contar com ele esconderia o risco de faltar. "
                                  "Cobre o fornecedor antes de comprar de novo."})
    passos.append({"rotulo": "Disponível + a caminho", "valor": num(posicao), "detalhe": "O que se pode contar para os próximos dias."})

    ss = rop = alvo = cobertura = data_reposicao = None
    if confianca == "insuficiente":
        modo = "cold_start"
        minimo = servico.estoque_minimo
        passos.append({"rotulo": "Histórico", "valor": f"{eventos} entregas em {dias_acomp} dias",
                       "detalhe": f"Abaixo do mínimo para estimar ({config.EVENTOS_CONFIANCA['baixa']} entregas e "
                                  f"{config.MIN_DIAS_ACOMPANHAMENTO} dias). O sistema não chuta um ritmo."})
        passos.append({"rotulo": "Mínimo definido por você", "valor": "não definido" if minimo is None else num(minimo),
                       "detalhe": "Com pouco histórico, o número vem de quem conhece o negócio, não de uma estimativa."})
        if servico.validade_meses:
            passos.append({"rotulo": "Renovações previstas", "valor": num(renov),
                           "detalhe": f"{n_renov} cliente(s) com vencimento nos próximos {int(L + H)} dias."})
        if minimo is None and renov == 0:
            status, sugestao = "sem_regra", 0
            minimo_seguro = origem_minimo = None
            resumo = "Pouco histórico e nenhum mínimo definido: defina um mínimo para este item."
            motivo = resumo
        else:
            alvo = max(minimo or 0, renov)
            sugestao = max(0, ceil(alvo - posicao - 1e-9))
            status = "comprar_agora" if posicao < alvo else "ok"
            minimo_seguro = ceil(alvo - 1e-9)
            origem_minimo = "renovacoes" if renov > (minimo or 0) else "definido"
            falta = max(0, minimo_seguro - posicao)
            motivo = (f"Item com poucos dados: tem {num(posicao)} e precisa ter pelo menos {minimo_seguro}, "
                      f"o mínimo {'definido por você' if origem_minimo == 'definido' else 'das renovações previstas'}. Faltam {num(falta)}.")
            resumo = (f"{motivo} Comprar {sugestao}."
                      if status == "comprar_agora" else
                      f"Item com poucos dados: tem {num(posicao)} e precisa ter pelo menos {minimo_seguro}. Nada a comprar.")
        rop = minimo
    else:
        minimo_seguro = origem_minimo = None
        modo = "projecao"
        dL = ritmo * L
        ss = config.Z_NIVEL_SERVICO * sqrt(dL)
        rop_calc = dL + ss
        rop = max(rop_calc, servico.estoque_minimo or 0)
        # itens contáveis: "comprar se tiver rop ou menos" equivale a "precisa ter pelo menos floor(rop) + 1"
        minimo_seguro = floor(rop) + 1 if servico.tipo_quantidade == "discreta" else round(rop, 1)
        origem_minimo = "definido" if servico.estoque_minimo and servico.estoque_minimo >= rop_calc else "calculado"
        demanda = max(ritmo * (L + H), renov)
        alvo = max(demanda + ss, servico.estoque_minimo or 0)
        sugestao = max(0, ceil(alvo - posicao - 1e-9))
        cobertura = cap / ritmo if ritmo > 0 else None
        if posicao <= rop:
            status, data_reposicao = "comprar_agora", hoje
        else:
            folga = (posicao - rop) / ritmo if ritmo > 0 else None
            data_reposicao = hoje + timedelta(days=floor(folga)) if folga is not None else None
            status = "planejar" if folga is not None and folga <= config.DIAS_ANTECEDENCIA_ATENCAO else "ok"
        passos += [
            {"rotulo": "Ritmo recente", "valor": f"{num(ritmo, 2)} por dia",
             "detalhe": f"{num(unidades)} {unidade(servico.unidade, unidades)} em {dias_obs} dias."},
            {"rotulo": "Confiança", "valor": {"baixa": "baixa", "media": "média", "alta": "alta"}[confianca],
             "detalhe": f"{eventos} entregas a clientes em {dias_obs} dias: margem de erro de cerca de ±{pct(erro, False)} (1/√{eventos})."},
            {"rotulo": "Prazo de entrega", "valor": f"{num(L)} dias",
             "detalhe": (f"Mediana de {n_L} entregas reais de {forn['fornecedor']}." if fonte_L == "observado"
                         else f"Valor cadastrado de {forn['fornecedor']} (só {n_L} entrega(s) observada(s)).")},
            {"rotulo": "Margem de segurança", "valor": num(ss),
             "detalhe": f"{num(config.Z_NIVEL_SERVICO, 2)} × √({num(ritmo, 2)} × {num(L)}): cobre cerca de 95% das variações de consumo."},
            {"rotulo": "Precisa ter pelo menos", "valor": num(minimo_seguro),
             "detalhe": f"Ponto de compra: {num(dL)} de consumo durante o prazo de entrega + {num(ss)} de margem = {num(rop)}"
                        + (f" (nunca abaixo do mínimo de {servico.estoque_minimo} definido por você)" if servico.estoque_minimo else "")
                        + f". Como o item é contado inteiro, é preciso ter {num(minimo_seguro)} ou mais."},
        ]
        if servico.validade_meses:
            passos.append({"rotulo": "Renovações previstas", "valor": num(renov),
                           "detalhe": f"{n_renov} cliente(s) vencendo em {int(L + H)} dias. A demanda usada é o maior "
                                      f"entre o ritmo ({num(ritmo * (L + H))}) e as renovações."})
        passos.append({"rotulo": f"Ideal para {int(L + H)} dias", "valor": num(alvo),
                       "detalhe": "Consumo previsto no prazo de entrega e no período, mais a margem."})
        motivo = None
        if status == "comprar_agora":
            motivo = (f"Tem {num(posicao)} e precisa ter pelo menos {num(minimo_seguro)}, já contando o prazo de entrega. "
                      f"Faltam {num(max(0, minimo_seguro - posicao))}.")
            repor = ceil(max(0, minimo_seguro - posicao))
            resto = sugestao - repor
            resumo = (f"Comprar {sugestao} agora: {repor} para voltar ao mínimo e {resto} para cobrir os próximos {int(L + H)} dias."
                      if resto > 0 else f"Comprar {sugestao} agora para voltar ao mínimo.")
        elif status == "planejar":
            motivo = f"A hora de comprar chega em menos de uma semana, por volta de {data_reposicao:%d/%m}."
            resumo = f"Planejar a compra de {sugestao} até {data_reposicao:%d/%m}."
        elif sugestao > 0 and data_reposicao and data_reposicao <= hoje + timedelta(days=H):
            resumo = f"Sem urgência. Prevista a compra de {sugestao} por volta de {data_reposicao:%d/%m}."
        else:
            resumo = "O disponível cobre o período. Nada a comprar agora."
        if cap <= 0 and transito > 0 and status != "comprar_agora":
            proximo = next(p for p in pedidos if p["situacao"] != "atrasada")
            resumo = (f"Acabou por agora, mas {proximo['codigo']} já está a caminho e cobre o período. "
                      "Comprar mais não faria chegar antes.")

    alternativa = None
    if modo == "projecao" and status == "comprar_agora" and ritmo > 0 and cap / ritmo < L:
        alternativa = _alternativa_rapida(ctx, servico.id, forn, L, hoje)
        if alternativa:
            passos.append({"rotulo": "Alternativa mais rápida", "valor": alternativa["fornecedor"],
                           "detalhe": f"A capacidade dura cerca de {num(cap / ritmo, 0)} dias, menos que os {num(L)} dias de "
                                      f"{forn['fornecedor']}. {alternativa['fornecedor']} entrega em "
                                      f"{num(alternativa['lead_time'])} dias por {pct(alternativa['diferenca'])} "
                                      f"({brl(alternativa['preco'])}). Decisão de negócio: prazo ou preço."})

    preco = forn["preco_esperado"]
    passos.append({"rotulo": "Sugestão", "valor": f"{sugestao}",
                   "detalhe": f"{forn['fornecedor']} a {brl(preco)} cada, cerca de {brl(sugestao * preco)}"
                              + (" (último preço: o fornecedor reajustou há pouco)." if forn["usa_ultimo_preco"] and forn["n_compras"] > 1 else ".")})

    if modo == "cold_start" and status == "ok":
        motivo = resumo
    return {**base, "modo": modo, "status": status, "sugestao": sugestao, "resumo": resumo,
            "motivo": motivo or resumo,
            "lead_time": L, "lead_time_fonte": fonte_L,
            "estoque_seguranca": _n(ss), "ponto_reposicao": _n(rop), "alvo": _n(alvo),
            "renovacoes_previstas": renov, "clientes_renovando": n_renov,
            "cobertura_dias": _n(cobertura, 0),
            "data_reposicao": data_reposicao.isoformat() if data_reposicao else None,
            "fornecedor_sugerido": forn["fornecedor"], "fornecedor_sugerido_id": forn["fornecedor_id"],
            "preco_esperado": preco, "base_preco": forn["base"],
            "usa_ultimo_preco": forn["usa_ultimo_preco"],
            "custo_estimado": round(sugestao * preco, 2), "alternativa_rapida": alternativa,
            "minimo_seguro": minimo_seguro, "origem_minimo": origem_minimo,
            "falta_para_minimo": None if minimo_seguro is None else round(max(0, minimo_seguro - posicao), 1),
            "linha_tempo": linha_do_tempo(ctx, servico, cap, ritmo if modo == "projecao" else 0.0,
                                          rop if modo == "projecao" else None,
                                          posicao, minimo_seguro, hoje),
            "passos": passos}


def _alternativa_rapida(ctx, servico_id: int, forn: dict, L: float, hoje: date) -> dict | None:
    """Outro fornecedor que já vendeu este item e entrega mais rápido que o recomendado."""
    opcoes = []
    for f in ctx.fornecedores:
        if f.id == forn["fornecedor_id"]:
            continue
        ref = referencia_atual(ctx.aquisicoes, servico_id, f.id, hoje)
        if not ref:
            continue
        lt, _, _ = lead_time_efetivo(ctx, f.id, hoje)
        if lt < L:
            opcoes.append({"fornecedor": f.nome, "fornecedor_id": f.id, "lead_time": lt,
                           "preco": ref["preco_esperado"],
                           "diferenca": round((ref["preco_esperado"] - forn["preco_esperado"]) / forn["preco_esperado"], 6)})
    return min(opcoes, key=lambda o: (o["lead_time"], o["preco"])) if opcoes else None


def linha_do_tempo(ctx, servico, cap: float, ritmo: float, rop, posicao: float, minimo_seguro, hoje: date,
                   dias: int = 30) -> dict:
    """
    Os próximos 30 dias de um item, sem nenhuma compra nova:
      chegadas   pedidos no prazo, no dia previsto (pedido + prazo real do fornecedor)
      acaba_em   dia em que o disponível chega a zero (None se não acaba no período ou sem ritmo)
      comprar_em dia em que o que tem (disponível + a caminho) cai abaixo do necessário
    """
    recebido = recebido_por_aquisicao(ctx.recebimentos, hoje)
    chegadas = []
    for aq in ctx.aquisicoes:
        if aq.servico_id != servico.id or aq.data_pedido > hoje:
            continue
        f = ctx.fornecedor(aq.fornecedor_id)
        rec = recebido.get(aq.id, 0)
        if situacao(aq, f, rec, hoje, servico.tipo_quantidade) not in ("aguardando", "parcial"):
            continue
        lt, _, _ = lead_time_efetivo(ctx, f.id, hoje)
        prevista = min(max(aq.data_pedido + timedelta(days=round(lt)), hoje), prazo_entrega(aq, f))
        chegadas.append({"dia": (prevista - hoje).days, "quantidade": aq.quantidade - rec,
                         "codigo": aq.codigo, "fornecedor": f.nome, "data": prevista.isoformat()})
    chegadas.sort(key=lambda c: c["dia"])

    acaba_em = None
    if ritmo > 0:
        estoque, t0 = cap, 0.0
        for marco in chegadas + [{"dia": dias, "quantidade": 0}]:
            t1 = min(marco["dia"], dias)
            if estoque - ritmo * (t1 - t0) <= 0:
                acaba_em = round(t0 + estoque / ritmo, 1)
                break
            estoque -= ritmo * (t1 - t0)
            t0 = t1
            estoque += marco["quantidade"]
    elif cap <= 0 and posicao <= 0:
        acaba_em = 0.0

    comprar_em = None
    if minimo_seguro is not None:
        if posicao < minimo_seguro:
            comprar_em = 0.0
        elif rop is not None and ritmo > 0:
            dia = (posicao - rop) / ritmo
            comprar_em = round(dia, 1) if dia <= dias else None
    volta_em = None
    if acaba_em is not None:
        volta_em = next((c["dia"] for c in chegadas if c["dia"] > acaba_em), None)
    return {"dias": dias, "chegadas": chegadas, "acaba_em": acaba_em, "volta_em": volta_em, "comprar_em": comprar_em}
