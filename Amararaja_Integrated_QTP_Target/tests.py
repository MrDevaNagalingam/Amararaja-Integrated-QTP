"""QTP target tests."""

import selec_EM4M

def ping(params):
    return {"status": "PASS", "message": "PONG - target received command"}


def echo(params):
    text = params.get("text", "")
    if not isinstance(text, str) or len(text.encode("utf-8")) > 16000:
        return {"status": "ERROR", "message": "Echo requires text up to 16000 UTF-8 bytes"}
    return {"status": "PASS", "message": text}


def selec_em4m(params):
    return selec_EM4M.run_qtp_test(
        port=params.get("port", "/dev/ttyCH9344USB4"),
        baudrate=int(params.get("baudrate", 9600)),
        slave_id=int(params.get("slave_id", 1)),
        timeout=float(params.get("timeout", 0.3)),
        voltage_tolerance=float(params.get("voltage_tolerance", 1.0)),
    )


TESTS = {"PING": ping, "ECHO": echo, "SELEC_EM4M": selec_em4m}
