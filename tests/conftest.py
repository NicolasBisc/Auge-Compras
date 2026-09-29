"""Contextos pequenos e controlados: cada teste monta só o que a regra precisa."""
from datetime import date, timedelta

import pytest

from app.motor.dominio import (Alocacao, Aquisicao, Cliente, Contexto, Fornecedor,
                               Recebimento, Servico)

HOJE = date(2026, 9, 28)


class Montador:
    def __init__(self):
        self.servicos = [Servico(1, "Voucher A1", "Certificado", "voucher", "discreta", 12, None)]
        self.fornecedores = [Fornecedor(1, "Fornecedor A", "11111111000100", 2),
                             Fornecedor(2, "Fornecedor B", "22222222000100", 10)]
        self.clientes = [Cliente(i, f"Cliente {i}", "Teste") for i in range(1, 201)]
        self.aquisicoes, self.alocacoes, self.recebimentos = [], [], []
        self.chaves = set()

    def servico(self, **kw):
        base = dict(id=len(self.servicos) + 1, nome=f"Item {len(self.servicos) + 1}", categoria="x",
                    unidade="un", tipo_quantidade="discreta", validade_meses=None, estoque_minimo=None)
        base.update(kw)
        self.servicos.append(Servico(**base))
        return base["id"]

    def compra(self, qtd, preco, dias_atras, servico=1, fornecedor=1, recebe_em=None, recebe_qtd=None,
               encerrada=False, codigo=None):
        aid = len(self.aquisicoes) + 1
        a = Aquisicao(aid, codigo or f"AQ-{aid:04d}", servico, fornecedor, qtd, preco,
                      HOJE - timedelta(days=dias_atras), encerrada)
        self.aquisicoes.append(a)
        if recebe_em is not None:
            self.receber(aid, recebe_qtd if recebe_qtd is not None else qtd, preco, recebe_em)
        return a

    def receber(self, aquisicao_id, qtd, preco, dias_atras, status="conforme", dif=0.0):
        rid = len(self.recebimentos) + 1
        self.recebimentos.append(Recebimento(rid, rid, aquisicao_id, qtd, preco, round(qtd * preco, 2),
                                             HOJE - timedelta(days=dias_atras), status, dif))

    def alocar(self, qtd, dias_atras, servico=1, cliente=1):
        self.alocacoes.append(Alocacao(len(self.alocacoes) + 1, servico, cliente, qtd,
                                       HOJE - timedelta(days=dias_atras)))

    def ctx(self):
        return Contexto(self.servicos, self.fornecedores, self.clientes, self.aquisicoes, self.alocacoes,
                        self.recebimentos, frozenset(self.chaves))


@pytest.fixture
def m():
    return Montador()
