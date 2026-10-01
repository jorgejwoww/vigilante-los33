"""
Vigilante de mesas para Los 33 (Madrid).

Pregunta a la web de reservas (CoverManager) si hay mesa para 2 personas
a las 22:30 cualquier viernes o sábado de los próximos 2 meses.
Si encuentra hueco, te manda un WhatsApp (a través de CallMeBot).

No reserva nada ni mete ningún dato: solo mira y avisa.
"""

import calendar
import json
import os
import sys
import time
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

# ---- Ajustes (puedes cambiarlos) ----
RESTAURANTE = "restaurante-los33"
PERSONAS = "2"
HORAS = ["22:30"]          # p. ej. ["20:00", "22:30"] para vigilar los dos turnos
DIAS = [4, 5]              # 4 = viernes, 5 = sábado
VIGILAR_HASTA = date(2027, 3, 1)   # después de este día, el vigilante se para solo
# -------------------------------------

WEB = "https://www.covermanager.com"
ENLACE = f"{WEB}/reservation/module_restaurant/{RESTAURANTE}/spanish"
DIAS_SEMANA = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]


def dos_meses_despues(d: date) -> date:
    mes = d.month + 2
    anio = d.year + (mes - 1) // 12
    mes = (mes - 1) % 12 + 1
    dia = min(d.day, calendar.monthrange(anio, mes)[1])
    return date(anio, mes, dia)


def fechas_a_vigilar(hoy: date):
    fin = dos_meses_despues(hoy)
    d = hoy
    while d <= fin:
        if d.weekday() in DIAS:
            yield d
        d += timedelta(days=1)


def hay_mesa(d: date, hora: str) -> bool:
    datos = urllib.parse.urlencode({
        "recaptchaToken": "",
        "language": "spanish",
        "restaurant": RESTAURANTE,
        "hour": hora,
        "date": d.strftime("%d-%m-%Y"),
        "people": PERSONAS,
        "extra": "-1",
        "skip_blocked_tables": "false",
        "source": "",
        "utm_emailmarketing": "false",
    }).encode()
    peticion = urllib.request.Request(
        f"{WEB}/reservs/avaible_reserv_module/0",
        data=datos,
        headers={
            "X-Requested-With": "XMLHttpRequest",
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
            "Referer": ENLACE,
        },
    )
    with urllib.request.urlopen(peticion, timeout=30) as r:
        respuesta = json.loads(r.read().decode("utf-8"))
    return str(respuesta.get("resp")) == "1"


def enviar_whatsapp(texto: str):
    telefono = os.environ["WHATSAPP_TELEFONO"]
    clave = os.environ["CALLMEBOT_APIKEY"]
    url = "https://api.callmebot.com/whatsapp.php?" + urllib.parse.urlencode(
        {"phone": telefono, "text": texto, "apikey": clave}
    )
    with urllib.request.urlopen(url, timeout=30) as r:
        print("WhatsApp enviado:", r.status)


def main():
    hoy = datetime.now(ZoneInfo("Europe/Madrid")).date()
    if hoy > VIGILAR_HASTA:
        print(f"Vigilancia terminada el {VIGILAR_HASTA}. No se comprueba nada.")
        return
    libres, errores, comprobadas = [], 0, 0

    for d in fechas_a_vigilar(hoy):
        for hora in HORAS:
            comprobadas += 1
            try:
                if hay_mesa(d, hora):
                    libres.append(f"• {DIAS_SEMANA[d.weekday()]} {d.strftime('%d/%m')} a las {hora}")
            except Exception as e:  # la web no respondió como esperábamos
                errores += 1
                print(f"Error comprobando {d} {hora}: {e}")
            time.sleep(1)  # sin prisas, para no saturar la web

    print(f"Comprobadas {comprobadas} combinaciones. Libres: {len(libres)}. Errores: {errores}.")

    if libres:
        enviar_whatsapp(
            "🍽️ ¡MESA LIBRE EN LOS 33! (2 personas)\n"
            + "\n".join(libres)
            + f"\n\nEntra YA: {ENLACE}\nElige la fecha, 2 personas, la hora y pulsa Reservar."
        )

    # Si TODAS las comprobaciones fallan, algo ha cambiado en la web:
    # el programa termina con error y GitHub te avisa por email.
    if comprobadas and errores == comprobadas:
        sys.exit("No se pudo comprobar ninguna fecha. Puede que la web haya cambiado.")


if __name__ == "__main__":
    if "--prueba-whatsapp" in sys.argv:
        enviar_whatsapp("✅ Vigilante de Los 33 conectado. Te avisaré por aquí cuando haya mesa.")
    else:
        main()
