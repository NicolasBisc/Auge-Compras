"""
Persistência em SQLite (arquivo único, zero instalação).

O motor não conhece o banco: aqui carregamos tudo para as dataclasses do
domínio e o motor calcula em memória. Para o volume de um escritório
(centenas de registros por mês) isso é mais simples e rápido que otimizar
consultas — troca-se quando o volume pedir, não antes.
"""
import os
import sqlite3
from datetime import date
from pathlib import Path

from app.motor.dominio import (Alocacao, Aquisicao, Cliente, Contexto, Fornecedor,
                               Recebimento, Servico)

RAIZ = Path(__file__).resolve().parent.parent
CAMINHO_PADRAO = RAIZ / "auge.db"

ESQUEMA = """
CREATE TABLE IF NOT EXISTS servico (
    id INTEGER PRIMARY KEY,
    nome TEXT NOT NULL UNIQUE,
    categoria TEXT NOT NULL,
    unidade TEXT NOT NULL,
    tipo_quantidade TEXT NOT NULL DEFAULT 'discreta' CHECK (tipo_quantidade IN ('discreta', 'continua')),
    validade_meses INTEGER CHECK (validade_meses IS NULL OR validade_meses > 0),
    estoque_minimo INTEGER CHECK (estoque_minimo IS NULL OR estoque_minimo >= 0)
);
CREATE TABLE IF NOT EXISTS fornecedor (
    id INTEGER PRIMARY KEY,
    nome TEXT NOT NULL UNIQUE,
    cnpj TEXT NOT NULL UNIQUE,
    lead_time_dias INTEGER NOT NULL CHECK (lead_time_dias >= 0)
);
CREATE TABLE IF NOT EXISTS cliente (
    id INTEGER PRIMARY KEY,
    nome TEXT NOT NULL UNIQUE,
    segmento TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS aquisicao (
    id INTEGER PRIMARY KEY,
    codigo TEXT NOT NULL UNIQUE,
    servico_id INTEGER NOT NULL REFERENCES servico(id),
    fornecedor_id INTEGER NOT NULL REFERENCES fornecedor(id),
    quantidade REAL NOT NULL CHECK (quantidade > 0),
    preco_unitario REAL NOT NULL CHECK (preco_unitario > 0),
    data_pedido TEXT NOT NULL,
    encerrada INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS alocacao (
    id INTEGER PRIMARY KEY,
    servico_id INTEGER NOT NULL REFERENCES servico(id),
    cliente_id INTEGER NOT NULL REFERENCES cliente(id),
    quantidade REAL NOT NULL CHECK (quantidade > 0),
    data TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS nota_fiscal (
    id INTEGER PRIMARY KEY,
    chave TEXT NOT NULL UNIQUE,          -- impede importar a mesma nota duas vezes
    numero TEXT NOT NULL,
    emitente_cnpj TEXT NOT NULL,
    emitente_nome TEXT NOT NULL,
    data_emissao TEXT NOT NULL,
    data_recebimento TEXT NOT NULL,
    status TEXT NOT NULL,
    xml TEXT                              -- original guardado para auditoria
);
CREATE TABLE IF NOT EXISTS nota_item (
    id INTEGER PRIMARY KEY,
    nota_id INTEGER NOT NULL REFERENCES nota_fiscal(id),
    aquisicao_id INTEGER NOT NULL REFERENCES aquisicao(id),
    quantidade REAL NOT NULL,
    preco_unitario REAL NOT NULL,
    valor_total REAL NOT NULL,
    status TEXT NOT NULL,
    status_preco TEXT NOT NULL,
    diferenca_valor REAL NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS ix_aquisicao_servico ON aquisicao(servico_id, fornecedor_id, data_pedido);
CREATE INDEX IF NOT EXISTS ix_alocacao_servico ON alocacao(servico_id, data);
CREATE INDEX IF NOT EXISTS ix_nota_item_aquisicao ON nota_item(aquisicao_id);
"""


def conectar(caminho: str | Path | None = None) -> sqlite3.Connection:
    caminho = caminho or os.environ.get("AUGE_DB") or CAMINHO_PADRAO
    conn = sqlite3.connect(str(caminho), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(ESQUEMA)
    return conn


def zerar(conn: sqlite3.Connection) -> None:
    for t in ("nota_item", "nota_fiscal", "alocacao", "aquisicao", "cliente", "fornecedor", "servico"):
        conn.execute(f"DELETE FROM {t}")
    conn.commit()


def _d(s: str) -> date:
    return date.fromisoformat(s)


def carregar_contexto(conn: sqlite3.Connection) -> Contexto:
    q = conn.execute
    recebimentos = [
        Recebimento(r["id"], r["nota_id"], r["aquisicao_id"], r["quantidade"], r["preco_unitario"],
                    r["valor_total"], _d(r["data_recebimento"]), r["status_preco"], r["diferenca_valor"])
        for r in q("""SELECT i.*, n.data_recebimento FROM nota_item i
                      JOIN nota_fiscal n ON n.id = i.nota_id ORDER BY i.id""")
    ]
    return Contexto(
        servicos=[Servico(r["id"], r["nome"], r["categoria"], r["unidade"], r["tipo_quantidade"],
                          r["validade_meses"], r["estoque_minimo"]) for r in q("SELECT * FROM servico ORDER BY id")],
        fornecedores=[Fornecedor(r["id"], r["nome"], r["cnpj"], r["lead_time_dias"])
                      for r in q("SELECT * FROM fornecedor ORDER BY id")],
        clientes=[Cliente(r["id"], r["nome"], r["segmento"]) for r in q("SELECT * FROM cliente ORDER BY nome")],
        aquisicoes=[Aquisicao(r["id"], r["codigo"], r["servico_id"], r["fornecedor_id"], r["quantidade"],
                              r["preco_unitario"], _d(r["data_pedido"]), bool(r["encerrada"]))
                    for r in q("SELECT * FROM aquisicao ORDER BY data_pedido, id")],
        alocacoes=[Alocacao(r["id"], r["servico_id"], r["cliente_id"], r["quantidade"], _d(r["data"]))
                   for r in q("SELECT * FROM alocacao ORDER BY data, id")],
        recebimentos=recebimentos,
        chaves_importadas=frozenset(r["chave"] for r in q("SELECT chave FROM nota_fiscal")),
    )


# --- gravações -------------------------------------------------------------
def inserir(conn, tabela: str, **campos) -> int:
    cols = ", ".join(campos)
    marcas = ", ".join("?" for _ in campos)
    cur = conn.execute(f"INSERT INTO {tabela} ({cols}) VALUES ({marcas})", tuple(campos.values()))
    return cur.lastrowid


def proximo_codigo_aquisicao(conn, ano: int) -> str:
    prefixo = f"AQ-{ano}-"
    r = conn.execute("SELECT codigo FROM aquisicao WHERE codigo LIKE ? ORDER BY codigo DESC LIMIT 1",
                     (prefixo + "%",)).fetchone()
    n = int(r["codigo"].rsplit("-", 1)[1]) + 1 if r else 1
    return f"{prefixo}{n:04d}"


def gravar_nota(conn, nota: dict, resultado: dict, data_recebimento: date, xml: str) -> int:
    nid = inserir(conn, "nota_fiscal", chave=nota["chave"], numero=nota["numero"],
                  emitente_cnpj=nota["emitente_cnpj"], emitente_nome=nota["emitente_nome"],
                  data_emissao=nota["emissao"], data_recebimento=data_recebimento.isoformat(),
                  status=resultado["status"], xml=xml)
    for it in resultado["itens"]:
        if it.get("importavel"):
            inserir(conn, "nota_item", nota_id=nid, aquisicao_id=it["aquisicao_id"], quantidade=it["quantidade"],
                    preco_unitario=it["preco_unitario"], valor_total=it["valor_total"], status=it["status"],
                    status_preco=it["status_preco"], diferenca_valor=it["diferenca_valor"])
    conn.commit()
    return nid


def listar_notas(conn) -> list[dict]:
    notas = []
    for n in conn.execute("SELECT * FROM nota_fiscal ORDER BY data_recebimento DESC, id DESC"):
        itens = conn.execute("""SELECT i.quantidade, i.valor_total, i.status, i.status_preco, i.diferenca_valor,
                                       a.codigo, s.nome AS servico
                                FROM nota_item i JOIN aquisicao a ON a.id = i.aquisicao_id
                                JOIN servico s ON s.id = a.servico_id WHERE i.nota_id = ?""", (n["id"],)).fetchall()
        notas.append({"id": n["id"], "numero": n["numero"], "chave": n["chave"], "emitente": n["emitente_nome"],
                      "data_recebimento": n["data_recebimento"], "status": n["status"],
                      "valor_total": round(sum(i["valor_total"] for i in itens), 2),
                      "itens": [dict(i) for i in itens]})
    return notas
