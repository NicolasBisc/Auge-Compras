"""
Dados fictícios da demonstração — determinísticos (semente fixa).

Simula ~15 meses de operação da Auge dia a dia: clientes novos e renovações de
certificado gerando alocações, uma pessoa comprando quando o saldo baixa, notas
chegando depois do lead time. Em seguida planta os cenários que cada decisão
precisa demonstrar (alta de preço, entrega parcial, excesso, cold start...).

Tudo é inventado: fornecedores, clientes, preços e CNPJs. Os CNPJs têm
dígito verificador propositalmente inválido para nunca coincidir com uma empresa real.

Rodar:  python -m app.seed
"""
import random
from datetime import date, timedelta
from pathlib import Path

from app import config, db
from app.motor.conciliacao import digito_verificador_chave
from app.motor.projecao import somar_meses

RAIZ = Path(__file__).resolve().parent.parent
PASTA_NOTAS = RAIZ / "dados" / "notas_exemplo"

HOJE = config.hoje()
INICIO = date(2025, 7, 1)
PARA_DE_COMPRAR = date(2026, 9, 19)       # depois disso, só os pedidos planejados
TOKEN_PARA_DE_COMPRAR = date(2026, 7, 1)   # deixa a capacidade de token baixar

DESTINATARIO = ("90121212000100", "Auge Contabilidade (demonstração)")

FORNECEDORES = [  # id, nome, cnpj, lead time
    (1, "Certisul AR", "90111222000100", 2),
    (2, "Vértice Certificação Digital", "90333444000100", 3),
    (3, "Tokenline Distribuidora", "90555666000100", 12),
    (4, "Nexo Software Fiscal", "90777888000100", 4),
    (5, "Serra Tributária Consultoria", "90999000000100", 5),
]

SERVICOS = [  # id, nome, categoria, unidade, tipo, validade, mínimo
    (1, "Voucher e-CNPJ A1", "Certificado digital", "voucher", "discreta", 12, None),
    (2, "Voucher e-CPF A1", "Certificado digital", "voucher", "discreta", 12, None),
    (3, "Voucher e-CNPJ A3", "Certificado digital", "voucher", "discreta", 36, None),
    (4, "Token criptográfico USB", "Mídia de certificado", "unidade", "discreta", None, 4),
    (5, "Certificado em nuvem", "Certificado digital", "voucher", "discreta", 12, 5),
    (6, "Licença do emissor de NFS-e", "Software", "licença", "discreta", 12, None),
    (7, "Horas de consultoria tributária", "Consultoria", "hora", "discreta", None, None),
]

# Demanda nova por dia (eventos), probabilidade de renovação e quantidades possíveis
DEMANDA = {
    1: {"lam": 0.36, "renova": 0.85, "qtd": [1]},
    2: {"lam": 0.20, "renova": 0.80, "qtd": [1, 1, 1, 2]},
    3: {"lam": 0.06, "renova": 0.0, "qtd": [1]},
    4: {"lam": 0.12, "renova": 0.0, "qtd": [1]},
    6: {"lam": 0.14, "renova": 0.90, "qtd": [1]},
    7: {"lam": 0.12, "renova": 0.0, "qtd": [2, 3, 4, 4, 6, 8]},
}
SAZONAL = {  # multiplicador por mês; e-CPF sobe na temporada do imposto de renda
    1: {12: 1.2, 1: 1.1, 3: 1.2},
    2: {3: 2.5, 4: 2.5, 5: 1.8},
}

SEGMENTOS = {
    "Saúde": ["Clínica", "Consultório", "Odontologia", "Fisioterapia", "Laboratório", "Psicologia"],
    "Construção civil": ["Construtora", "Engenharia", "Reformas", "Arquitetura", "Revestimentos"],
    "Comércio": ["Empório", "Mercearia", "Ateliê", "Madeireira", "Pet Shop", "Papelaria"],
    "Serviços": ["Studio", "Auto Center", "Transportes", "Soluções Digitais", "Escola", "Academia"],
    "Alimentação": ["Restaurante", "Padaria", "Cafeteria", "Cervejaria", "Doceria"],
}
NOMES = ["Aurora", "Horizonte", "Pinhal", "Serra Azul", "Trigo Dourado", "Vale Verde", "Araucária",
         "Campo Sereno", "Pedra Angular", "Rio Claro", "Sol Nascente", "Bela Vista", "Nova Era",
         "Ipê Roxo", "Colina", "Mirante", "Recanto", "Vila Rica", "Prisma", "Alvorada", "Cedro",
         "Jardim", "Laguna", "Monte Alto", "Oásis", "Primavera", "Quintal", "Raiz", "Sabiá",
         "Terra Firme", "Umuarama", "Vértebra", "Xisto", "Zênite", "Âncora", "Brisa", "Carvalho",
         "Duna", "Estrela Guia", "Farol"]


def preco(servico_id: int, fornecedor_id: int, d: date, rng: random.Random) -> float:
    if (servico_id, fornecedor_id) == (1, 1):
        return 92.00 if d < date(2026, 3, 1) else 94.50            # +2,7%: reajuste normal
    if (servico_id, fornecedor_id) == (1, 2):
        return 86.90                                               # estável e mais barato
    if (servico_id, fornecedor_id) == (2, 1):
        return 69.90 if d < date(2026, 7, 1) else 74.90            # +7,2%: vira nota, depois patamar
    if (servico_id, fornecedor_id) == (3, 1):
        return 189.00
    if (servico_id, fornecedor_id) == (4, 3):                      # importado, segue o dólar: oscila ±6%
        oscilacao = [0.02, -0.05, 0.06, -0.03, 0.04, -0.06, 0.05, -0.02][d.toordinal() % 8]
        return round(62.00 * (1 + oscilacao), 2)
    if (servico_id, fornecedor_id) == (4, 2):
        return 73.90                                               # mais caro, mas entrega em 3 dias
    if (servico_id, fornecedor_id) == (5, 2):
        return 129.00
    if (servico_id, fornecedor_id) == (6, 4):
        return 49.00
    if (servico_id, fornecedor_id) == (7, 5):
        return 180.00
    raise ValueError((servico_id, fornecedor_id))


def fornecedor_de(servico_id: int, rng: random.Random) -> int:
    return {1: 2 if rng.random() < 0.5 else 1, 2: 1, 3: 1, 4: 3, 5: 2, 6: 4, 7: 5}[servico_id]


def gerar_clientes(rng: random.Random, n: int = 240) -> list[tuple[str, str]]:
    vistos, saida = set(), []
    while len(saida) < n:
        seg = rng.choice(list(SEGMENTOS))
        nome = f"{rng.choice(SEGMENTOS[seg])} {rng.choice(NOMES)}"
        if nome not in vistos:
            vistos.add(nome)
            saida.append((nome, seg))
    return saida


def poisson(lam: float, rng: random.Random) -> int:
    # Knuth: suficiente para lam pequeno
    limite, k, p = 2.718281828459045 ** (-lam), 0, 1.0
    while True:
        p *= rng.random()
        if p <= limite:
            return k
        k += 1


def chave_acesso(cnpj: str, d: date, numero: int, rng: random.Random) -> str:
    base = f"41{d:%y%m}{cnpj}55001{numero:09d}1{rng.randrange(10**7, 10**8)}"
    return base + str(digito_verificador_chave(base))


def xml_nota(chave, numero, emissao: date, emitente, itens) -> str:
    """Subconjunto do layout NF-e 4.00: o suficiente para conciliar quantidade e preço."""
    dets = "".join(f"""
      <det nItem="{i}">
        <prod>
          <cProd>{it['cprod']}</cProd>
          <xProd>{it['descricao']}</xProd>
          <uCom>{it['unidade']}</uCom>
          <qCom>{it['qtd']:.4f}</qCom>
          <vUnCom>{it['unit']:.10f}</vUnCom>
          <vProd>{round(it['qtd'] * it['unit'], 2):.2f}</vProd>
          <xPed>{it['pedido']}</xPed>
        </prod>
      </det>""" for i, it in enumerate(itens, 1))
    total = sum(round(it["qtd"] * it["unit"], 2) for it in itens)
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<!-- Nota fiscal FICTÍCIA para demonstração. Subconjunto do layout NF-e 4.00. -->
<nfeProc xmlns="http://www.portalfiscal.inf.br/nfe" versao="4.00">
  <NFe>
    <infNFe Id="NFe{chave}" versao="4.00">
      <ide><nNF>{numero}</nNF><dhEmi>{emissao.isoformat()}T09:30:00-03:00</dhEmi></ide>
      <emit><CNPJ>{emitente[0]}</CNPJ><xNome>{emitente[1]}</xNome></emit>
      <dest><CNPJ>{DESTINATARIO[0]}</CNPJ><xNome>{DESTINATARIO[1]}</xNome></dest>{dets}
      <total><ICMSTot><vNF>{total:.2f}</vNF></ICMSTot></total>
    </infNFe>
  </NFe>
  <protNFe><infProt><chNFe>{chave}</chNFe></infProt></protNFe>
</nfeProc>
"""


def simular(rng: random.Random):
    """Devolve pedidos, entregas e alocações da operação simulada."""
    clientes = gerar_clientes(rng)
    lead = {f[0]: f[3] for f in FORNECEDORES}
    capac = {s[0]: 0.0 for s in SERVICOS}
    pedidos, entregas, alocs = [], [], []
    renovar: dict[date, list] = {}
    proximo_novo_cnpj = 0
    com_licenca: set[int] = set()

    def estimativa(sid: int, d: date) -> float:
        janela = [a for a in alocs if a["servico_id"] == sid and d - timedelta(days=60) < a["data"] <= d]
        dias = min(60, (d - INICIO).days)
        base = DEMANDA[sid]["lam"] * sum(DEMANDA[sid]["qtd"]) / len(DEMANDA[sid]["qtd"])
        return max(base, sum(a["quantidade"] for a in janela) / dias) if dias >= 20 else base

    d = INICIO
    while d <= HOJE:
        # 1. notas que chegam hoje
        for e in [e for e in entregas if e["data"] == d]:
            capac[e["servico_id"]] += e["quantidade"]

        # 2. demanda do dia: renovações vencendo + clientes novos
        demanda = list(renovar.pop(d, []))
        for sid, dem in DEMANDA.items():
            fator = SAZONAL.get(sid, {}).get(d.month, 1.0)
            for _ in range(poisson(dem["lam"] * fator, rng)):
                if sid == 1:
                    if proximo_novo_cnpj >= len(clientes):
                        continue
                    cli = proximo_novo_cnpj
                    proximo_novo_cnpj += 1
                elif sid == 6:
                    livres = [i for i in range(len(clientes)) if i not in com_licenca]
                    if not livres:
                        continue
                    cli = rng.choice(livres)
                else:
                    cli = rng.randrange(len(clientes))
                demanda.append((sid, cli, rng.choice(dem["qtd"])))

        # 3. aloca se houver capacidade; senão o cliente é perdido
        for sid, cli, q in demanda:
            if capac[sid] >= q:
                capac[sid] -= q
                alocs.append({"servico_id": sid, "cliente": cli, "quantidade": q, "data": d})
                if sid == 6:
                    com_licenca.add(cli)
                validade = next(s[5] for s in SERVICOS if s[0] == sid)
                if validade and rng.random() < DEMANDA[sid]["renova"]:
                    quando = somar_meses(d, validade) + timedelta(days=rng.randint(-10, 3))
                    renovar.setdefault(quando, []).append((sid, cli, q))

        # 4. a pessoa que compra olha o saldo e decide
        for sid in DEMANDA:
            parar = TOKEN_PARA_DE_COMPRAR if sid == 4 else PARA_DE_COMPRAR
            if d >= parar:
                continue
            transito = sum(e["quantidade"] for e in entregas if e["servico_id"] == sid and e["data"] > d)
            r = estimativa(sid, d)
            fid = fornecedor_de(sid, rng)
            if sid == 7:
                gatilho, qtd = 10, 20
            else:
                gatilho = r * (lead[fid] + 10)
                qtd = max(5, 5 * -(-int(r * 21 + 0.999) // 5))   # lotes de ~3 semanas
            if capac[sid] + transito <= gatilho:
                p = {"servico_id": sid, "fornecedor_id": fid, "quantidade": float(qtd),
                     "preco": preco(sid, fid, d, rng), "data": d}
                pedidos.append(p)
                chegada = d + timedelta(days=max(1, lead[fid] + rng.choice([-1, 0, 0, 1, 2])))
                if qtd >= 10 and rng.random() < 0.08:        # entrega em duas notas (1 pedido : N notas)
                    q1 = float(round(qtd * 0.6))
                    entregas.append({"pedido": p, "servico_id": sid, "quantidade": q1, "data": chegada})
                    entregas.append({"pedido": p, "servico_id": sid, "quantidade": qtd - q1,
                                     "data": chegada + timedelta(days=rng.randint(2, 4))})
                else:
                    entregas.append({"pedido": p, "servico_id": sid, "quantidade": float(qtd), "data": chegada})
        d += timedelta(days=1)

    entregas = [e for e in entregas if e["data"] <= HOJE]
    return clientes, pedidos, entregas, alocs


def popular(conn) -> dict:
    rng = random.Random(20260928)
    db.zerar(conn)
    for f in FORNECEDORES:
        db.inserir(conn, "fornecedor", id=f[0], nome=f[1], cnpj=f[2], lead_time_dias=f[3])
    for s in SERVICOS:
        db.inserir(conn, "servico", id=s[0], nome=s[1], categoria=s[2], unidade=s[3],
                   tipo_quantidade=s[4], validade_meses=s[5], estoque_minimo=s[6])

    clientes, pedidos, entregas, alocs = simular(rng)
    for i, (nome, seg) in enumerate(clientes, 1):
        db.inserir(conn, "cliente", id=i, nome=nome, segmento=seg)

    # --- cenários planejados (o que cada decisão precisa mostrar) -----------------
    cenarios = [
        # tag,             serviço, fornecedor, qtd, preço, data do pedido
        ("ok_arredondamento", 1, 1, 20, 94.50, date(2026, 9, 24)),
        ("preco_divergente",  1, 2, 15, 102.50, date(2026, 9, 22)),   # também é a alta de +18% (Decisão 3)
        ("entrega_parcial",   2, 1, 10, 74.90, date(2026, 9, 25)),
        ("excesso",           6, 4, 10, 49.00, date(2026, 9, 24)),
        ("diferenca_pequena", 3, 1, 3, 189.00, date(2026, 9, 23)),
        ("recorrente",        7, 5, 20, 180.00, date(2026, 9, 21)),
        ("emitente_errado",   2, 1, 5, 74.90, date(2026, 9, 26)),
        ("token_atrasado",    4, 3, 10, 69.50, date(2026, 9, 5)),     # +8%, mas dentro da oscilação
        ("nuvem_inicial",     5, 2, 6, 129.00, date(2026, 9, 14)),
        ("token_urgente_1",   4, 2, 5, 73.90, date(2026, 5, 28)),     # compras de emergência de token
        ("token_urgente_2",   4, 2, 5, 73.90, date(2026, 6, 24)),     # em fornecedor mais rápido
        ("horas_historico",   7, 5, 20, 180.00, date(2026, 7, 20)),
    ]
    for tag, sid, fid, q, pr, dt in cenarios:
        pedidos.append({"servico_id": sid, "fornecedor_id": fid, "quantidade": float(q), "preco": pr,
                        "data": dt, "tag": tag})
    for tag in ("token_urgente_1", "token_urgente_2", "horas_historico"):
        t = next(p for p in pedidos if p.get("tag") == tag)
        entregas.append({"pedido": t, "servico_id": t["servico_id"], "quantidade": t["quantidade"],
                         "data": t["data"] + timedelta(days=3 if t["servico_id"] == 4 else 5)})
    # uma construtora renovou o A3 de vários sócios de uma vez: a capacidade de token despenca
    construtora = next(i for i, c in enumerate(clientes) if c[0].startswith("Construtora"))
    alocs.append({"servico_id": 4, "cliente": construtora, "quantidade": 5, "data": date(2026, 9, 10)})
    alocs.append({"servico_id": 4, "cliente": construtora, "quantidade": 4, "data": date(2026, 9, 18)})
    nuvem = next(p for p in pedidos if p.get("tag") == "nuvem_inicial")
    entregas.append({"pedido": nuvem, "servico_id": 5, "quantidade": 6.0, "data": date(2026, 9, 16)})
    for dia in (17, 22, 25):  # três alocações: pouco demais para projetar (cold start)
        alocs.append({"servico_id": 5, "cliente": rng.randrange(len(clientes)), "quantidade": 1,
                      "data": date(2026, 9, dia)})

    # --- grava pedidos em ordem de data, com código sequencial por ano ---------------
    pedidos.sort(key=lambda p: (p["data"], p["servico_id"]))
    seq: dict[int, int] = {}
    for p in pedidos:
        seq[p["data"].year] = seq.get(p["data"].year, 0) + 1
        p["codigo"] = f"AQ-{p['data'].year}-{seq[p['data'].year]:04d}"
        p["id"] = db.inserir(conn, "aquisicao", codigo=p["codigo"], servico_id=p["servico_id"],
                             fornecedor_id=p["fornecedor_id"], quantidade=p["quantidade"],
                             preco_unitario=p["preco"], data_pedido=p["data"].isoformat())

    # --- notas históricas: 1 por entrega; 10% com arredondamento no unitário ---------
    forn = {f[0]: f for f in FORNECEDORES}
    numero = {f[0]: 1000 for f in FORNECEDORES}
    # diferenças pequenas da Serra nas duas últimas entregas de horas da janela (cenário de acúmulo)
    janela = HOJE - timedelta(days=config.JANELA_ACUMULO_DIAS - 5)
    horas = [e for e in sorted(entregas, key=lambda e: e["data"])
             if e["servico_id"] == 7 and e["data"] >= janela]
    extra_por_entrega = {id(e): x for e, x in zip(horas[-2:], (1.10, 1.25))}
    for e in sorted(entregas, key=lambda e: e["data"]):
        p = e["pedido"]
        f = forn[p["fornecedor_id"]]
        numero[f[0]] += 1
        unit, status_preco = p["preco"], "conforme"
        if rng.random() < 0.10:
            unit = round(p["preco"] - 0.001, 4)  # até 10 casas no unitário da nota
        if id(e) in extra_por_entrega:
            unit, status_preco = round(p["preco"] + extra_por_entrega[id(e)], 2), "menor"
        total = round(e["quantidade"] * unit, 2)
        dif = round(total - e["quantidade"] * p["preco"], 2)
        chave = chave_acesso(f[2], e["data"], numero[f[0]], rng)
        nid = db.inserir(conn, "nota_fiscal", chave=chave, numero=str(numero[f[0]]), emitente_cnpj=f[2],
                         emitente_nome=f[1], data_emissao=e["data"].isoformat(),
                         data_recebimento=e["data"].isoformat(),
                         status="atencao" if status_preco == "menor" else "ok", xml=None)
        db.inserir(conn, "nota_item", nota_id=nid, aquisicao_id=p["id"], quantidade=e["quantidade"],
                   preco_unitario=unit, valor_total=total, status="atencao" if status_preco == "menor" else "ok",
                   status_preco=status_preco, diferenca_valor=dif)

    for a in sorted(alocs, key=lambda a: a["data"]):
        db.inserir(conn, "alocacao", servico_id=a["servico_id"], cliente_id=a["cliente"] + 1,
                   quantidade=a["quantidade"], data=a["data"].isoformat())
    conn.commit()

    arquivos = gerar_notas_exemplo({p["tag"]: p for p in pedidos if p.get("tag")}, forn, rng)
    return {"clientes": len(clientes), "aquisicoes": len(pedidos), "notas": len(entregas),
            "alocacoes": len(alocs), "notas_exemplo": arquivos}


def gerar_notas_exemplo(por_tag: dict, forn: dict, rng: random.Random) -> list[str]:
    """Um XML por cenário da Decisão 4. Ficam em dados/notas_exemplo/ para upload."""
    PASTA_NOTAS.mkdir(parents=True, exist_ok=True)
    for antigo in PASTA_NOTAS.glob("*.xml"):
        antigo.unlink()
    nomes = {1: "Voucher certificado digital e-CNPJ A1", 2: "Voucher certificado digital e-CPF A1",
             3: "Voucher certificado digital e-CNPJ A3", 6: "Licença anual emissor NFS-e",
             7: "Consultoria tributária (horas)"}
    cprod = {1: "A1-CNPJ", 2: "A1-CPF", 3: "A3-CNPJ", 6: "EMISSOR-NFSE", 7: "CONS-HORA"}
    unid = {1: "UN", 2: "UN", 3: "UN", 6: "UN", 7: "H"}

    def item(p, qtd=None, unit=None, pedido=None):
        return {"cprod": cprod[p["servico_id"]], "descricao": nomes[p["servico_id"]],
                "unidade": unid[p["servico_id"]], "qtd": qtd if qtd is not None else p["quantidade"],
                "unit": unit if unit is not None else p["preco"], "pedido": pedido or p["codigo"]}

    planos = [
        ("01_conforme_arredondamento.xml", "ok_arredondamento", None, lambda p: [item(p, unit=94.499)]),
        ("02_preco_divergente.xml", "preco_divergente", None, lambda p: [item(p, unit=105.00)]),
        ("03_entrega_parcial.xml", "entrega_parcial", None, lambda p: [item(p, qtd=6)]),
        ("04_quantidade_excedente.xml", "excesso", None, lambda p: [item(p, qtd=12)]),
        ("05_diferenca_pequena.xml", "diferenca_pequena", None, lambda p: [item(p, unit=189.50)]),
        ("06_diferencas_recorrentes.xml", "recorrente", None, lambda p: [item(p, unit=180.30)]),
        ("07_emitente_diferente.xml", "emitente_errado", 2, lambda p: [item(p)]),
        ("08_pedido_inexistente.xml", "ok_arredondamento", None,
         lambda p: [item(p, qtd=5, unit=94.50, pedido="AQ-2026-9999")]),
    ]
    feitos = []
    for i, (nome, tag, emitente_forcado, montar) in enumerate(planos, 1):
        p = por_tag[tag]
        f = forn[emitente_forcado or p["fornecedor_id"]]
        numero = 9000 + i
        chave = chave_acesso(f[2], HOJE, numero, rng)
        (PASTA_NOTAS / nome).write_text(xml_nota(chave, numero, HOJE - timedelta(days=1), (f[2], f[1]), montar(p)),
                                        encoding="utf-8")
        feitos.append(nome)
    return feitos


if __name__ == "__main__":
    conn = db.conectar()
    r = popular(conn)
    print(f"Dados fictícios gerados em {db.CAMINHO_PADRAO.name}: {r['clientes']} clientes, "
          f"{r['aquisicoes']} aquisições, {r['notas']} notas, {r['alocacoes']} alocações.")
    print(f"Notas de exemplo para testar a conciliação: dados/notas_exemplo/ ({len(r['notas_exemplo'])} arquivos)")
