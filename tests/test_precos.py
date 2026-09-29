"""Decisão 3 — preço fora do padrão."""
import pytest

from app.motor.precos import (avaliar_aquisicao, avaliar_preco, comparacao_fornecedores, mad,
                              melhor_fornecedor, referencia_atual)
from tests.conftest import HOJE


def test_mad_ignora_um_valor_absurdo():
    valores = [10, 10, 10, 11, 1000]
    assert mad(valores, 10) == 0      # o 1000 não arrasta a dispersão


def test_sem_base_com_menos_de_tres_precos():
    assert avaliar_preco(100, [90, 91])["nivel"] == "sem_base"


@pytest.mark.parametrize("preco,nivel", [
    (103.00, "normal"),   # +3%: cabe num reajuste anual
    (107.00, "nota"),     # +7%
    (118.00, "alerta"),   # +18%
    (92.00, "queda"),     # −8%
])
def test_limiares_com_preco_historicamente_fixo(preco, nivel):
    assert avaliar_preco(preco, [100, 100, 100, 100, 100])["nivel"] == nivel


def test_z_modificado_rebaixa_quando_o_fornecedor_sempre_oscila():
    historico = [100, 92, 108, 95, 106]      # oscila ±8%
    r = avaliar_preco(109, historico)       # +9% contra a mediana 100
    assert r["nivel"] == "normal" and r["rebaixado"] is True
    assert abs(r["z"]) < 3.5


def test_z_modificado_nao_rebaixa_salto_fora_da_oscilacao():
    historico = [100, 101, 99, 100, 102]
    r = avaliar_preco(120, historico)
    assert r["nivel"] == "alerta" and r["rebaixado"] is False


def test_mediana_aceita_o_novo_patamar_depois_de_tres_compras(m):
    for atras in (100, 90, 80, 70, 60):
        m.compra(10, 100.0, dias_atras=atras)
    niveis = []
    for atras in (50, 40, 30, 20):
        a = m.compra(10, 110.0, dias_atras=atras)
        niveis.append(avaliar_aquisicao(m.ctx().aquisicoes, a)["nivel"])
    assert niveis == ["nota", "nota", "nota", "normal"]


def test_janela_de_180_dias_descarta_preco_antigo(m):
    for atras in (400, 390, 380):
        m.compra(10, 50.0, dias_atras=atras)
    a = m.compra(10, 100.0, dias_atras=1)
    assert avaliar_aquisicao(m.ctx().aquisicoes, a)["nivel"] == "sem_base"


def test_preco_esperado_usa_ultimo_quando_houve_alerta(m):
    for atras in (60, 50, 40, 30):
        m.compra(10, 100.0, dias_atras=atras)
    m.compra(10, 120.0, dias_atras=5)
    ref = referencia_atual(m.ctx().aquisicoes, 1, 1, HOJE)
    assert ref["usa_ultimo_preco"] is True and ref["preco_esperado"] == 120.0
    assert ref["mediana"] == 100.0


def test_recomendacao_troca_de_fornecedor_depois_da_alta(m):
    for atras in (60, 50, 40):
        m.compra(10, 90.0, dias_atras=atras, fornecedor=1)
        m.compra(10, 95.0, dias_atras=atras, fornecedor=2)
    assert melhor_fornecedor(m.ctx(), 1, HOJE)["fornecedor"] == "Fornecedor A"
    m.compra(10, 108.0, dias_atras=2, fornecedor=1)      # +20%: alerta
    assert melhor_fornecedor(m.ctx(), 1, HOJE)["fornecedor"] == "Fornecedor B"


def test_comparacao_marca_fornecedor_mais_de_dez_por_cento_acima(m):
    for atras in (60, 50, 40):
        m.compra(10, 100.0, dias_atras=atras, fornecedor=1)
        m.compra(10, 112.0, dias_atras=atras, fornecedor=2)
    comp = comparacao_fornecedores(m.ctx(), 1, HOJE)
    caro = next(l for l in comp["linhas"] if l["fornecedor"] == "Fornecedor B")
    barato = next(l for l in comp["linhas"] if l["fornecedor"] == "Fornecedor A")
    assert caro["acima_do_limiar"] is True
    assert caro["custo_extra_estimado"] == 3 * 10 * 12.0
    assert barato["custo_extra_estimado"] == 0 and barato["e_o_melhor"]


def test_fornecedor_de_base_fraca_nao_vira_referencia(m):
    for atras in (60, 50, 40):
        m.compra(10, 100.0, dias_atras=atras, fornecedor=1)
    m.compra(10, 80.0, dias_atras=10, fornecedor=2)       # uma compra só, mais barata
    assert melhor_fornecedor(m.ctx(), 1, HOJE)["fornecedor"] == "Fornecedor A"
