"""Formatação em português do Brasil para todo texto que o motor escreve."""

PLURAIS = {"voucher": "vouchers", "unidade": "unidades", "licença": "licenças", "hora": "horas"}


def num(v: float, casas: int = 1) -> str:
    """4.5 → '4,5'; 12.0 → '12'; 1234.5 → '1.234,5'."""
    s = f"{v:,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")
    if "," in s:
        s = s.rstrip("0").rstrip(",")
    return s


def brl(v: float) -> str:
    s = f"{abs(v):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{'-' if v < 0 else ''}R$ {s}"


def pct(v: float, sinal: bool = True) -> str:
    s = f"{v * 100:{'+' if sinal else ''}.1f}".replace(".", ",")
    return s.rstrip("0").rstrip(",") + "%" if s.endswith(",0") else s + "%"


def unidade(nome: str, qtd: float) -> str:
    return nome if abs(qtd) == 1 else PLURAIS.get(nome, nome + "s")
