"""Lectura y validación del archivo de configuración (config.toml)."""

from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path


class ConfigError(ValueError):
    """El archivo de configuración tiene un error que el usuario debe corregir."""


@dataclass
class Fuente:
    dominio: str = "www.datos.gov.co"
    dataset: str = "p6dx-8zbt"
    campos_busqueda: list[str] = field(
        default_factory=lambda: ["descripci_n_del_procedimiento", "nombre_del_procedimiento"]
    )
    campo_fecha: str = "fecha_de_publicacion_del"
    tamano_pagina: int = 10000

    @property
    def url(self) -> str:
        return f"https://{self.dominio}/resource/{self.dataset}.json"


@dataclass
class Filtros:
    fecha_desde: str = ""
    fecha_hasta: str = ""
    departamento: str = ""
    ciudad: str = ""
    entidad_contiene: str = ""
    where_extra: str = ""


@dataclass
class Busqueda:
    nombre: str
    frases: list[str] = field(default_factory=list)
    todas: list[str] = field(default_factory=list)


@dataclass
class Config:
    fuente: Fuente
    filtros: Filtros
    busquedas: list[Busqueda]


_FECHA = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _lista_de_textos(valor, donde: str) -> list[str]:
    if valor is None:
        return []
    if isinstance(valor, str):
        valor = [valor]
    if not isinstance(valor, list) or not all(isinstance(v, str) and v.strip() for v in valor):
        raise ConfigError(f"{donde} debe ser una lista de textos no vacíos")
    return [v.strip() for v in valor]


def cargar_config(ruta: str | Path) -> Config:
    ruta = Path(ruta)
    if not ruta.exists():
        raise ConfigError(f"No existe el archivo de configuración: {ruta}")
    try:
        datos = tomllib.loads(ruta.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as e:
        raise ConfigError(f"{ruta} no es un TOML válido: {e}") from e

    fuente_d = datos.get("fuente", {})
    fuente = Fuente(**{k: v for k, v in fuente_d.items() if k in Fuente.__dataclass_fields__})
    fuente.campos_busqueda = _lista_de_textos(fuente.campos_busqueda, "fuente.campos_busqueda")
    if not fuente.campos_busqueda:
        raise ConfigError("fuente.campos_busqueda no puede estar vacío")
    if not 1 <= int(fuente.tamano_pagina) <= 50000:
        raise ConfigError("fuente.tamano_pagina debe estar entre 1 y 50000")

    filtros_d = datos.get("filtros", {})
    filtros = Filtros(**{k: str(v) for k, v in filtros_d.items() if k in Filtros.__dataclass_fields__})
    for nombre in ("fecha_desde", "fecha_hasta"):
        valor = getattr(filtros, nombre)
        if valor and not _FECHA.match(valor):
            raise ConfigError(f"filtros.{nombre} debe tener formato AAAA-MM-DD (recibido: {valor!r})")

    busquedas = []
    vistos = set()
    for i, b in enumerate(datos.get("busquedas", []), start=1):
        nombre = str(b.get("nombre", "")).strip()
        if not nombre:
            raise ConfigError(f"La búsqueda #{i} no tiene 'nombre'")
        if nombre in vistos:
            raise ConfigError(f"El nombre de búsqueda {nombre!r} está repetido")
        vistos.add(nombre)
        busqueda = Busqueda(
            nombre=nombre,
            frases=_lista_de_textos(b.get("frases"), f"busquedas[{nombre}].frases"),
            todas=_lista_de_textos(b.get("todas"), f"busquedas[{nombre}].todas"),
        )
        if not busqueda.frases and not busqueda.todas:
            raise ConfigError(f"La búsqueda {nombre!r} necesita 'frases' o 'todas'")
        busquedas.append(busqueda)

    if not busquedas:
        raise ConfigError("Defina al menos un bloque [[busquedas]] en la configuración")

    return Config(fuente=fuente, filtros=filtros, busquedas=busquedas)
