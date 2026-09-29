"""Fase 1: capacidade vem do que CHEGOU, nunca do que foi pedido."""
from app.motor.capacidade import capacidade, em_transito, prazo_entrega, situacao
from tests.conftest import HOJE


def test_capacidade_soma_notas_e_nao_pedidos(m):
    m.compra(10, 90, dias_atras=20, recebe_em=18)      # chegou
    m.compra(50, 90, dias_atras=1)                     # pedido, ainda não chegou
    m.alocar(3, dias_atras=5)
    ctx = m.ctx()
    assert capacidade(1, ctx.aquisicoes, ctx.recebimentos, ctx.alocacoes, HOJE) == 7


def test_entrega_parcial_em_duas_notas_soma_na_mesma_aquisicao(m):
    a = m.compra(10, 90, dias_atras=20, recebe_em=18, recebe_qtd=6)
    m.receber(a.id, 4, 90, dias_atras=15)
    ctx = m.ctx()
    assert capacidade(1, ctx.aquisicoes, ctx.recebimentos, ctx.alocacoes, HOJE) == 10
    assert situacao(a, ctx.fornecedor(1), 10, HOJE) == "recebida"


def test_prazo_usa_o_maior_entre_fator_e_folga_minima():
    from app.motor.dominio import Aquisicao, Fornecedor
    a = Aquisicao(1, "X", 1, 1, 10, 1, HOJE)
    assert (prazo_entrega(a, Fornecedor(1, "f", "0", 2)) - HOJE).days == 5     # 2 + 3 > 1,5 × 2
    assert (prazo_entrega(a, Fornecedor(1, "f", "0", 12)) - HOJE).days == 18   # 1,5 × 12 > 12 + 3


def test_situacoes_do_pedido(m):
    f = m.ctx().fornecedor(1)  # lead 2 → prazo 5 dias
    dentro = m.compra(10, 1, dias_atras=2)
    fora = m.compra(10, 1, dias_atras=10)
    assert situacao(dentro, f, 0, HOJE) == "aguardando"
    assert situacao(dentro, f, 4, HOJE) == "parcial"
    assert situacao(fora, f, 0, HOJE) == "atrasada"
    assert situacao(fora, f, 4, HOJE) == "faltante"
    assert situacao(dentro, f, 11, HOJE) == "excedente"


def test_pedido_encerrado_com_falta_vira_faltante_mesmo_no_prazo(m):
    a = m.compra(10, 1, dias_atras=1, encerrada=True)
    assert situacao(a, m.ctx().fornecedor(1), 8, HOJE) == "faltante"


def test_quantidade_continua_aceita_dois_por_cento(m):
    a = m.compra(100, 1, dias_atras=1)
    f = m.ctx().fornecedor(1)
    assert situacao(a, f, 98.5, HOJE, "continua") == "recebida"
    assert situacao(a, f, 97.0, HOJE, "continua") == "parcial"
    assert situacao(a, f, 98.5, HOJE, "discreta") == "parcial"


def test_transito_ignora_pedido_atrasado(m):
    m.compra(10, 1, dias_atras=2)    # dentro do prazo → conta
    m.compra(7, 1, dias_atras=30)    # atrasado → não conta
    total, detalhes = em_transito(1, m.ctx(), HOJE)
    assert total == 10
    assert {d["situacao"] for d in detalhes} == {"aguardando", "atrasada"}
