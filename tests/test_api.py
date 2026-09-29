"""Ponta a ponta: seed → API → importação de nota → projeção muda."""
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

NOTAS = Path(__file__).resolve().parent.parent / "dados" / "notas_exemplo"


@pytest.fixture
def cliente(tmp_path, monkeypatch):
    monkeypatch.setenv("AUGE_DB", str(tmp_path / "teste.db"))
    from app import db, seed
    seed.popular(db.conectar())
    from app.main import app
    return TestClient(app)


def _item(projecao, nome):
    return next(p for p in projecao if p["servico"] == nome)


def test_leituras_respondem(cliente):
    for rota in ("/api/painel", "/api/catalogos", "/api/projecao", "/api/precos/anomalias",
                 "/api/aquisicoes", "/api/alocacoes", "/api/notas", "/api/regras",
                 "/api/precos/evolucao?servico_id=1"):
        assert cliente.get(rota).status_code == 200, rota
    assert cliente.get("/").status_code == 200


def test_painel_traz_as_decisoes_planejadas(cliente):
    fila = cliente.get("/api/painel").json()["fila"]
    titulos = " | ".join(f["titulo"] for f in fila)
    assert "Comprar 2 vouchers de Certificado em nuvem" in titulos
    assert "Token criptográfico USB" in titulos
    assert "Vértice Certificação Digital subiu o preço" in titulos


def test_importar_nota_aumenta_capacidade_e_bloqueia_duplicata(cliente):
    antes = _item(cliente.get("/api/projecao").json(), "Voucher e-CNPJ A1")
    xml = (NOTAS / "01_conforme_arredondamento.xml").read_bytes()
    r = cliente.post("/api/conciliacao/importar", files={"arquivo": ("n.xml", xml, "text/xml")})
    assert r.status_code == 200 and r.json()["status"] == "ok"
    depois = _item(cliente.get("/api/projecao").json(), "Voucher e-CNPJ A1")
    assert depois["capacidade"] == antes["capacidade"] + 20
    assert depois["em_transito"] == antes["em_transito"] - 20
    dup = cliente.post("/api/conciliacao/importar", files={"arquivo": ("n.xml", xml, "text/xml")})
    assert dup.status_code == 409


def test_previa_nao_grava(cliente):
    xml = (NOTAS / "04_quantidade_excedente.xml").read_bytes()
    for _ in range(2):
        r = cliente.post("/api/conciliacao/previa", files={"arquivo": ("n.xml", xml, "text/xml")})
        assert r.json()["status"] == "divergencia"


def test_alocacao_acima_da_capacidade_e_recusada(cliente):
    r = cliente.post("/api/alocacoes", json={"servico_id": 5, "cliente_id": 1, "quantidade": 50,
                                             "data": "2026-09-28"})
    assert r.status_code == 422 and "Capacidade insuficiente" in r.json()["detail"]


def test_cadastro_de_aquisicao_avalia_o_preco_na_hora(cliente):
    r = cliente.post("/api/aquisicoes", json={"servico_id": 1, "fornecedor_id": 1, "quantidade": 10,
                                              "preco_unitario": 115.00, "data_pedido": "2026-09-28"})
    assert r.status_code == 201
    assert r.json()["avaliacao_preco"]["nivel"] == "alerta"


def test_cadastro_recusa_data_futura_e_fracao_de_voucher(cliente):
    base = {"servico_id": 1, "fornecedor_id": 1, "preco_unitario": 90.0}
    assert cliente.post("/api/aquisicoes", json={**base, "quantidade": 1, "data_pedido": "2027-01-01"}).status_code == 422
    assert cliente.post("/api/aquisicoes", json={**base, "quantidade": 1.5, "data_pedido": "2026-09-28"}).status_code == 422


def test_definir_estoque_minimo_tira_item_do_cold_start_sem_regra(cliente):
    r = cliente.put("/api/servicos/5/estoque-minimo", json={"estoque_minimo": 2})
    assert r.status_code == 200
    nuvem = _item(cliente.get("/api/projecao").json(), "Certificado em nuvem")
    assert nuvem["status"] == "ok" and nuvem["modo"] == "cold_start"
