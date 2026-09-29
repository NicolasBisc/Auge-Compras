"""Decisão 4 — tolerância na conciliação."""
import random

import pytest

from app.motor.conciliacao import (NotaInvalida, avaliar_preco, chave_valida, conciliar,
                                   digito_verificador_chave, ler_nota)
from app.seed import chave_acesso, xml_nota
from tests.conftest import HOJE

CNPJ_A = "11111111000100"


def nota(m, itens, cnpj=CNPJ_A, chave=None):
    chave = chave or chave_acesso(cnpj, HOJE, random.randrange(10**6), random.Random(len(itens)))
    xml = xml_nota(chave, 1, HOJE, (cnpj, "Emitente"), [
        {"cprod": "X", "descricao": "Item", "unidade": "UN", "qtd": q, "unit": u, "pedido": p}
        for q, u, p in itens])
    return ler_nota(xml.encode())


# --- leitura e segurança ---------------------------------------------------------
def test_digito_verificador_da_chave():
    base = "4126099011122200010055001000001001123456"[:43].ljust(43, "0")
    chave = base + str(digito_verificador_chave(base))
    assert chave_valida(chave)
    assert not chave_valida(chave[:-1] + str((int(chave[-1]) + 1) % 10))


def test_recusa_doctype_e_entidades():
    ataque = b'<?xml version="1.0"?><!DOCTYPE x [<!ENTITY a "aaaa">]><x>&a;</x>'
    with pytest.raises(NotaInvalida, match="DOCTYPE"):
        ler_nota(ataque)


def test_recusa_xml_malformado_e_arquivo_que_nao_e_nfe():
    with pytest.raises(NotaInvalida, match="malformado"):
        ler_nota(b"<nfe><sem-fechar>")
    with pytest.raises(NotaInvalida, match="infNFe"):
        ler_nota(b"<qualquer><coisa/></qualquer>")


def test_le_os_campos_do_layout_nfe(m):
    n = nota(m, [(20, 94.499, "AQ-0001")])
    assert n["emitente_cnpj"] == CNPJ_A
    assert n["itens"][0] == {"n": 1, "codigo_produto": "X", "descricao": "Item", "quantidade": 20.0,
                             "preco_unitario": 94.499, "valor_total": 1889.98, "pedido": "AQ-0001"}


# --- as três camadas de preço -----------------------------------------------------
def test_camada_1_arredondamento_e_conforme():
    check, status, dif = avaliar_preco(20, 94.499, 1889.98, 94.50, 0)
    assert (check["status"], status, dif) == ("ok", "conforme", -0.02)


def test_um_centavo_real_no_unitario_nao_e_arredondamento():
    check, status, _ = avaliar_preco(20, 94.51, 1890.20, 94.50, 0)
    assert status == "menor" and check["status"] == "atencao"


def test_camada_2_abaixo_da_materialidade_fica_ambar():
    check, status, dif = avaliar_preco(3, 189.50, 568.50, 189.00, 0)
    assert (check["status"], status, dif) == ("atencao", "menor", 1.50)


def test_camada_2_acima_da_materialidade_e_divergencia():
    # R$ 37,50 a mais; limite = max(R$ 10; 1% de R$ 1.537,50 = R$ 15,38)
    check, status, _ = avaliar_preco(15, 105.00, 1575.00, 102.50, 0)
    assert (check["status"], status) == ("divergencia", "material")
    assert check["valores"]["limite_material"] == 15.38


def test_materialidade_cresce_com_o_valor_da_linha():
    # R$ 40 a mais num pedido de R$ 20.000 fica abaixo de 1% (R$ 200)
    check, status, _ = avaliar_preco(100, 200.40, 20040.00, 200.00, 0)
    assert status == "menor" and check["status"] == "atencao"


def test_camada_3_acumulo_do_fornecedor_vira_alerta():
    check, status, _ = avaliar_preco(20, 180.30, 3606.00, 180.00, acumulado_antes=47.00)
    assert check["status"] == "divergencia" and status == "menor"
    assert check["valores"]["acumulado_fornecedor"] == 53.00


def test_cobrado_a_menos_pede_confirmacao():
    check, status, _ = avaliar_preco(10, 90.00, 900.00, 95.00, 0)
    assert (check["status"], status) == ("atencao", "a_favor")


# --- conciliação completa ---------------------------------------------------------
def test_quantidade_parcial_no_prazo_e_faltante_fora_do_prazo(m):
    m.compra(10, 50.0, dias_atras=1, codigo="AQ-NOVO")
    m.compra(10, 50.0, dias_atras=30, codigo="AQ-VELHO")
    r = conciliar(m.ctx(), nota(m, [(6, 50.0, "AQ-NOVO"), (6, 50.0, "AQ-VELHO")]), HOJE)
    q = [next(c for c in i["verificacoes"] if c["tipo"] == "quantidade") for i in r["itens"]]
    assert [c["status"] for c in q] == ["atencao", "divergencia"]
    assert [c["titulo"] for c in q] == ["Entrega parcial", "Quantidade faltante"]


def test_excesso_e_sempre_divergencia(m):
    m.compra(10, 50.0, dias_atras=1, codigo="AQ-1")
    r = conciliar(m.ctx(), nota(m, [(12, 50.0, "AQ-1")]), HOJE)
    assert r["status"] == "divergencia"


def test_segunda_nota_completa_a_entrega_parcial(m):
    a = m.compra(10, 50.0, dias_atras=3, codigo="AQ-1")
    m.receber(a.id, 6, 50.0, dias_atras=2)
    r = conciliar(m.ctx(), nota(m, [(4, 50.0, "AQ-1")]), HOJE)
    assert r["status"] == "ok"


def test_emitente_diferente_do_fornecedor(m):
    m.compra(5, 50.0, dias_atras=1, codigo="AQ-1")       # fornecedor A
    r = conciliar(m.ctx(), nota(m, [(5, 50.0, "AQ-1")], cnpj="22222222000100"), HOJE)
    assert any(c["tipo"] == "emitente" and c["status"] == "divergencia" for c in r["itens"][0]["verificacoes"])


def test_pedido_inexistente_nao_e_importavel(m):
    r = conciliar(m.ctx(), nota(m, [(5, 50.0, "AQ-9999")]), HOJE)
    assert r["status"] == "divergencia" and r["itens"][0]["importavel"] is False


def test_nota_duplicada_e_rejeitada(m):
    m.compra(5, 50.0, dias_atras=1, codigo="AQ-1")
    n = nota(m, [(5, 50.0, "AQ-1")])
    m.chaves.add(n["chave"])
    r = conciliar(m.ctx(), n, HOJE)
    assert r["rejeitada"] and "já foi importada" in r["motivo"]


def test_chave_com_digito_errado_e_rejeitada(m):
    m.compra(5, 50.0, dias_atras=1, codigo="AQ-1")
    boa = chave_acesso(CNPJ_A, HOJE, 1, random.Random(1))
    ruim = boa[:-1] + str((int(boa[-1]) + 1) % 10)
    r = conciliar(m.ctx(), nota(m, [(5, 50.0, "AQ-1")], chave=ruim), HOJE)
    assert r["rejeitada"] and "Chave de acesso" in r["motivo"]


def test_nota_internamente_inconsistente(m):
    m.compra(5, 50.0, dias_atras=1, codigo="AQ-1")
    n = nota(m, [(5, 50.0, "AQ-1")])
    n["itens"][0]["valor_total"] = 260.00           # 5 × 50 = 250
    r = conciliar(m.ctx(), n, HOJE)
    assert any(c["tipo"] == "consistencia" for c in r["itens"][0]["verificacoes"])
