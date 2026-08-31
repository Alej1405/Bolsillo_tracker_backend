"""Correo saliente a traves de Resend.

Una sola regla gobierna este modulo: **enviar un correo no puede tumbar la
operacion que lo origino**. La cuenta ya esta creada y confirmada en la base
cuando esto corre; si Resend esta caido, la clave expiro o la red falla, se
anota en el log y se sigue. Por eso ningun metodo de aqui propaga excepciones.

Se llama a la API REST con httpx en vez de usar el SDK de Resend: es una sola
peticion POST, y asi el timeout, el manejo de errores y lo que se registra en
el log quedan a la vista en lugar de dentro de una dependencia mas.
"""

import logging

import httpx

logger = logging.getLogger(__name__)

_URL = "https://api.resend.com/emails"

#Si Resend no contesta en este tiempo, se abandona. Corre en segundo plano,
#pero un worker colgado en una peticion sin timeout no se libera nunca.
_ESPERA = 10.0


class EmailService:
    """Envia los correos de la aplicacion.

    Recibe la clave y el remitente ya resueltos en lugar de leer `settings`
    aqui dentro: asi se puede construir con otros valores en una prueba sin
    tocar variables de entorno.
    """

    def __init__(self, api_key: str, remitente: str):
        self._api_key = api_key
        self._remitente = remitente

    def enviar_bienvenida(self, para: str, nombre: str) -> bool:
        """Da la bienvenida a una cuenta recien creada.

        Devuelve si el envio salio bien, para poder comprobarlo en una prueba.
        Quien lo llama en produccion no necesita mirarlo: no hay nada que hacer
        si falla salvo lo que ya se hizo, que es dejarlo escrito en el log.
        """
        #Solo el primer nombre: "Hola, Diego" suena a persona; "Hola, Diego
        #Alejandro Morales Cruz" suena a cobranza.
        primer_nombre = nombre.strip().split(" ")[0] if nombre.strip() else "hola"

        return self._enviar(
            para=para,
            asunto="Bienvenido a Bolsillo",
            html=_bienvenida_html(primer_nombre),
            texto=_bienvenida_texto(primer_nombre),
        )

    def _enviar(self, para: str, asunto: str, html: str, texto: str) -> bool:
        try:
            respuesta = httpx.post(
                _URL,
                headers={"Authorization": f"Bearer {self._api_key}"},
                json={
                    "from": self._remitente,
                    "to": [para],
                    "subject": asunto,
                    "html": html,
                    #Alternativa en texto plano. No es un adorno: sin ella los
                    #filtros de spam puntuan peor el mensaje.
                    "text": texto,
                },
                timeout=_ESPERA,
            )
        except httpx.HTTPError:
            #Sin `exc_info` el traceback no aparece, y aqui es lo unico que
            #dice si fue DNS, timeout o certificado.
            logger.exception("No se pudo contactar con Resend para %s", para)
            return False

        if respuesta.status_code >= 400:
            #El cuerpo trae el motivo real de Resend: dominio sin verificar,
            #clave invalida, destinatario rechazado. Sin el, un 403 no dice nada.
            logger.error(
                "Resend rechazo el correo para %s: %s %s",
                para,
                respuesta.status_code,
                respuesta.text,
            )
            return False

        logger.info("Correo de bienvenida enviado a %s", para)
        return True


def _bienvenida_html(nombre: str) -> str:
    """Cuerpo HTML del correo.

    Todo el estilo va en linea y la estructura en tablas porque los clientes de
    correo no son navegadores: Outlook ignora <style> en el head, y Gmail
    recorta lo que no entiende. Es HTML de 2005 a proposito.
    """
    return f"""\
<!doctype html>
<html lang="es">
  <body style="margin:0;padding:0;background-color:#ece9f6;font-family:Helvetica,Arial,sans-serif;">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background-color:#ece9f6;padding:32px 16px;">
      <tr>
        <td align="center">
          <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:520px;background-color:#ffffff;border-radius:14px;overflow:hidden;">
            <tr>
              <td style="background-color:#553d78;padding:28px 32px;">
                <p style="margin:0;font-size:22px;font-weight:bold;color:#ffffff;letter-spacing:0.045em;">Bolsillo</p>
              </td>
            </tr>
            <tr>
              <td style="padding:32px;">
                <p style="margin:0 0 16px;font-size:20px;font-weight:bold;color:#0f172a;">Hola, {nombre}</p>
                <p style="margin:0 0 16px;font-size:15px;line-height:1.6;color:#475569;">
                  Tu cuenta ya está lista. Bolsillo es para llevar tus finanzas sin
                  complicarte: registras lo que entra y lo que sale, y la aplicación
                  arma los reportes por ti.
                </p>
                <p style="margin:0 0 24px;font-size:15px;line-height:1.6;color:#475569;">
                  Para empezar, crea tus bolsillos &mdash; efectivo, banco, tarjeta,
                  ahorro &mdash; y registra tu primer movimiento. Con eso ya tienes
                  de dónde leer.
                </p>
                <p style="margin:0 0 8px;font-size:13px;line-height:1.6;color:#64748b;">
                  Si no fuiste tú quien creó esta cuenta, ignora este correo.
                </p>
              </td>
            </tr>
            <tr>
              <td style="padding:20px 32px;border-top:1px solid #e2e8f0;">
                <p style="margin:0;font-size:11px;color:#94a3b8;">Bolsillo &middot; Hecho en Ecuador</p>
              </td>
            </tr>
          </table>
        </td>
      </tr>
    </table>
  </body>
</html>"""


def _bienvenida_texto(nombre: str) -> str:
    """La misma carta sin formato, para quien lee el correo en texto plano."""
    return f"""\
Hola, {nombre}

Tu cuenta ya está lista. Bolsillo es para llevar tus finanzas sin complicarte:
registras lo que entra y lo que sale, y la aplicación arma los reportes por ti.

Para empezar, crea tus bolsillos -efectivo, banco, tarjeta, ahorro- y registra
tu primer movimiento. Con eso ya tienes de dónde leer.

Si no fuiste tú quien creó esta cuenta, ignora este correo.

Bolsillo - Hecho en Ecuador"""
