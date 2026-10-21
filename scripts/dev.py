"""Servidor de desenvolvimento: sobe a interface e simula bips digitados no terminal."""

import sys
import threading
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from bip.db import Repo  # noqa: E402
from bip.detector import Scan  # noqa: E402
from bip.servico import Servico  # noqa: E402
from bip.web import create_app  # noqa: E402


def main() -> None:
    repo = Repo(str(RAIZ / "dev.db"))
    repo.set_config("limiar_ms", "50")
    servico = Servico(repo)
    app = create_app(servico, repo, str(RAIZ / "bip" / "static"))
    threading.Thread(target=lambda: app.run(port=8765), daemon=True).start()
    print("http://127.0.0.1:8765 — digite um rastreio e Enter para simular bip", flush=True)
    for linha in sys.stdin:
        codigo = linha.strip().upper()
        if codigo:
            print(servico.processar_scan(Scan(codigo, 10))["mensagem"], flush=True)


if __name__ == "__main__":
    main()
