"""Intervalos de data dos relatórios (dia, semana de segunda a domingo, mês)."""

from datetime import date, datetime, timedelta


def periodo(nome: str, hoje: date) -> tuple[datetime, datetime]:
    if nome == "dia":
        inicio = hoje
        fim = hoje + timedelta(days=1)
    elif nome == "semana":
        inicio = hoje - timedelta(days=hoje.weekday())
        fim = inicio + timedelta(days=7)
    elif nome == "mes":
        inicio = hoje.replace(day=1)
        fim = date(inicio.year + 1, 1, 1) if inicio.month == 12 else date(inicio.year, inicio.month + 1, 1)
    else:
        raise ValueError(f"Período inválido: {nome}")
    return datetime.combine(inicio, datetime.min.time()), datetime.combine(fim, datetime.min.time())
