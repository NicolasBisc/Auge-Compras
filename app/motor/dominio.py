"""
Entidades do domínio (Fase 1 da modelagem).

São estruturas imutáveis e sem acesso a banco: o motor recebe listas delas e
devolve resultados. Isso permite testar cada decisão isoladamente.

Mapeamento para a Auge:
  Servico     → item que a Auge compra e repassa (voucher, token, licença, hora)
  Aquisicao   → o que foi COMBINADO com o fornecedor (o pedido)
  Alocacao    → consumo: um item entregue a um cliente
  Recebimento → o que CHEGOU, linha de uma nota fiscal já importada
Estoque não é entidade: é calculado (ver capacidade.py).
"""
from dataclasses import dataclass
from datetime import date
from typing import Optional


@dataclass(frozen=True)
class Servico:
    id: int
    nome: str
    categoria: str
    unidade: str                      # rótulo exibido: voucher, unidade, licença, hora
    tipo_quantidade: str = "discreta"  # 'discreta' (contável) ou 'continua' (peso, volume)
    validade_meses: Optional[int] = None  # certificados vencem → renovações previsíveis
    estoque_minimo: Optional[int] = None  # piso declarado pelo usuário (regra do cold start)


@dataclass(frozen=True)
class Fornecedor:
    id: int
    nome: str
    cnpj: str
    lead_time_dias: int  # tempo médio entre pedir e receber, informado no cadastro


@dataclass(frozen=True)
class Cliente:
    id: int
    nome: str
    segmento: str


@dataclass(frozen=True)
class Aquisicao:
    id: int
    codigo: str          # vai no campo xPed da nota: é o que liga nota e pedido
    servico_id: int
    fornecedor_id: int
    quantidade: float
    preco_unitario: float
    data_pedido: date
    encerrada: bool = False  # o usuário declara que não virá mais nada


@dataclass(frozen=True)
class Alocacao:
    id: int
    servico_id: int
    cliente_id: int
    quantidade: float
    data: date


@dataclass(frozen=True)
class Recebimento:
    id: int
    nota_id: int
    aquisicao_id: int
    quantidade: float
    preco_unitario: float
    valor_total: float
    data_recebimento: date
    status_preco: str = "conforme"   # conforme | menor | material | a_favor
    diferenca_valor: float = 0.0     # valor cobrado − valor combinado, em R$


@dataclass(frozen=True)
class Contexto:
    """Tudo que o motor precisa para calcular, carregado de uma vez."""
    servicos: list
    fornecedores: list
    clientes: list
    aquisicoes: list
    alocacoes: list
    recebimentos: list
    chaves_importadas: frozenset

    def servico(self, sid: int) -> Servico:
        return next(s for s in self.servicos if s.id == sid)

    def fornecedor(self, fid: int) -> Fornecedor:
        return next(f for f in self.fornecedores if f.id == fid)

    def aquisicao_por_codigo(self, codigo: str) -> Optional[Aquisicao]:
        return next((a for a in self.aquisicoes if a.codigo == codigo), None)
