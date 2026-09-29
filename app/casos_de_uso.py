"""
Casos de uso: a ponte entre banco, motor e interface.

A API e o script de demonstração chamam as MESMAS funções daqui — por isso a
demo publicada mostra exatamente o que o sistema calcula, sem lógica duplicada.
"""
from datetime import date, timedelta

from app import config, db
from app.motor import capacidade as cap
from app.motor import conciliacao, precos, projecao
from app.motor.formato import brl, num, pct, unidade


class ErroDeRegra(Exception):
    """Entrada recusada por uma regra de negócio; a mensagem vai direto para a tela."""


def _brl(v):
    return conciliacao.brl(v)


# ---------------------------------------------------------------------------
# Leituras
# ---------------------------------------------------------------------------
def catalogos(ctx) -> dict:
    return {
        "servicos": [s.__dict__ for s in ctx.servicos],
        "fornecedores": [f.__dict__ for f in ctx.fornecedores],
        "clientes": [c.__dict__ for c in ctx.clientes],
    }


def aquisicoes(ctx, hoje: date, limite: int = 60) -> list[dict]:
    recebido = cap.recebido_por_aquisicao(ctx.recebimentos, hoje)
    saida = []
    for a in sorted(ctx.aquisicoes, key=lambda a: (a.data_pedido, a.id), reverse=True)[:limite]:
        f, s = ctx.fornecedor(a.fornecedor_id), ctx.servico(a.servico_id)
        rec = recebido.get(a.id, 0)
        aval = precos.avaliar_aquisicao(ctx.aquisicoes, a)
        saida.append({
            "id": a.id, "codigo": a.codigo, "data_pedido": a.data_pedido.isoformat(),
            "servico": s.nome, "fornecedor": f.nome, "quantidade": a.quantidade,
            "preco_unitario": a.preco_unitario, "total": round(a.quantidade * a.preco_unitario, 2),
            "recebido": rec, "situacao": cap.situacao(a, f, rec, hoje, s.tipo_quantidade),
            "prazo": cap.prazo_entrega(a, f).isoformat(), "nivel_preco": aval["nivel"],
        })
    return saida


def alocacoes(ctx, limite: int = 40) -> list[dict]:
    nomes = {c.id: c.nome for c in ctx.clientes}
    return [{"id": a.id, "data": a.data.isoformat(), "servico": ctx.servico(a.servico_id).nome,
             "cliente": nomes.get(a.cliente_id, "?"), "quantidade": a.quantidade}
            for a in sorted(ctx.alocacoes, key=lambda a: (a.data, a.id), reverse=True)[:limite]]


def projecoes(ctx, hoje: date, horizonte: int | None = None) -> list[dict]:
    ordem = {"comprar_agora": 0, "planejar": 1, "sem_regra": 2, "ok": 3}
    itens = [projecao.projetar(ctx, s, hoje, horizonte) for s in ctx.servicos]
    return sorted(itens, key=lambda p: (ordem.get(p["status"], 9), p["servico"]))


def evolucao_precos(ctx, servico_id: int, dias: int, hoje: date) -> dict:
    return {**precos.evolucao(ctx, servico_id, hoje - timedelta(days=dias), hoje),
            "comparacao": precos.comparacao_fornecedores(ctx, servico_id, hoje),
            "servico": ctx.servico(servico_id).nome}


def anomalias(ctx, dias: int, hoje: date) -> list[dict]:
    return precos.anomalias(ctx, hoje - timedelta(days=dias), hoje)


def painel(ctx, hoje: date) -> dict:
    """A fila de decisões: o que pede ação hoje, em ordem de prioridade."""
    fila = []
    projs = projecoes(ctx, hoje)
    for p in projs:
        if p["status"] in ("comprar_agora", "planejar"):
            alt = p.get("alternativa_rapida")
            extra = (f" Mais rápido: {alt['fornecedor']} entrega em {num(alt['lead_time'])} dias, "
                     f"por {pct(alt['diferenca'])}." if alt else "")
            verbo = "Comprar" if p["status"] == "comprar_agora" else "Planejar"
            fila.append({"prioridade": 1 if verbo == "Comprar" else 2, "tipo": "compra", "tela": "projecao",
                         "ref": p["servico_id"],
                         "titulo": f"{verbo} {p['sugestao']} {unidade(p['unidade'], p['sugestao'])} de {p['servico']}",
                         "valor": p["custo_estimado"], "fornecedor": p["fornecedor_sugerido"],
                         "servico": p["servico"], "servico_id": p["servico_id"],
                         "fornecedor_id": p["fornecedor_sugerido_id"], "quantidade": p["sugestao"],
                         "preco": p["preco_esperado"], "detalhe": f"{p['motivo']}{extra}",
                         "numeros": [{"rotulo": "Tem", "valor": num(p["posicao"])},
                                     {"rotulo": "Precisa ter", "valor": num(p["minimo_seguro"]) if p.get("minimo_seguro") is not None else "—"},
                                     {"rotulo": "Comprar", "valor": num(p["sugestao"])}]})
        elif p["status"] == "sem_regra":
            fila.append({"prioridade": 3, "tipo": "regra", "tela": "cadastros", "ref": p["servico_id"],
                         "servico": p["servico"], "numeros": [{"rotulo": "Tem", "valor": num(p["posicao"])},
                                                              {"rotulo": "Mínimo", "valor": "não definido"}],
                         "titulo": f"Definir estoque mínimo de {p['servico']}", "detalhe": p["resumo"]})
        for atr in p["pedidos_atrasados"]:
            aq = next(a for a in ctx.aquisicoes if a.codigo == atr["codigo"])
            prazo = cap.prazo_entrega(aq, ctx.fornecedor(aq.fornecedor_id))
            fila.append({"prioridade": 1, "tipo": "entrega", "tela": "aquisicoes", "ref": atr["codigo"],
                         "servico": p["servico"], "fornecedor": ctx.fornecedor(aq.fornecedor_id).nome,
                         "titulo": f"Pedido {atr['codigo']} atrasado",
                         "numeros": [{"rotulo": "Não chegaram", "valor": num(atr["falta"])},
                                     {"rotulo": "Prazo era", "valor": f"{prazo:%d/%m}"},
                                     {"rotulo": "Pedido em", "valor": f"{aq.data_pedido:%d/%m}"}],
                         "detalhe": f"{num(atr['falta'])} {unidade(p['unidade'], atr['falta'])} de {p['servico']} ainda não chegaram. "
                                    "Cobre o fornecedor antes de comprar de novo."})
    for a in anomalias(ctx, 30, hoje):
        if a["nivel"] == "alerta":
            fila.append({"prioridade": 1, "tipo": "preco", "tela": "precos", "ref": a["servico_id"],
                         "servico": a["servico"], "fornecedor": a["fornecedor"],
                         "numeros": [{"rotulo": "Habitual", "valor": brl(a["referencia"])},
                                     {"rotulo": "Cobrado", "valor": brl(a["preco"])},
                                     {"rotulo": "Variação", "valor": pct(a["variacao"])}],
                         "titulo": f"{a['fornecedor']} subiu o preço de {a['servico']}", "detalhe": a["motivo"]})
        elif a["nivel"] == "nota":
            fila.append({"prioridade": 3, "tipo": "preco", "tela": "precos", "ref": a["servico_id"],
                         "servico": a["servico"], "fornecedor": a["fornecedor"],
                         "numeros": [{"rotulo": "Habitual", "valor": brl(a["referencia"])},
                                     {"rotulo": "Cobrado", "valor": brl(a["preco"])},
                                     {"rotulo": "Variação", "valor": pct(a["variacao"])}],
                         "titulo": f"Reajuste de {a['fornecedor']} em {a['servico']}", "detalhe": a["motivo"]})
    for s in ctx.servicos:
        comp = precos.comparacao_fornecedores(ctx, s.id, hoje)
        for l in comp["linhas"]:
            if l["acima_do_limiar"] and l["custo_extra_estimado"] > 0:
                fila.append({"prioridade": 3, "tipo": "fornecedor", "tela": "precos", "ref": s.id,
                             "servico": s.nome, "fornecedor": l["fornecedor"],
                             "numeros": [{"rotulo": "Acima do mais barato", "valor": pct(l["diferenca_para_melhor"])},
                                         {"rotulo": "Pago a mais em 6 meses", "valor": brl(l["custo_extra_estimado"])}],
                             "titulo": f"{l['fornecedor']} está {pct(l['diferenca_para_melhor'], False)} acima em {s.nome}",
                             "detalhe": f"Comprar dele custou cerca de {_brl(l['custo_extra_estimado'])} a mais em "
                                        f"{config.JANELA_PRECO_DIAS} dias, comparado a {comp['melhor']}."})
    for sit in aquisicoes(ctx, hoje, limite=500):
        if sit["situacao"] in ("excedente", "faltante"):
            fila.append({"prioridade": 1, "tipo": "entrega", "tela": "aquisicoes", "ref": sit["codigo"],
                         "servico": sit["servico"], "fornecedor": sit["fornecedor"],
                         "titulo": f"Pedido {sit['codigo']}: {'excesso' if sit['situacao'] == 'excedente' else 'faltante'}",
                         "detalhe": f"Recebido {sit['recebido']:g} de {sit['quantidade']:g} ({sit['servico']})."})
    fila.sort(key=lambda x: x["prioridade"])

    total_transito = sum(p["em_transito"] * p["preco_esperado"] for p in projs if p.get("preco_esperado"))
    return {
        "hoje": hoje.isoformat(),
        "fila": fila,
        "resumo": {
            "decisoes_urgentes": sum(1 for f in fila if f["prioridade"] == 1),
            "itens_a_comprar": sum(1 for p in projs if p["status"] == "comprar_agora"),
            "itens_em_cold_start": sum(1 for p in projs if p["modo"] == "cold_start"),
            "valor_em_transito": round(total_transito, 2),
            "compra_sugerida_total": round(sum(p.get("custo_estimado", 0) for p in projs
                                               if p["status"] in ("comprar_agora", "planejar")), 2),
        },
        "capacidades": [{"servico_id": p["servico_id"], "servico": p["servico"], "capacidade": p["capacidade"],
                         "em_transito": p["em_transito"], "posicao": p["posicao"], "ponto_reposicao": p.get("ponto_reposicao"),
                         "minimo_seguro": p.get("minimo_seguro"), "origem_minimo": p.get("origem_minimo"),
                         "falta_para_minimo": p.get("falta_para_minimo"), "linha_tempo": p.get("linha_tempo"),
                         "ritmo_diario": p["ritmo_diario"], "sugestao": p["sugestao"],
                         "fornecedor_sugerido": p.get("fornecedor_sugerido"), "custo_estimado": p.get("custo_estimado"),
                         "status": p["status"], "modo": p["modo"], "unidade": p["unidade"]} for p in projs],
    }


# ---------------------------------------------------------------------------
# Conciliação
# ---------------------------------------------------------------------------
def previsualizar_nota(ctx, conteudo: bytes, hoje: date) -> dict:
    try:
        nota = conciliacao.ler_nota(conteudo)
    except conciliacao.NotaInvalida as e:
        return {"status": "rejeitada", "rejeitada": True, "motivo": str(e), "itens": []}
    return conciliacao.conciliar(ctx, nota, hoje)


def importar_nota(conn, conteudo: bytes, hoje: date) -> dict:
    ctx = db.carregar_contexto(conn)
    resultado = previsualizar_nota(ctx, conteudo, hoje)
    if resultado["rejeitada"]:
        raise ErroDeRegra(resultado["motivo"])
    nota = conciliacao.ler_nota(conteudo)
    nid = db.gravar_nota(conn, nota, resultado, hoje, conteudo.decode("utf-8", errors="replace"))
    return {**resultado, "nota_id": nid,
            "nao_importados": [i["n"] for i in resultado["itens"] if not i["importavel"]]}


# ---------------------------------------------------------------------------
# Cadastros (com as validações que evitam dado ruim na origem)
# ---------------------------------------------------------------------------
def registrar_aquisicao(conn, servico_id: int, fornecedor_id: int, quantidade: float,
                        preco_unitario: float, data_pedido: date, hoje: date) -> dict:
    ctx = db.carregar_contexto(conn)
    if not any(s.id == servico_id for s in ctx.servicos):
        raise ErroDeRegra("Item não encontrado.")
    if not any(f.id == fornecedor_id for f in ctx.fornecedores):
        raise ErroDeRegra("Fornecedor não encontrado.")
    if quantidade <= 0 or preco_unitario <= 0:
        raise ErroDeRegra("Quantidade e preço precisam ser maiores que zero.")
    if data_pedido > hoje:
        raise ErroDeRegra("A data do pedido não pode estar no futuro.")
    s = ctx.servico(servico_id)
    if s.tipo_quantidade == "discreta" and quantidade != int(quantidade):
        raise ErroDeRegra(f"{s.nome} é contado em unidades inteiras.")
    codigo = db.proximo_codigo_aquisicao(conn, data_pedido.year)
    aid = db.inserir(conn, "aquisicao", codigo=codigo, servico_id=servico_id, fornecedor_id=fornecedor_id,
                     quantidade=quantidade, preco_unitario=round(preco_unitario, 2),
                     data_pedido=data_pedido.isoformat())
    conn.commit()
    ctx = db.carregar_contexto(conn)
    aq = next(a for a in ctx.aquisicoes if a.id == aid)
    return {"id": aid, "codigo": codigo, "avaliacao_preco": precos.avaliar_aquisicao(ctx.aquisicoes, aq)}


def registrar_alocacao(conn, servico_id: int, cliente_id: int, quantidade: float, data: date, hoje: date) -> dict:
    ctx = db.carregar_contexto(conn)
    if not any(c.id == cliente_id for c in ctx.clientes):
        raise ErroDeRegra("Cliente não encontrado.")
    if not any(s.id == servico_id for s in ctx.servicos):
        raise ErroDeRegra("Item não encontrado.")
    if quantidade <= 0:
        raise ErroDeRegra("Quantidade precisa ser maior que zero.")
    if data > hoje:
        raise ErroDeRegra("A data não pode estar no futuro.")
    disponivel = cap.capacidade(servico_id, ctx.aquisicoes, ctx.recebimentos, ctx.alocacoes, data)
    if quantidade > disponivel + 1e-9:
        raise ErroDeRegra(f"Capacidade insuficiente: há {disponivel:g} disponível(is) em {data:%d/%m/%Y}. "
                          "Registre o recebimento da nota antes de alocar.")
    aid = db.inserir(conn, "alocacao", servico_id=servico_id, cliente_id=cliente_id,
                     quantidade=quantidade, data=data.isoformat())
    conn.commit()
    return {"id": aid, "capacidade_restante": disponivel - quantidade}


def registrar_servico(conn, nome, categoria, unidade, tipo_quantidade, validade_meses, estoque_minimo) -> dict:
    if tipo_quantidade not in ("discreta", "continua"):
        raise ErroDeRegra("Tipo de quantidade inválido.")
    if not nome.strip():
        raise ErroDeRegra("Informe o nome do item.")
    try:
        sid = db.inserir(conn, "servico", nome=nome.strip(), categoria=categoria.strip() or "Geral",
                         unidade=unidade.strip() or "unidade", tipo_quantidade=tipo_quantidade,
                         validade_meses=validade_meses or None, estoque_minimo=estoque_minimo)
    except Exception:
        raise ErroDeRegra("Já existe um item com esse nome.")
    conn.commit()
    return {"id": sid}


def definir_estoque_minimo(conn, servico_id: int, estoque_minimo: int | None) -> dict:
    if estoque_minimo is not None and estoque_minimo < 0:
        raise ErroDeRegra("O estoque mínimo não pode ser negativo.")
    conn.execute("UPDATE servico SET estoque_minimo = ? WHERE id = ?", (estoque_minimo, servico_id))
    conn.commit()
    return {"id": servico_id, "estoque_minimo": estoque_minimo}


def registrar_fornecedor(conn, nome, cnpj, lead_time_dias) -> dict:
    digitos = conciliacao.so_digitos(cnpj)
    if len(digitos) != 14:
        raise ErroDeRegra("CNPJ precisa ter 14 dígitos.")
    if lead_time_dias < 0:
        raise ErroDeRegra("Lead time não pode ser negativo.")
    try:
        fid = db.inserir(conn, "fornecedor", nome=nome.strip(), cnpj=digitos, lead_time_dias=lead_time_dias)
    except Exception:
        raise ErroDeRegra("Já existe um fornecedor com esse nome ou CNPJ.")
    conn.commit()
    return {"id": fid}


def registrar_cliente(conn, nome, segmento) -> dict:
    try:
        cid = db.inserir(conn, "cliente", nome=nome.strip(), segmento=segmento.strip() or "Geral")
    except Exception:
        raise ErroDeRegra("Já existe um cliente com esse nome.")
    conn.commit()
    return {"id": cid}


def encerrar_aquisicao(conn, codigo: str) -> dict:
    cur = conn.execute("UPDATE aquisicao SET encerrada = 1 WHERE codigo = ?", (codigo,))
    conn.commit()
    if not cur.rowcount:
        raise ErroDeRegra("Aquisição não encontrada.")
    return {"codigo": codigo, "encerrada": True}
