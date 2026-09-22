# PC B — SOLO productor. Ejecutar DESPUÉS de ver en A: DETECTOR SUSCRITO y BIENESTAR SUSCRITO.

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


def publicar(topic, evento):
    c = nuevo_cliente("prod_" + uuid.uuid4().hex[:8])
    c.connect(BROKER, PORT, 60)
    c.loop_start()
    time.sleep(0.8)
    payload = json.dumps(evento, indent=2, ensure_ascii=False)
    info = c.publish(topic, payload, qos=1, retain=False)
    try:
        info.wait_for_publish(timeout=10)
    except Exception as exc:
        print("Publicación fallida:", exc, flush=True)
        raise
    if not info.is_published():
        raise RuntimeError(f"Publicación NO confirmada en {topic}. No se finge éxito.")
    print("B publicó en", topic, flush=True)
    print(payload, flush=True)
    c.disconnect()
    c.loop_stop()


def hecho(event_name, source, data):
    return {
        "event_id": str(uuid.uuid4()),
        "event_name": event_name,
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "source_system": source,
        "periodo": "2026-2",
        "data": data,
    }


print("PC B productor →", BROKER, PORT, TRANSPORTE, flush=True)
print("Mira la salida en el PC A (celda [*] de consumidores), no aquí.", flush=True)
time.sleep(1)

print("\n--- Académico 4.2 → 2.9 ---")
publicar(
    TOPIC_ACAD,
    hecho(
        "RendimientoAcademicoCaido",
        "academico",
        {
            "codigo_estudiante": "EST001",
            "nombre": "Ana Pérez",
            "programa": "Ingeniería de Sistemas",
            "promedio_anterior": 4.2,
            "promedio_actual": 2.9,
            "delta_promedio": -1.3,
        },
    ),
)
time.sleep(2)

print("\n--- Virtual 18 días ---")
publicar(
    TOPIC_VIRT,
    hecho(
        "InactividadPlataformaDetectada",
        "virtual",
        {
            "codigo_estudiante": "EST001",
            "nombre": "Ana Pérez",
            "dias_inactividad": 18,
            "participacion_pct": 22.0,
        },
    ),
)
time.sleep(2)

print("\n--- Financiero mora 20 días ---")
publicar(
    TOPIC_FIN,
    hecho(
        "MoraFinancieraDetectada",
        "financiero",
        {
            "codigo_estudiante": "EST001",
            "nombre": "Ana Pérez",
            "dias_mora": 20,
            "valor_pendiente": 850000.0,
            "estado_obligacion": "EN_MORA",
        },
    ),
)
print("\nB terminó. En A debes ver DETECTOR (1 señal, luego MEDIA, luego ALTA) y BIENESTAR.")
