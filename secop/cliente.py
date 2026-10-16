"""Cliente HTTP para la API SODA (Socrata) de datos.gov.co."""

from __future__ import annotations

import logging
import os
import time
from collections.abc import Iterator
from urllib.parse import urlencode

import requests

log = logging.getLogger(__name__)

REINTENTOS = 5
TIMEOUT_S = 120


class ErrorAPI(RuntimeError):
    """La API respondió con un error que no se resuelve reintentando."""


class ClienteSocrata:
    def __init__(self, url: str, token: str | None = None, sesion: requests.Session | None = None,
                 espera_base: float = 2.0):
        self.url = url
        self.sesion = sesion or requests.Session()
        self.espera_base = espera_base
        token = token if token is not None else os.environ.get("SOCRATA_APP_TOKEN", "")
        if token:
            # Con token la API permite muchas más consultas por hora.
            self.sesion.headers["X-App-Token"] = token
        self.sesion.headers.setdefault("Accept", "application/json")

    def url_navegador(self, params: dict) -> str:
        """URL equivalente que se puede abrir en el navegador para verificar."""
        return f"{self.url}?{urlencode(params)}"

    def get(self, params: dict) -> list[dict]:
        for intento in range(1, REINTENTOS + 1):
            try:
                r = self.sesion.get(self.url, params=params, timeout=TIMEOUT_S)
            except (requests.ConnectionError, requests.Timeout) as e:
                if intento == REINTENTOS:
                    raise ErrorAPI(f"No fue posible conectarse a {self.url}: {e}") from e
                self._esperar(intento, f"error de conexión ({e.__class__.__name__})")
                continue

            if r.status_code == 200:
                return r.json()
            if r.status_code in (429, 500, 502, 503, 504) and intento < REINTENTOS:
                self._esperar(intento, f"HTTP {r.status_code}")
                continue
            raise ErrorAPI(f"HTTP {r.status_code} al consultar {self.url}: {_mensaje(r)}")
        raise ErrorAPI("Se agotaron los reintentos")  # pragma: no cover

    def contar(self, where: str) -> int:
        filas = self.get({"$select": "count(*) AS total", "$where": where})
        return int(filas[0]["total"]) if filas else 0

    def paginar(self, where: str, orden: str, tamano_pagina: int,
                maximo: int | None = None) -> Iterator[list[dict]]:
        """Entrega los registros por páginas hasta agotar los resultados."""
        offset = 0
        while True:
            limite = tamano_pagina if maximo is None else min(tamano_pagina, maximo - offset)
            if limite <= 0:
                return
            pagina = self.get({
                "$where": where,
                # `:id` desempata para que la paginación sea estable.
                "$order": f"{orden} DESC, :id",
                "$limit": limite,
                "$offset": offset,
            })
            if not pagina:
                return
            yield pagina
            offset += len(pagina)
            if len(pagina) < limite:
                return

    def _esperar(self, intento: int, motivo: str) -> None:
        segundos = self.espera_base * 2 ** (intento - 1)
        log.warning("%s; reintento %d/%d en %.0f s", motivo, intento, REINTENTOS - 1, segundos)
        time.sleep(segundos)


def _mensaje(r: requests.Response) -> str:
    try:
        cuerpo = r.json()
        return cuerpo.get("message") or str(cuerpo)
    except ValueError:
        return r.text[:300]
