"""Construcción de las condiciones SoQL ($where) a partir de la configuración."""

from __future__ import annotations

import unicodedata

from secop.config import Busqueda, Config, Filtros, Fuente


def quitar_tildes(texto: str) -> str:
    """'LOGÍSTICOS' -> 'LOGISTICOS'. Conserva la Ñ."""
    texto = texto.replace("ñ", "\0n").replace("Ñ", "\0N")
    sin = "".join(c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn")
    return sin.replace("\0n", "ñ").replace("\0N", "Ñ")


def literal(texto: str) -> str:
    """Texto SoQL entre comillas simples, con las comillas internas escapadas."""
    return "'" + texto.replace("'", "''") + "'"


def variantes(frase: str) -> list[str]:
    """La frase en mayúsculas, con y sin tildes (sin duplicados)."""
    con = " ".join(frase.upper().split())
    sin = quitar_tildes(con)
    return [con] if con == sin else [con, sin]


def condicion_frase(frase: str, campos: list[str]) -> str:
    """La frase (o su versión sin tildes) aparece en alguno de los campos."""
    partes = [
        f"upper({campo}) like {literal('%' + v + '%')}"
        for v in variantes(frase)
        for campo in campos
    ]
    return "(" + " OR ".join(partes) + ")"


def condicion_busqueda(busqueda: Busqueda, fuente: Fuente) -> str:
    bloques = []
    if busqueda.frases:
        bloques.append(
            "(" + " OR ".join(condicion_frase(f, fuente.campos_busqueda) for f in busqueda.frases) + ")"
        )
    bloques.extend(condicion_frase(f, fuente.campos_busqueda) for f in busqueda.todas)
    return " AND ".join(bloques)


def condicion_filtros(filtros: Filtros, fuente: Fuente) -> list[str]:
    partes = []
    if filtros.fecha_desde:
        partes.append(f"{fuente.campo_fecha} >= {literal(filtros.fecha_desde + 'T00:00:00')}")
    if filtros.fecha_hasta:
        partes.append(f"{fuente.campo_fecha} <= {literal(filtros.fecha_hasta + 'T23:59:59')}")
    if filtros.departamento:
        partes.append(condicion_frase(filtros.departamento, ["departamento_entidad"]))
    if filtros.ciudad:
        partes.append(condicion_frase(filtros.ciudad, ["ciudad_entidad"]))
    if filtros.entidad_contiene:
        partes.append(condicion_frase(filtros.entidad_contiene, ["entidad"]))
    if filtros.where_extra.strip():
        partes.append("(" + filtros.where_extra.strip() + ")")
    return partes


def where_completo(busqueda: Busqueda, config: Config) -> str:
    partes = [condicion_busqueda(busqueda, config.fuente)]
    partes.extend(condicion_filtros(config.filtros, config.fuente))
    return " AND ".join(partes)
