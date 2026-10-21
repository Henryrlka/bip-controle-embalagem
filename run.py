"""Ponto de entrada do bip.exe."""

import logging
import sys
import threading

import waitress

from bip.db import Repo
from bip.inicio import abrir_janela, caminho_static, ja_rodando, pasta_dados, registrar_autostart
from bip.servico import Servico
from bip.teclado import iniciar_escuta
from bip.web import create_app

PORTA = 8765
URL = f"http://127.0.0.1:{PORTA}"


def main() -> None:
    pasta = pasta_dados()
    logging.basicConfig(filename=pasta / "bip.log", level=logging.INFO, encoding="utf-8",
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    if ja_rodando(PORTA):
        abrir_janela(URL)
        return
    try:
        if getattr(sys, "frozen", False):
            registrar_autostart(sys.executable)
        repo = Repo(str(pasta / "bip.db"))
        servico = Servico(repo)
        iniciar_escuta(servico)
        app = create_app(servico, repo, caminho_static())
        threading.Timer(1.0, abrir_janela, args=(URL,)).start()
        logging.info("Bip iniciado em %s", URL)
        waitress.serve(app, host="127.0.0.1", port=PORTA)
    except Exception:
        logging.exception("Falha ao iniciar")
        raise


if __name__ == "__main__":
    main()
