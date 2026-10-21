"""Regras do bip: colaborador ativo, gravação, eventos para a tela e calibração do leitor."""

import secrets
import threading
from collections import deque
from collections.abc import Callable
from datetime import date, datetime

from bip.db import Repo
from bip.detector import Scan

LIMIAR_PADRAO_MS = 50.0
LIMIAR_CALIBRACAO_MS = 300.0
AMOSTRAS_CALIBRACAO = 3
LIMIAR_MIN_MS = 50
LIMIAR_MAX_MS = 80
MAX_EVENTOS = 200


class Servico:
    def __init__(self, repo: Repo, relogio: Callable[[], datetime] = datetime.now):
        self._repo = repo
        # Muda a cada início do programa: a tela percebe que ele caiu e voltou.
        self.sessao = secrets.token_hex(8)
        self._relogio = relogio
        self._lock = threading.Lock()
        self._eventos: deque[dict] = deque(maxlen=MAX_EVENTOS)
        self._ultimo_id = 0
        self._amostras: list[float] = []
        self._calibrando = self.precisa_calibrar()
        # Em memória: limiar_ms() é lido a cada tecla, sem ir ao SQLite.
        self._limiar = float(repo.get_config("limiar_ms", str(LIMIAR_PADRAO_MS)))
        repo.del_config("colaborador_ativo")

    # Colaborador ativo

    def ativo(self) -> dict | None:
        # Sem lock: processar_scan chama daqui já segurando o lock (que não é reentrante).
        valor = self._repo.get_config("colaborador_ativo")
        return self._repo.obter_colaborador(int(valor)) if valor else None

    def definir_ativo(self, colaborador_id: int | None) -> None:
        with self._lock:
            if colaborador_id is None:
                self._repo.del_config("colaborador_ativo")
                return
            colaborador = self._repo.obter_colaborador(colaborador_id)
            if colaborador is None or not colaborador["ativo"]:
                raise ValueError("Colaborador inexistente ou inativo")
            self._repo.set_config("colaborador_ativo", str(colaborador_id))

    def desativar_colaborador(self, id: int) -> dict:
        with self._lock:
            colaborador = self._repo.atualizar_colaborador(id, ativo=False)
            ativo = self.ativo()
            if ativo and ativo["id"] == id:
                self._repo.del_config("colaborador_ativo")
            return colaborador

    def hoje(self) -> date:
        return self._relogio().date()

    # Calibração

    def precisa_calibrar(self) -> bool:
        return self._repo.get_config("limiar_ms") is None

    def limiar_ms(self) -> float:
        if self._calibrando:
            return LIMIAR_CALIBRACAO_MS
        return self._limiar

    def iniciar_calibracao(self) -> None:
        with self._lock:
            self._amostras = []
            self._calibrando = True

    def cancelar_calibracao(self) -> None:
        with self._lock:
            self._amostras = []
            self._calibrando = False

    def calibracao(self) -> dict:
        return {"calibrando": self._calibrando, "amostras": len(self._amostras), "total": AMOSTRAS_CALIBRACAO,
                "limiar_ms": self.limiar_ms()}

    def _amostra(self, intervalo_ms: float) -> None:
        self._amostras.append(intervalo_ms)
        if len(self._amostras) >= AMOSTRAS_CALIBRACAO:
            limiar = min(max(round(max(self._amostras) * 2), LIMIAR_MIN_MS), LIMIAR_MAX_MS)
            self._repo.set_config("limiar_ms", str(limiar))
            self._limiar = float(limiar)
            self._amostras = []
            self._calibrando = False

    # Bip

    def processar_scan(self, scan: Scan) -> dict:
        with self._lock:
            if self._calibrando:
                self._amostra(scan.max_intervalo_ms)
            ativo = self.ativo()
            if ativo and not ativo["ativo"]:
                ativo = None
            criado, registro = self._repo.registrar(scan.codigo, ativo["id"] if ativo else None, self._relogio())
            nome = registro["colaborador_nome"] or "Sem colaborador"
            if not criado:
                tipo, mensagem = "repetido", f"Já registrado no {nome}"
            elif registro["colaborador_id"] is None:
                tipo, mensagem = "sem_colaborador", "Sem colaborador"
            else:
                tipo, mensagem = "novo", nome
            self._ultimo_id += 1
            evento = {"id": self._ultimo_id, "tipo": tipo, "rastreio": scan.codigo, "registro": registro,
                      "mensagem": mensagem}
            self._eventos.append(evento)
            return evento

    def eventos_desde(self, ultimo_id: int) -> list[dict]:
        with self._lock:
            return [e for e in self._eventos if e["id"] > ultimo_id]

    def ultimo_evento_id(self) -> int:
        return self._ultimo_id
