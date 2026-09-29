"""Decisão 1 — cold start — e a projeção de compra."""
from math import ceil, sqrt

import pytest

from app import config
from app.motor.projecao import lead_time_efetivo, nivel_confianca, projetar, renovacoes_previstas
from tests.conftest import HOJE


@pytest.mark.parametrize("eventos,dias,esperado", [
    (3, 200, "insuficiente"),   # poucos eventos
    (50, 20, "insuficiente"),   # pouco tempo acompanhando
    (4, 30, "baixa"), (15, 90, "baixa"),
    (16, 90, "media"), (35, 90, "media"),
    (36, 90, "alta"),
])
def test_niveis_de_confianca(eventos, dias, esperado):
    assert nivel_confianca(eventos, dias) == esperado


def test_cold_start_sem_minimo_nao_inventa_numero(m):
    sid = m.servico(nome="Novo", validade_meses=None)
    m.compra(5, 100, dias_atras=10, servico=sid, recebe_em=8)
    m.alocar(1, dias_atras=5, servico=sid)
    p = projetar(m.ctx(), m.ctx().servico(sid), HOJE)
    assert p["modo"] == "cold_start"
    assert p["status"] == "sem_regra"
    assert p["sugestao"] == 0


def test_cold_start_usa_o_minimo_declarado(m):
    sid = m.servico(nome="Novo", estoque_minimo=5)
    m.compra(4, 100, dias_atras=10, servico=sid, recebe_em=8)
    m.alocar(1, dias_atras=5, servico=sid)
    p = projetar(m.ctx(), m.ctx().servico(sid), HOJE)
    assert (p["modo"], p["status"], p["sugestao"]) == ("cold_start", "comprar_agora", 2)  # 5 − 3


def test_cold_start_usa_renovacoes_conhecidas_como_fato(m):
    # item antigo em outro sistema: 6 clientes com certificado vencendo em ~6 dias
    m.compra(10, 100, dias_atras=400, recebe_em=398)
    for cli in range(1, 7):
        m.alocar(1, dias_atras=359, cliente=cli)
    p = projetar(m.ctx(), m.ctx().servico(1), HOJE)
    assert p["modo"] == "cold_start"         # nenhuma alocação na janela de 90 dias
    assert p["renovacoes_previstas"] == 6
    assert p["sugestao"] == 6 - 4            # posição 4, piso = 6 renovações


def _ritmo_meio_por_dia(m, comprado):
    """45 alocações de 1 unidade nos últimos 90 dias → ritmo 0,5/dia, confiança alta."""
    m.compra(comprado, 90, dias_atras=95, recebe_em=94)
    for d in range(1, 90, 2):
        m.alocar(1, dias_atras=d, cliente=d)


def test_formula_do_ponto_de_reposicao(m):
    _ritmo_meio_por_dia(m, comprado=46)      # capacidade final = 1
    p = projetar(m.ctx(), m.ctx().servico(1), HOJE)
    L, d, z, H = 2, 0.5, config.Z_NIVEL_SERVICO, config.HORIZONTE_DIAS
    ss = z * sqrt(d * L)
    assert p["confianca"] == "alta" and p["ritmo_diario"] == 0.5
    assert p["lead_time_fonte"] == "cadastrado"
    assert p["estoque_seguranca"] == round(ss, 1)
    assert p["ponto_reposicao"] == round(d * L + ss, 1)
    assert p["status"] == "comprar_agora"
    assert p["sugestao"] == ceil(d * (L + H) + ss - 1)


def test_posicao_confortavel_nao_sugere_nada(m):
    _ritmo_meio_por_dia(m, comprado=100)     # capacidade final = 55
    p = projetar(m.ctx(), m.ctx().servico(1), HOJE)
    assert (p["status"], p["sugestao"]) == ("ok", 0)


def test_estoque_minimo_e_piso_do_ponto_de_reposicao(m):
    sid = m.servico(nome="Com piso", estoque_minimo=20)
    m.compra(60, 90, dias_atras=95, servico=sid, recebe_em=94)
    for d in range(1, 90, 2):
        m.alocar(1, dias_atras=d, servico=sid, cliente=d)       # capacidade 15
    p = projetar(m.ctx(), m.ctx().servico(sid), HOJE)
    assert p["ponto_reposicao"] == 20
    assert p["status"] == "comprar_agora"


def test_pedido_atrasado_nao_entra_na_posicao(m):
    _ritmo_meio_por_dia(m, comprado=46)
    m.compra(30, 90, dias_atras=20)          # lead 2 → prazo 5 dias: está atrasado
    p = projetar(m.ctx(), m.ctx().servico(1), HOJE)
    assert p["em_transito"] == 0
    assert p["status"] == "comprar_agora"
    assert p["pedidos_atrasados"][0]["falta"] == 30


def test_pedido_no_prazo_entra_na_posicao(m):
    _ritmo_meio_por_dia(m, comprado=46)
    m.compra(30, 90, dias_atras=1)
    p = projetar(m.ctx(), m.ctx().servico(1), HOJE)
    assert p["em_transito"] == 30 and p["posicao"] == 31
    assert p["status"] == "ok"


def test_lead_time_observado_substitui_o_cadastrado_depois_de_tres_entregas(m):
    for atras in (100, 70, 40):
        m.compra(5, 90, dias_atras=atras, recebe_em=atras - 6)   # entregou em 6 dias, cadastro diz 2
    assert lead_time_efetivo(m.ctx(), 1, HOJE) == (6.0, "observado", 3)
    m2 = type(m)()
    m2.compra(5, 90, dias_atras=100, recebe_em=94)
    assert lead_time_efetivo(m2.ctx(), 1, HOJE)[1] == "cadastrado"


def test_renovacao_ja_feita_nao_conta_de_novo(m):
    m.alocar(1, dias_atras=360, cliente=7)
    m.alocar(1, dias_atras=10, cliente=7)    # o cliente já renovou
    m.alocar(1, dias_atras=360, cliente=8)
    total, clientes = renovacoes_previstas(m.ctx().servico(1), m.ctx().alocacoes, HOJE,
                                           HOJE.replace(day=28).replace(month=10))
    assert (total, clientes) == (1, 1)


def test_alternativa_rapida_quando_capacidade_acaba_antes_do_lead_time(m):
    # fornecedor 1 (mais barato) passa a demorar 20 dias; fornecedor 2 entrega em 10
    for atras in (140, 110, 100):
        m.compra(20, 80, dias_atras=atras, recebe_em=atras - 20, fornecedor=1)
    for atras in (130, 120, 105):
        m.compra(2, 95, dias_atras=atras, recebe_em=atras - 10, fornecedor=2)
    for d in range(1, 90, 2):
        m.alocar(1, dias_atras=d, cliente=d)
    for d in range(92, 102):
        m.alocar(2, dias_atras=d, cliente=100 + d)   # consome o excedente antigo: capacidade final 1
    p = projetar(m.ctx(), m.ctx().servico(1), HOJE)
    assert p["fornecedor_sugerido"] == "Fornecedor A"
    assert p["status"] == "comprar_agora"
    assert p["alternativa_rapida"]["fornecedor"] == "Fornecedor B"
    assert p["alternativa_rapida"]["lead_time"] < p["lead_time"]


# --- "precisa ter pelo menos": um único número inteiro e explícito --------------------
def test_minimo_seguro_e_inteiro_e_equivale_ao_ponto_de_compra(m):
    _ritmo_meio_por_dia(m, comprado=46)          # ponto de compra 2,65
    p = projetar(m.ctx(), m.ctx().servico(1), HOJE)
    assert p["minimo_seguro"] == 3               # ter 2 ou menos exige compra → precisa ter 3
    assert p["origem_minimo"] == "calculado"
    assert p["falta_para_minimo"] == 2           # tem 1


def test_minimo_seguro_no_cold_start_vem_do_usuario(m):
    sid = m.servico(nome="Novo", estoque_minimo=5)
    m.compra(4, 100, dias_atras=10, servico=sid, recebe_em=8)
    m.alocar(1, dias_atras=5, servico=sid)
    p = projetar(m.ctx(), m.ctx().servico(sid), HOJE)
    assert (p["minimo_seguro"], p["origem_minimo"], p["falta_para_minimo"]) == (5, "definido", 2)


def test_linha_do_tempo_mostra_quando_acaba_e_quando_chega(m):
    _ritmo_meio_por_dia(m, comprado=46)          # 1 disponível, consome 0,5 por dia
    m.compra(10, 90, dias_atras=1)               # a caminho, fornecedor entrega em 2 dias
    lt = projetar(m.ctx(), m.ctx().servico(1), HOJE)["linha_tempo"]
    assert lt["chegadas"][0]["dia"] == 1 and lt["chegadas"][0]["quantidade"] == 10
    # 1 hoje, +10 no dia 1, consumo 0,5/dia: 0,5 + 10 = 10,5 duram mais 21 dias → acaba no dia 22
    assert lt["acaba_em"] == 22.0


def test_linha_do_tempo_nao_chuta_fim_no_cold_start(m):
    sid = m.servico(nome="Novo", estoque_minimo=5)
    m.compra(4, 100, dias_atras=10, servico=sid, recebe_em=8)
    m.alocar(1, dias_atras=5, servico=sid)
    lt = projetar(m.ctx(), m.ctx().servico(sid), HOJE)["linha_tempo"]
    assert lt["acaba_em"] is None and lt["comprar_em"] == 0
