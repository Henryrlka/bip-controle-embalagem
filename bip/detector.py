"""Separa bips do leitor (digitação muito rápida + Enter) da digitação humana."""

from dataclasses import dataclass

MIN_LEN = 10
MAX_LEN = 30


@dataclass(frozen=True)
class Scan:
    codigo: str
    max_intervalo_ms: float


def _valido(texto: str) -> bool:
    return MIN_LEN <= len(texto) <= MAX_LEN and texto.isascii() and texto.isalnum()


class ScanDetector:
    def __init__(self, limiar_ms: float):
        self.limiar_ms = limiar_ms
        self._buffer: list[str] = []
        self._ultimo_t = 0.0
        self._maior = 0.0

    def _zerar(self) -> None:
        self._buffer = []
        self._maior = 0.0

    def alimentar(self, tecla: str, t_ms: float) -> Scan | None:
        if tecla == "MOD":
            return None
        if tecla == "OUTRA":
            self._zerar()
            return None

        intervalo = t_ms - self._ultimo_t
        if tecla == "ENTER":
            texto = "".join(self._buffer)
            maior = max(self._maior, intervalo)
            self._zerar()
            if texto and intervalo <= self.limiar_ms and _valido(texto):
                return Scan(texto.upper(), maior)
            return None

        if self._buffer and intervalo > self.limiar_ms:
            self._zerar()
        if self._buffer:
            self._maior = max(self._maior, intervalo)
        self._buffer.append(tecla)
        self._ultimo_t = t_ms
        return None
