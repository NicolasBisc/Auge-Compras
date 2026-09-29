"""
API do protótipo. Cada rota é fina: valida o formato e chama um caso de uso.

Rodar:  uvicorn app.main:app --reload     e abrir http://127.0.0.1:8000
Docs automáticas da API: http://127.0.0.1:8000/docs
"""
from datetime import date
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app import casos_de_uso as uc
from app import config, db

RAIZ = Path(__file__).resolve().parent.parent
WEB = RAIZ / "web"
EXEMPLOS = RAIZ / "dados" / "notas_exemplo"

app = FastAPI(title="Auge · Projeção de compras e conciliação",
              description="Protótipo do desafio de estágio, com dados fictícios.", version="1.0")


def _ctx():
    return db.carregar_contexto(db.conectar())


def _regra(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except uc.ErroDeRegra as e:
        raise HTTPException(status_code=422, detail=str(e))


# --- interface --------------------------------------------------------------
app.mount("/assets", StaticFiles(directory=WEB / "assets"), name="assets")
app.mount("/css", StaticFiles(directory=WEB / "css"), name="css")
app.mount("/js", StaticFiles(directory=WEB / "js"), name="js")


@app.get("/", include_in_schema=False)
def interface():
    return FileResponse(WEB / "index.html")


# --- leituras ----------------------------------------------------------------
@app.get("/api/painel")
def painel():
    return uc.painel(_ctx(), config.hoje())


@app.get("/api/catalogos")
def catalogos():
    return uc.catalogos(_ctx())


@app.get("/api/projecao")
def projecao(horizonte: int = Query(config.HORIZONTE_DIAS, ge=7, le=120)):
    return uc.projecoes(_ctx(), config.hoje(), horizonte)


@app.get("/api/precos/evolucao")
def evolucao(servico_id: int, dias: int = Query(config.JANELA_PRECO_DIAS, ge=30, le=730)):
    ctx = _ctx()
    if not any(s.id == servico_id for s in ctx.servicos):
        raise HTTPException(404, "Item não encontrado.")
    return uc.evolucao_precos(ctx, servico_id, dias, config.hoje())


@app.get("/api/precos/anomalias")
def anomalias(dias: int = Query(config.JANELA_PRECO_DIAS, ge=30, le=730)):
    return uc.anomalias(_ctx(), dias, config.hoje())


@app.get("/api/aquisicoes")
def aquisicoes():
    return uc.aquisicoes(_ctx(), config.hoje())


@app.get("/api/alocacoes")
def alocacoes():
    return uc.alocacoes(_ctx())


@app.get("/api/notas")
def notas():
    return db.listar_notas(db.conectar())


@app.get("/api/regras")
def regras():
    return {"hoje": config.hoje().isoformat(), "regras": config.como_dicionario()}


# --- conciliação -------------------------------------------------------------
async def _ler(arquivo: UploadFile) -> bytes:
    conteudo = await arquivo.read(config.TAMANHO_MAXIMO_XML + 1)
    if not conteudo:
        raise HTTPException(422, "Arquivo vazio.")
    return conteudo


@app.post("/api/conciliacao/previa")
async def previa(arquivo: UploadFile = File(...)):
    """Confere a nota sem gravar nada."""
    return uc.previsualizar_nota(_ctx(), await _ler(arquivo), config.hoje())


@app.post("/api/conciliacao/importar")
async def importar(arquivo: UploadFile = File(...)):
    """Confere e grava: o que chegou passa a contar na capacidade."""
    conteudo = await _ler(arquivo)
    try:
        return uc.importar_nota(db.conectar(), conteudo, config.hoje())
    except uc.ErroDeRegra as e:
        raise HTTPException(409, str(e))


# --- notas de exemplo (para testar sem ter XML real) ---------------------------------
def _exemplo(nome: str) -> bytes:
    permitidos = {p.name: p for p in EXEMPLOS.glob("*.xml")}
    if nome not in permitidos:        # só nomes da lista: nada de caminhos arbitrários
        raise HTTPException(404, "Nota de exemplo não encontrada.")
    return permitidos[nome].read_bytes()


@app.get("/api/notas-exemplo")
def notas_exemplo():
    return sorted(p.name for p in EXEMPLOS.glob("*.xml"))


@app.get("/api/notas-exemplo/{nome}/previa")
def previa_exemplo(nome: str):
    return uc.previsualizar_nota(_ctx(), _exemplo(nome), config.hoje())


@app.post("/api/notas-exemplo/{nome}/importar")
def importar_exemplo(nome: str):
    try:
        return uc.importar_nota(db.conectar(), _exemplo(nome), config.hoje())
    except uc.ErroDeRegra as e:
        raise HTTPException(409, str(e))


# --- cadastros ----------------------------------------------------------------
class NovaAquisicao(BaseModel):
    servico_id: int
    fornecedor_id: int
    quantidade: float = Field(gt=0)
    preco_unitario: float = Field(gt=0)
    data_pedido: date


class NovaAlocacao(BaseModel):
    servico_id: int
    cliente_id: int
    quantidade: float = Field(gt=0)
    data: date


class NovoServico(BaseModel):
    nome: str
    categoria: str = "Geral"
    unidade: str = "unidade"
    tipo_quantidade: str = "discreta"
    validade_meses: Optional[int] = None
    estoque_minimo: Optional[int] = None


class NovoFornecedor(BaseModel):
    nome: str
    cnpj: str
    lead_time_dias: int


class NovoCliente(BaseModel):
    nome: str
    segmento: str = "Geral"


class EstoqueMinimo(BaseModel):
    estoque_minimo: Optional[int] = None


@app.post("/api/aquisicoes", status_code=201)
def nova_aquisicao(d: NovaAquisicao):
    return _regra(uc.registrar_aquisicao, db.conectar(), d.servico_id, d.fornecedor_id, d.quantidade,
                  d.preco_unitario, d.data_pedido, config.hoje())


@app.post("/api/aquisicoes/{codigo}/encerrar")
def encerrar(codigo: str):
    return _regra(uc.encerrar_aquisicao, db.conectar(), codigo)


@app.post("/api/alocacoes", status_code=201)
def nova_alocacao(d: NovaAlocacao):
    return _regra(uc.registrar_alocacao, db.conectar(), d.servico_id, d.cliente_id, d.quantidade,
                  d.data, config.hoje())


@app.post("/api/servicos", status_code=201)
def novo_servico(d: NovoServico):
    return _regra(uc.registrar_servico, db.conectar(), d.nome, d.categoria, d.unidade, d.tipo_quantidade,
                  d.validade_meses, d.estoque_minimo)


@app.put("/api/servicos/{servico_id}/estoque-minimo")
def estoque_minimo(servico_id: int, d: EstoqueMinimo):
    return _regra(uc.definir_estoque_minimo, db.conectar(), servico_id, d.estoque_minimo)


@app.post("/api/fornecedores", status_code=201)
def novo_fornecedor(d: NovoFornecedor):
    return _regra(uc.registrar_fornecedor, db.conectar(), d.nome, d.cnpj, d.lead_time_dias)


@app.post("/api/clientes", status_code=201)
def novo_cliente(d: NovoCliente):
    return _regra(uc.registrar_cliente, db.conectar(), d.nome, d.segmento)
