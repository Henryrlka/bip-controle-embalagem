"""Acesso ao banco SQLite: colaboradores, registros de bip e configuração."""

import sqlite3
import threading
from datetime import datetime

CORES = ["#2563EB", "#16A34A", "#EA580C", "#9333EA", "#DB2777", "#0891B2", "#CA8A04", "#92400E"]
SONS = [440, 554, 659, 784, 880, 988, 1175, 1319]
SEM_COLABORADOR_COR = "#DC2626"

SCHEMA = """
CREATE TABLE IF NOT EXISTS colaboradores (
    id INTEGER PRIMARY KEY,
    nome TEXT NOT NULL UNIQUE COLLATE NOCASE,
    cor TEXT,
    som_hz INTEGER,
    ativo INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS registros (
    id INTEGER PRIMARY KEY,
    rastreio TEXT NOT NULL UNIQUE,
    colaborador_id INTEGER NULL REFERENCES colaboradores(id),
    bipado_em TEXT NOT NULL,
    erro INTEGER NOT NULL DEFAULT 0,
    erro_obs TEXT
);
CREATE INDEX IF NOT EXISTS idx_registros_bipado_em ON registros(bipado_em);
CREATE TABLE IF NOT EXISTS config (
    chave TEXT PRIMARY KEY,
    valor TEXT
);
"""

SELECT_REGISTRO = """
SELECT r.id, r.rastreio, r.colaborador_id, c.nome AS colaborador_nome,
       c.cor AS colaborador_cor, r.bipado_em, r.erro, r.erro_obs
FROM registros r LEFT JOIN colaboradores c ON c.id = r.colaborador_id
"""


class NomeDuplicado(Exception):
    pass


def _colaborador(row) -> dict:
    return {"id": row["id"], "nome": row["nome"], "cor": row["cor"],
            "som_hz": row["som_hz"], "ativo": bool(row["ativo"])}


def _registro(row) -> dict:
    d = dict(row)
    d["erro"] = bool(d["erro"])
    return d


def _nome_limpo(nome: str) -> str:
    nome = nome.strip()
    if not nome:
        raise ValueError("Nome vazio")
    return nome


class Repo:
    def __init__(self, caminho: str):
        self._con = sqlite3.connect(str(caminho), check_same_thread=False)
        self._con.row_factory = sqlite3.Row
        self._lock = threading.Lock()
        with self._lock:
            self._con.executescript(SCHEMA)
            self._con.commit()

    def _q(self, sql: str, params=()) -> list:
        with self._lock:
            return self._con.execute(sql, params).fetchall()

    def _exec(self, sql: str, params=()) -> sqlite3.Cursor:
        with self._lock:
            cur = self._con.execute(sql, params)
            self._con.commit()
            return cur

    # Colaboradores

    def criar_colaborador(self, nome: str) -> dict:
        nome = _nome_limpo(nome)
        total = self._q("SELECT COUNT(*) FROM colaboradores")[0][0]
        try:
            cur = self._exec(
                "INSERT INTO colaboradores (nome, cor, som_hz) VALUES (?, ?, ?)",
                (nome, CORES[total % 8], SONS[total % 8]))
        except sqlite3.IntegrityError:
            raise NomeDuplicado(nome)
        return self.obter_colaborador(cur.lastrowid)

    def atualizar_colaborador(self, id: int, nome: str | None = None, cor: str | None = None,
                              ativo: bool | None = None) -> dict:
        try:
            if nome is not None:
                self._exec("UPDATE colaboradores SET nome = ? WHERE id = ?", (_nome_limpo(nome), id))
        except sqlite3.IntegrityError:
            raise NomeDuplicado(nome)
        if cor is not None:
            self._exec("UPDATE colaboradores SET cor = ? WHERE id = ?", (cor, id))
        if ativo is not None:
            self._exec("UPDATE colaboradores SET ativo = ? WHERE id = ?", (int(ativo), id))
        return self.obter_colaborador(id)

    def obter_colaborador(self, id: int) -> dict | None:
        rows = self._q("SELECT * FROM colaboradores WHERE id = ?", (id,))
        return _colaborador(rows[0]) if rows else None

    def listar_colaboradores(self, incluir_inativos: bool = False) -> list[dict]:
        filtro = "" if incluir_inativos else "WHERE ativo = 1"
        return [_colaborador(r) for r in
                self._q(f"SELECT * FROM colaboradores {filtro} ORDER BY nome COLLATE NOCASE")]

    # Registros

    def obter_registro(self, id: int) -> dict | None:
        rows = self._q(SELECT_REGISTRO + "WHERE r.id = ?", (id,))
        return _registro(rows[0]) if rows else None

    def registrar(self, rastreio: str, colaborador_id: int | None, quando: datetime) -> tuple[bool, dict]:
        try:
            cur = self._exec(
                "INSERT INTO registros (rastreio, colaborador_id, bipado_em) VALUES (?, ?, ?)",
                (rastreio, colaborador_id, quando.isoformat(timespec="seconds")))
        except sqlite3.IntegrityError:
            existente = self._q(SELECT_REGISTRO + "WHERE r.rastreio = ?", (rastreio,))
            return False, _registro(existente[0])
        return True, self.obter_registro(cur.lastrowid)

    def mover(self, registro_id: int, colaborador_id: int | None) -> dict:
        self._exec("UPDATE registros SET colaborador_id = ? WHERE id = ?", (colaborador_id, registro_id))
        return self.obter_registro(registro_id)

    def excluir(self, registro_id: int) -> None:
        self._exec("DELETE FROM registros WHERE id = ?", (registro_id,))

    def marcar_erro(self, registro_id: int, obs: str | None) -> dict:
        self._exec("UPDATE registros SET erro = 1, erro_obs = ? WHERE id = ?", (obs or None, registro_id))
        return self.obter_registro(registro_id)

    def desmarcar_erro(self, registro_id: int) -> dict:
        self._exec("UPDATE registros SET erro = 0, erro_obs = NULL WHERE id = ?", (registro_id,))
        return self.obter_registro(registro_id)

    def buscar(self, trecho: str, limite: int = 50) -> list[dict]:
        padrao = "%" + trecho.strip().upper().replace("%", "").replace("_", "") + "%"
        rows = self._q(SELECT_REGISTRO + "WHERE r.rastreio LIKE ? ORDER BY r.bipado_em DESC, r.id DESC LIMIT ?",
                       (padrao, limite))
        return [_registro(r) for r in rows]

    def ultimos(self, n: int = 20) -> list[dict]:
        return [_registro(r) for r in self._q(SELECT_REGISTRO + "ORDER BY r.id DESC LIMIT ?", (n,))]

    # Relatórios

    def resumo(self, inicio: datetime, fim: datetime) -> list[dict]:
        rows = self._q(
            """SELECT r.colaborador_id, c.nome, c.cor, COUNT(*) AS pacotes, SUM(r.erro) AS erros
               FROM registros r LEFT JOIN colaboradores c ON c.id = r.colaborador_id
               WHERE r.bipado_em >= ? AND r.bipado_em < ?
               GROUP BY r.colaborador_id ORDER BY pacotes DESC, c.nome""",
            (inicio.isoformat(timespec="seconds"), fim.isoformat(timespec="seconds")))
        linhas = []
        for r in rows:
            sem = r["colaborador_id"] is None
            linhas.append({
                "colaborador_id": r["colaborador_id"],
                "nome": "Sem colaborador" if sem else r["nome"],
                "cor": SEM_COLABORADOR_COR if sem else r["cor"],
                "pacotes": r["pacotes"],
                "erros": r["erros"],
                "taxa": r["erros"] / r["pacotes"] if r["pacotes"] else 0.0,
            })
        return linhas

    def listar_registros(self, inicio: datetime, fim: datetime, colaborador_id: int | None = None,
                         sem_colaborador: bool = False) -> list[dict]:
        sql = SELECT_REGISTRO + "WHERE r.bipado_em >= ? AND r.bipado_em < ?"
        params: list = [inicio.isoformat(timespec="seconds"), fim.isoformat(timespec="seconds")]
        if sem_colaborador:
            sql += " AND r.colaborador_id IS NULL"
        elif colaborador_id is not None:
            sql += " AND r.colaborador_id = ?"
            params.append(colaborador_id)
        sql += " ORDER BY r.bipado_em DESC, r.id DESC"
        return [_registro(r) for r in self._q(sql, params)]

    # Configuração

    def get_config(self, chave: str, padrao: str | None = None) -> str | None:
        rows = self._q("SELECT valor FROM config WHERE chave = ?", (chave,))
        return rows[0][0] if rows else padrao

    def set_config(self, chave: str, valor: str) -> None:
        self._exec("INSERT OR REPLACE INTO config (chave, valor) VALUES (?, ?)", (chave, valor))

    def del_config(self, chave: str) -> None:
        self._exec("DELETE FROM config WHERE chave = ?", (chave,))
