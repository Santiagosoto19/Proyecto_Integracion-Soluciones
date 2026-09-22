# PC A — SOLO consumidores. En Colab: pip en otra celda, luego pegar esto.
# Debe quedarse viva ~4 min, como la prueba de radio. No ejecutes el productor aquí.

import json
import time
import uuid
from datetime import datetime

import paho.mqtt.client as mqtt

BROKER = "broker.emqx.io"
PORT = 1883
TRANSPORTE = "tcp"
# Si 1883 está bloqueado, AMBOS PCs iguales:
# TRANSPORTE = "websockets"
# PORT = 8084
TOPIC_ACAD = "uni/soto-guzman-gomez/academico/eventos"
TOPIC_VIRT = "uni/soto-guzman-gomez/virtual/eventos"
TOPIC_FIN = "uni/soto-guzman-gomez/financiero/eventos"
TOPIC_ALERTA = "uni/soto-guzman-gomez/detector/alertas"

UMBRAL_DELTA = -1.0
UMBRAL_INACTIVIDAD = 14
UMBRAL_PARTICIPACION = 30
UMBRAL_MORA = 15

ESTADO = {}


def log(*a):
    print(*a, flush=True)


def nuevo_cliente(cid):
    if TRANSPORTE == "tcp" or PORT == 1883:
        return mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=cid)
    c = mqtt.Client(
        mqtt.CallbackAPIVersion.VERSION2,
        client_id=cid,
        transport="websockets",
    )
    c.ws_set_options(path="/mqtt")
    if PORT == 8084:
        c.tls_set()
    return c


def evaluar(evento):
    nombre = evento.get("event_name")
    data = evento.get("data") or {}
    senales = set()
    if nombre == "RendimientoAcademicoCaido":
        delta = data.get("delta_promedio")
        if isinstance(delta, (int, float)) and not isinstance(delta, bool) and delta <= UMBRAL_DELTA:
            senales.add("CAIDA_RENDIMIENTO")
    elif nombre == "InactividadPlataformaDetectada":
        dias = data.get("dias_inactividad") or 0
        part = data.get("participacion_pct", 100)
        if part is None:
            part = 100
        if dias >= UMBRAL_INACTIVIDAD or part < UMBRAL_PARTICIPACION:
            senales.add("INACTIVIDAD_VIRTUAL")
    elif nombre == "MoraFinancieraDetectada":
        dias = data.get("dias_mora") or 0
        if dias >= UMBRAL_MORA:
            senales.add("MORA_FINANCIERA")
    return senales


def publicar_alerta(event_name, codigo, estado, prioridad):
    alerta = {
        "event_id": str(uuid.uuid4()),
        "event_name": event_name,
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "source_system": "detector",
        "periodo": "2026-2",
        "data": {
            "codigo_estudiante": codigo,
            "nombre": estado.get("nombre", ""),
            "nivel_prioridad": prioridad,
            "senales": sorted(estado["senales"]),
            "accion_sugerida": "Revisión por profesional de Bienestar",
        },
    }
    payload = json.dumps(alerta, ensure_ascii=False)
    pub = nuevo_cliente("alerta_" + uuid.uuid4().hex[:8])
    pub.connect(BROKER, PORT, 60)
    pub.loop_start()
    time.sleep(0.8)
    info = pub.publish(TOPIC_ALERTA, payload, qos=1, retain=False)
    try:
        info.wait_for_publish(timeout=10)
    except Exception as exc:
        log("Publicación fallida:", exc)
        raise
    if not info.is_published():
        raise RuntimeError("Publicación NO confirmada en alerta. No se finge éxito.")
    log("DETECTOR publicó", event_name, prioridad, json.dumps(alerta, indent=2, ensure_ascii=False))
    pub.disconnect()
    pub.loop_stop()


def on_hecho(_c, _u, msg):
    try:
        evento = json.loads(msg.payload.decode("utf-8"))
    except Exception as exc:
        log("DETECTOR EVENTO_RECHAZADO", exc)
        return
    data = evento.get("data") or {}
    codigo = str(data.get("codigo_estudiante") or "").strip()
    if not codigo:
        log("DETECTOR EVENTO_RECHAZADO: sin codigo_estudiante")
        return
    est = ESTADO.setdefault(codigo, {"senales": set(), "nombre": "", "alerta": False})
    if data.get("nombre"):
        est["nombre"] = data["nombre"]
    est["senales"] |= evaluar(evento)
    log("==== DETECTOR DE RIESGO ====")
    log("Recibí", evento.get("event_name"), "|", codigo, "| señales", sorted(est["senales"]))
    n = len(est["senales"])
    if n < 2:
        log("Aún no hay alerta (hace falta correlación).")
        return
    prioridad = "ALTA" if n >= 3 else "MEDIA"
    nombre_ev = "AlertaActualizada" if est["alerta"] else "EstudianteRequiereRevision"
    publicar_alerta(nombre_ev, codigo, est, prioridad)
    est["alerta"] = True


def on_alerta(_c, _u, msg):
    try:
        evento = json.loads(msg.payload.decode("utf-8"))
    except Exception as exc:
        log("BIENESTAR EVENTO_RECHAZADO", exc)
        return
    datos = evento.get("data") or {}
    log("==== BIENESTAR INSTITUCIONAL ====")
    log("Alerta recibida:", evento.get("event_name"))
    log("Estudiante:", datos.get("codigo_estudiante"), datos.get("nombre"))
    log("Prioridad:", datos.get("nivel_prioridad"))
    log("Señales:", datos.get("senales"))
    log("Acuse: CasoRegistradoBienestar PENDIENTE_REVISION")


def arrancar():
    log("PC A conecta a", BROKER, PORT, TRANSPORTE)

    det = nuevo_cliente("detector_" + uuid.uuid4().hex[:8])

    def det_connect(c, u, f, rc, p):
        log("DETECTOR CONECTADO", rc)
        c.subscribe(TOPIC_ACAD, qos=1)
        c.subscribe(TOPIC_VIRT, qos=1)
        c.subscribe(TOPIC_FIN, qos=1)
        log("DETECTOR SUSCRITO a Académico, Virtual y Financiero")

    det.on_connect = det_connect
    det.on_message = on_hecho
    det.connect(BROKER, PORT, 60)
    det.loop_start()

    bien = nuevo_cliente("bienestar_" + uuid.uuid4().hex[:8])

    def bien_connect(c, u, f, rc, p):
        log("BIENESTAR CONECTADO", rc)
        c.subscribe(TOPIC_ALERTA, qos=1)
        log("BIENESTAR SUSCRITO a alertas")

    bien.on_connect = bien_connect
    bien.on_message = on_alerta
    bien.connect(BROKER, PORT, 60)
    bien.loop_start()

    time.sleep(2)
    log("PC A listo. AHORA en el PC B ejecuta el productor.")
    log("Esta celda debe seguir en [*] unos 5 minutos. No la detengas.")
    for i in range(60):
        time.sleep(5)
        log("PC A vivo", (i + 1) * 5, "s — DETECTOR y BIENESTAR salen AQUÍ")


arrancar()
