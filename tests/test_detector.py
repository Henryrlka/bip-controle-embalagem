from bip.detector import Scan, ScanDetector


def digitar(det, texto, inicio=0.0, passo=10.0):
    t = inicio
    for c in texto:
        t += passo
        det.alimentar(c, t)
    t += passo
    return det.alimentar("ENTER", t)


def test_bip_rapido_detectado():
    det = ScanDetector(50)
    assert digitar(det, "999882543964725") == Scan("999882543964725", 10.0)


def test_digitacao_lenta_ignorada():
    det = ScanDetector(50)
    assert digitar(det, "999882543964725", passo=120) is None


def test_curto_ignorado():
    det = ScanDetector(50)
    assert digitar(det, "123456789") is None
    assert digitar(det, "1234567890", inicio=1000).codigo == "1234567890"


def test_longo_ignorado():
    det = ScanDetector(50)
    assert digitar(det, "1" * 31) is None
    assert digitar(det, "1" * 30, inicio=1000).codigo == "1" * 30


def test_caractere_invalido():
    det = ScanDetector(50)
    assert digitar(det, "99988254396-725") is None


def test_normaliza_maiusculas():
    det = ScanDetector(50)
    assert digitar(det, "br1234567890br").codigo == "BR1234567890BR"


def test_pausa_reinicia_buffer():
    det = ScanDetector(50)
    for i, c in enumerate("abc"):
        det.alimentar(c, i * 200.0)
    assert digitar(det, "999882543964725", inicio=900).codigo == "999882543964725"


def test_outra_tecla_zera():
    det = ScanDetector(50)
    t = 0.0
    for c in "12345678":
        t += 10
        det.alimentar(c, t)
    det.alimentar("OUTRA", t + 5)
    assert digitar(det, "1234567", inicio=t + 5) is None


def test_modificador_nao_quebra_sequencia():
    det = ScanDetector(50)
    t = 0.0
    for c in "BR":
        det.alimentar("MOD", t + 5)
        t += 10
        det.alimentar(c, t)
    scan = digitar(det, "123456789012", inicio=t)
    assert scan.codigo == "BR123456789012"


def test_limiar_alteravel():
    det = ScanDetector(50)
    det.limiar_ms = 300
    assert digitar(det, "999882543964725", passo=120).codigo == "999882543964725"
