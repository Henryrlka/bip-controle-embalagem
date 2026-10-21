"""Escuta global do teclado: o leitor digita no UpSeller e o programa também recebe as teclas."""

import logging
import time

from pynput import keyboard
from pynput.keyboard import Key, KeyCode

from bip.detector import ScanDetector
from bip.servico import Servico

MODIFICADORES = {Key.shift, Key.shift_r, Key.shift_l, Key.ctrl_l, Key.ctrl_r, Key.alt_l, Key.alt_r,
                 Key.alt_gr, Key.caps_lock}
VK_NUMPAD_0 = 96
VK_NUMPAD_9 = 105

log = logging.getLogger(__name__)


def token_de(key) -> str:
    if key == Key.enter:
        return "ENTER"
    if key in MODIFICADORES:
        return "MOD"
    if isinstance(key, KeyCode):
        if key.char is not None:
            return key.char
        if key.vk is not None and VK_NUMPAD_0 <= key.vk <= VK_NUMPAD_9:
            return str(key.vk - VK_NUMPAD_0)
    return "OUTRA"


def iniciar_escuta(servico: Servico) -> keyboard.Listener:
    detector = ScanDetector(servico.limiar_ms())

    def on_press(key) -> None:
        try:
            detector.limiar_ms = servico.limiar_ms()
            scan = detector.alimentar(token_de(key), time.perf_counter() * 1000)
            if scan is not None:
                evento = servico.processar_scan(scan)
                log.info("bip %s -> %s", scan.codigo, evento["mensagem"])
        except Exception:
            log.exception("Erro ao processar tecla")

    listener = keyboard.Listener(on_press=on_press)
    listener.daemon = True
    listener.start()
    return listener
