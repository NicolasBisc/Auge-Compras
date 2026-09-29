"""
Capacidade disponível (o "estoque" da Auge) e situação das aquisições.

Decisão da Fase 1, com a correção do Nicolas:
    capacidade = soma do que CHEGOU (notas) − soma do que foi ALOCADO
Nunca soma do que foi pedido: pedido que não chegou não pode ser entregue a cliente.

Posição = capacidade + o que está em trânsito DENTRO do prazo. Pedido atrasado
não entra na posição: contar com ele esconderia o risco de faltar.
"""
from datetime import date, timedelta

from app import config
from app.motor.dominio import Aquisicao, Fornecedor


def recebido_por_aquisicao(recebimentos, ate: date | None = None) -> dict[int, float]:
    total: dict[int, float] = {}
    for r in recebimentos:
        if ate is None or r.data_recebimento <= ate:
            total[r.aquisicao_id] = total.get(r.aquisicao_id, 0) + r.quantidade
    return total


def capacidade(servico_id: int, aquisicoes, recebimentos, alocacoes, ate: date) -> float:
    ids = {a.id for a in aquisicoes if a.servico_id == servico_id}
    entrou = sum(r.quantidade for r in recebimentos
                 if r.aquisicao_id in ids and r.data_recebimento <= ate)
    saiu = sum(a.quantidade for a in alocacoes if a.servico_id == servico_id and a.data <= ate)
    return round(entrou - saiu, 4)


def prazo_entrega(aq: Aquisicao, fornecedor: Fornecedor) -> date:
    lt = fornecedor.lead_time_dias
    folga = max(round(lt * config.FATOR_FOLGA_ENTREGA), lt + config.FOLGA_MINIMA_ENTREGA_DIAS)
    return aq.data_pedido + timedelta(days=folga)


def _bate(recebido: float, pedido: float, tipo_quantidade: str) -> int:
    """-1 = veio menos, 0 = bate, 1 = veio mais (com tolerância só para contínuos)."""
    tol = pedido * config.TOLERANCIA_QTD_CONTINUA if tipo_quantidade == "continua" else 0
    if recebido > pedido + tol + 1e-9:
        return 1
    if recebido < pedido - tol - 1e-9:
        return -1
    return 0


def situacao(aq: Aquisicao, fornecedor: Fornecedor, recebido: float, hoje: date,
             tipo_quantidade: str = "discreta") -> str:
    """
    aguardando  nada chegou, dentro do prazo
    parcial     chegou parte, dentro do prazo
    recebida    chegou tudo
    excedente   chegou mais do que o pedido
    atrasada    nada chegou e o prazo passou
    faltante    chegou parte e o prazo passou (ou o pedido foi encerrado)
    """
    comp = _bate(recebido, aq.quantidade, tipo_quantidade)
    if comp == 1:
        return "excedente"
    if comp == 0:
        return "recebida"
    if aq.encerrada:
        return "faltante"
    dentro = hoje <= prazo_entrega(aq, fornecedor)
    if recebido <= 0:
        return "aguardando" if dentro else "atrasada"
    return "parcial" if dentro else "faltante"


def em_transito(servico_id: int, ctx, hoje: date) -> tuple[float, list[dict]]:
    """Quantidade pedida e ainda não recebida, só de pedidos dentro do prazo."""
    recebido = recebido_por_aquisicao(ctx.recebimentos, hoje)
    servico = ctx.servico(servico_id)
    total, detalhes = 0.0, []
    for aq in ctx.aquisicoes:
        if aq.servico_id != servico_id or aq.data_pedido > hoje:
            continue
        rec = recebido.get(aq.id, 0)
        sit = situacao(aq, ctx.fornecedor(aq.fornecedor_id), rec, hoje, servico.tipo_quantidade)
        if sit in ("aguardando", "parcial"):
            falta = aq.quantidade - rec
            total += falta
            detalhes.append({"codigo": aq.codigo, "falta": falta, "situacao": sit})
        elif sit == "atrasada":
            detalhes.append({"codigo": aq.codigo, "falta": aq.quantidade - rec, "situacao": sit})
    return round(total, 4), detalhes
