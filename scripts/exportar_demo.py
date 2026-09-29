"""
Gera os dados da demonstração a partir do motor real (nada de lógica duplicada):

  web/js/dados-exemplo.js  → usado pela página quando não há servidor (Live Server, arquivo aberto direto)
  web/demo.html            → arquivo único com CSS, JS, logos e dados embutidos (para publicar ou mandar)

Rodar:  python -m scripts.exportar_demo
"""
import base64
import json
from pathlib import Path

from app import casos_de_uso as uc
from app import config, db, seed

RAIZ = Path(__file__).resolve().parent.parent
WEB = RAIZ / "web"
EXEMPLOS = RAIZ / "dados" / "notas_exemplo"


def _data_uri(caminho: Path) -> str:
    return "data:image/png;base64," + base64.b64encode(caminho.read_bytes()).decode()


def coletar() -> dict:
    conn = db.conectar(":memory:")
    seed.popular(conn)
    ctx = db.carregar_contexto(conn)
    hoje = config.hoje()
    d = {
        "/api/painel": uc.painel(ctx, hoje),
        "/api/catalogos": uc.catalogos(ctx),
        "/api/precos/anomalias?dias=180": uc.anomalias(ctx, 180, hoje),
        "/api/aquisicoes": uc.aquisicoes(ctx, hoje),
        "/api/alocacoes": uc.alocacoes(ctx),
        "/api/notas": db.listar_notas(conn),
        "/api/regras": {"hoje": hoje.isoformat(), "regras": config.como_dicionario()},
    }
    for h in (15, 30, 60):
        d[f"/api/projecao?horizonte={h}"] = uc.projecoes(ctx, hoje, h)
    for s in ctx.servicos:
        for dias in (90, 180, 365):
            d[f"/api/precos/evolucao?servico_id={s.id}&dias={dias}"] = uc.evolucao_precos(ctx, s.id, dias, hoje)
    nomes = sorted(p.name for p in EXEMPLOS.glob("*.xml"))
    for n in nomes:
        d[f"/api/notas-exemplo/{n}/previa"] = uc.previsualizar_nota(ctx, (EXEMPLOS / n).read_bytes(), hoje)
    # cenário extra só da demo: a nota 01 importada e enviada de novo
    primeira = (EXEMPLOS / nomes[0]).read_bytes()
    uc.importar_nota(conn, primeira, hoje)
    d["/api/notas-exemplo/09_nota_repetida.xml/previa"] = uc.previsualizar_nota(db.carregar_contexto(conn), primeira, hoje)
    d["/api/notas-exemplo"] = nomes + ["09_nota_repetida.xml"]
    return d


def gerar() -> Path:
    dados = coletar()
    embutido = json.dumps(dados, ensure_ascii=False).replace("</", "<\\/")
    (WEB / "js" / "dados-exemplo.js").write_text(
        "// Dados fictícios gerados por scripts/exportar_demo.py: usados só quando a API não responde.\n"
        f"window.__DADOS_EXEMPLO__ = {embutido};\n", encoding="utf-8")

    html = (WEB / "index.html").read_text(encoding="utf-8")
    css = (WEB / "css" / "estilo.css").read_text(encoding="utf-8")
    js = (WEB / "js" / "app.js").read_text(encoding="utf-8")
    html = html.replace('<link rel="stylesheet" href="css/estilo.css">', f"<style>\n{css}</style>")
    html = html.replace('<script src="js/dados-exemplo.js"></script>\n', "")
    html = html.replace('<script src="js/app.js"></script>', f"<script>\n{js}</script>")
    for arq in (WEB / "assets").glob("*.png"):
        html = html.replace(f"assets/{arq.name}", _data_uri(arq))
    html = html.replace("<script>/*__DEMO__*/</script>", f"<script>window.__DEMO__ = {embutido};</script>")
    destino = WEB / "demo.html"
    destino.write_text(html, encoding="utf-8")
    return destino


if __name__ == "__main__":
    print(f"Demonstração gerada em {gerar()}")
