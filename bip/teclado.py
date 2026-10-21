"""Escuta global do teclado: o leitor digita no UpSeller e o programa também recebe as teclas."""

import logging
import os
import time

from pynput import keyboard
from pynput.keyboard import Key, KeyCode

from bip.detector import ScanDetector
from bip.servico import Servico

MODIFICADORES = {Key.shift, Key.shift_r, Key.shift_l, Key.ctrl_l, Key.ctrl_r, Key.alt_l, Key.alt_r,
                 Key.alt_gr, Key.caps_lock}
VK_NUMPAD_0 = 96
VK_NUMPAD_9 = 105
LLKHF_INJECTED = 0x10
# Só para testes neste PC: aceita teclas simuladas (SendKeys). Nunca ligar no pavilhão.
ACEITAR_SIMULADO = os.environ.get("BIP_ACEITAR_SIMULADO") == "1"

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


def aceitar_evento(flags: int, aceitar_simulado: bool) -> bool:
    # Leitor USB é hardware: nunca vem marcado como injetado. Auto-digitação de
    # gerenciador de senha vem, e não pode virar "bip".
    return aceitar_simulado or not flags & LLKHF_INJECTED


def iniciar_escuta(servico: Servico) -> keyboard.Listener:
    detector = ScanDetector(servico.limiar_ms())

    def on_press(key) -> None:
        t_ms = time.perf_counter() * 1000  # antes de tudo: atraso aqui vira intervalo falso
        try:
            detector.limiar_ms = servico.limiar_ms()
            scan = detector.alimentar(token_de(key), t_ms)
            if scan is not None:
                log.info("bip %s", servico.processar_scan(scan)["tipo"])
        except Exception:
            log.exception("Erro ao processar tecla")

    def filtro(msg, data) -> bool:
        return aceitar_evento(data.flags, ACEITAR_SIMULADO)

    listener = keyboard.Listener(on_press=on_press, win32_event_filter=filtro)
    listener.daemon = True
    listener.start()
    return listener
