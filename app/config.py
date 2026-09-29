"""
Painel de calibração do sistema.

Todo número que decide alguma coisa mora aqui, com a justificativa ao lado.
Mudar um valor muda o comportamento do sistema inteiro — de propósito:
é esta lista que se revisa com o usuário depois do primeiro mês de uso real.
"""
import os
from datetime import date

from app.motor.formato import brl, num

# Data de referência da demonstração. Fixa para que dados fictícios e testes
# deem sempre o mesmo resultado. Em produção, apague a variável e vale o dia de hoje.
_DATA_ENV = os.environ.get("AUGE_DATA_REFERENCIA", "2026-09-28")


def hoje() -> date:
    return date.fromisoformat(_DATA_ENV) if _DATA_ENV else date.today()


# ---------------------------------------------------------------------------
# Decisão 1 — cold start e projeção
# ---------------------------------------------------------------------------
# Janela do "ritmo recente": 90 dias ≈ três ciclos mensais de obrigações
# contábeis. Curta o bastante para reagir, longa o bastante para não
# depender de uma semana atípica.
JANELA_RITMO_DIAS = 90

# Mínimo de dias acompanhando um item antes de extrapolar ritmo: um ciclo mensal.
MIN_DIAS_ACOMPANHAMENTO = 30

# Confiança pelo número de alocações (eventos) na janela. Contagem de eventos
# independentes tem erro relativo ≈ 1/√n (processo de Poisson):
#   n = 4  → ±50%  (baixa)   n = 16 → ±25%  (média)   n = 36 → ±17%  (alta)
# Abaixo de 4 eventos o erro passa de 50%: qualquer ritmo seria chute.
EVENTOS_CONFIANCA = {"baixa": 4, "media": 16, "alta": 36}

# "Período" do desafio: quanto comprar para cobrir os próximos 30 dias.
HORIZONTE_DIAS = 30

# Estoque de segurança = z × √(demanda no lead time), a fórmula para demanda
# de contagem (Poisson). z = 1,65 ≈ 95% de chance de não faltar no lead time.
Z_NIVEL_SERVICO = 1.65

# Status "planejar": a data de reposição cai dentro de uma semana.
DIAS_ANTECEDENCIA_ATENCAO = 7

# Lead time observado (mediana entre pedido e primeiro recebimento) só
# substitui o cadastrado depois de 3 entregas — mesmo raciocínio da mediana.
MIN_ENTREGAS_LEAD_TIME = 3

# ---------------------------------------------------------------------------
# Decisão 3 — preço fora do padrão
# ---------------------------------------------------------------------------
# "Últimos 6 meses", como no enunciado.
JANELA_PRECO_DIAS = 180
# Referência = mediana das últimas 5 compras do par item+fornecedor.
# Ímpar dá mediana exata; 5 é pequeno o bastante para aceitar um novo patamar
# depois de 3 compras (a mediana passa a ser o preço novo).
N_PRECOS_REFERENCIA = 5
# Com menos de 3 preços anteriores não existe "padrão": o sistema só acumula.
MIN_PRECOS_REFERENCIA = 3
# Até 5%: compatível com um reajuste anual pela inflação → normal.
LIMIAR_NOTA = 0.05
# 15% ou mais: cerca de três anos de inflação num salto → alerta.
LIMIAR_ALERTA = 0.15
# z modificado (Iglewicz e Hoaglin): acima de 3,5 é incomum PARA AQUELE
# fornecedor. Abaixo disso, a variação cabe na oscilação histórica dele
# e o nível é rebaixado um degrau.
LIMIAR_Z_MODIFICADO = 3.5
# Comparação entre fornecedores do mesmo item: mais de 10% acima do mais barato.
LIMIAR_DIFERENCA_FORNECEDOR = 0.10

# ---------------------------------------------------------------------------
# Decisão 4 — tolerância na conciliação
# ---------------------------------------------------------------------------
# Preço combinado tem 2 casas; a nota pode ter até 10 no unitário. Diferença
# menor que 1 centavo no unitário só pode ser representação decimal.
TOLERANCIA_UNITARIO = 0.01
# No total, cada unidade pode carregar até meio centavo de arredondamento.
MEIO_CENTAVO = 0.005
# Materialidade: acima do maior entre R$ 10 e 1% do valor da linha, a
# diferença vira divergência que exige ação. R$ 10 ≈ o custo de ~20 minutos
# de trabalho administrativo para contestar: abaixo disso, contestar custa
# mais do que recupera. 1% protege pedidos grandes.
MATERIALIDADE_MINIMA = 10.00
MATERIALIDADE_PERCENTUAL = 0.01
# Diferenças pequenas não somem: acumulam por fornecedor. Se a soma em 90
# dias passa de R$ 50, vira alerta de padrão recorrente (ideia de acumular
# distorções da NBC TA 450 / ISA 450).
LIMITE_ACUMULADO_FORNECEDOR = 50.00
JANELA_ACUMULO_DIAS = 90
# Itens vendidos por medida contínua (peso, volume) — herdado do desafio
# original; nenhum item da Auge usa hoje. Contáveis têm tolerância zero.
TOLERANCIA_QTD_CONTINUA = 0.02
# Prazo de entrega = pedido + o maior entre 1,5 × lead time e lead time + 3 dias.
# Dentro do prazo, falta é "entrega parcial"; depois, é "faltante".
FATOR_FOLGA_ENTREGA = 1.5
FOLGA_MINIMA_ENTREGA_DIAS = 3

# Segurança na importação de XML
TAMANHO_MAXIMO_XML = 2 * 1024 * 1024  # 2 MB


def como_dicionario() -> list[dict]:
    """Regras em formato legível, para a tela 'Regras' — transparência total."""
    return [
        {"decisao": "Cold start", "regra": "Dias mínimos de acompanhamento", "valor": f"{MIN_DIAS_ACOMPANHAMENTO} dias",
         "porque": "Um ciclo mensal completo antes de extrapolar qualquer ritmo."},
        {"decisao": "Cold start", "regra": "Eventos para confiança baixa / média / alta",
         "valor": f"{EVENTOS_CONFIANCA['baixa']} / {EVENTOS_CONFIANCA['media']} / {EVENTOS_CONFIANCA['alta']}",
         "porque": "Erro relativo ≈ 1/√n: 50%, 25% e 17%. Abaixo de 4 eventos, o ritmo seria chute."},
        {"decisao": "Projeção", "regra": "Janela do ritmo recente", "valor": f"{JANELA_RITMO_DIAS} dias",
         "porque": "Três ciclos mensais: reage a mudanças sem depender de uma semana atípica."},
        {"decisao": "Projeção", "regra": "Horizonte de compra", "valor": f"{HORIZONTE_DIAS} dias",
         "porque": "O 'período' do desafio; ajustável na tela."},
        {"decisao": "Projeção", "regra": "Nível de serviço (z)", "valor": num(Z_NIVEL_SERVICO, 2),
         "porque": "≈ 95% de chance de não faltar enquanto a reposição não chega."},
        {"decisao": "Preço", "regra": "Referência", "valor": f"mediana das últimas {N_PRECOS_REFERENCIA} compras em {JANELA_PRECO_DIAS} dias",
         "porque": "A mediana ignora um preço isolado e aceita um novo patamar depois de 3 compras."},
        {"decisao": "Preço", "regra": "Nota / alerta", "valor": f"{LIMIAR_NOTA:.0%} / {LIMIAR_ALERTA:.0%}",
         "porque": "Até 5% cabe num reajuste anual; 15% equivale a anos de inflação num salto."},
        {"decisao": "Preço", "regra": "z modificado", "valor": num(LIMIAR_Z_MODIFICADO),
         "porque": "Rebaixa o nível quando a variação cabe na oscilação histórica daquele fornecedor."},
        {"decisao": "Preço", "regra": "Diferença entre fornecedores", "valor": f"{LIMIAR_DIFERENCA_FORNECEDOR:.0%}",
         "porque": "Métrica separada: um fornecedor estável ainda pode ser o mais caro."},
        {"decisao": "Conciliação", "regra": "Arredondamento", "valor": "menos de R$ 0,01 no unitário",
         "porque": "E até meio centavo por unidade no total. É o máximo que a representação decimal consegue explicar."},
        {"decisao": "Conciliação", "regra": "Materialidade", "valor": f"maior entre {brl(MATERIALIDADE_MINIMA)} e {MATERIALIDADE_PERCENTUAL:.0%} da linha",
         "porque": "Abaixo disso, contestar custa mais que o valor recuperado."},
        {"decisao": "Conciliação", "regra": "Acúmulo por fornecedor", "valor": f"{brl(LIMITE_ACUMULADO_FORNECEDOR)} em {JANELA_ACUMULO_DIAS} dias",
         "porque": "Diferenças pequenas repetidas viram padrão e passam a ser alerta."},
        {"decisao": "Conciliação", "regra": "Quantidade de itens contáveis", "valor": "tolerância zero",
         "porque": "Não existe arredondamento de voucher: um a menos é um a menos."},
        {"decisao": "Conciliação", "regra": "Prazo de entrega", "valor": f"maior entre {num(FATOR_FOLGA_ENTREGA)} × prazo e prazo + {FOLGA_MINIMA_ENTREGA_DIAS} dias",
         "porque": "Dentro do prazo, falta é entrega parcial; depois dele, é faltante."},
    ]
