"""Limpieza de los resultados y escritura de CSV / Excel."""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

# Columnas que se muestran primero (si existen); el resto va después.
COLUMNAS_PRINCIPALES = [
    "busquedas",
    "entidad",
    "nit_entidad",
    "departamento_entidad",
    "ciudad_entidad",
    "id_del_proceso",
    "referencia_del_proceso",
    "nombre_del_procedimiento",
    "descripci_n_del_procedimiento",
    "fase",
    "estado_del_procedimiento",
    "modalidad_de_contratacion",
    "tipo_de_contrato",
    "fecha_de_publicacion_del",
    "precio_base",
    "adjudicado",
    "nombre_del_proveedor",
    "valor_total_adjudicacion",
    "urlproceso",
]
COLUMNAS_NUMERICAS = ["precio_base", "valor_total_adjudicacion"]
CLAVE = "id_del_proceso"


def a_tabla(registros: list[dict]) -> pd.DataFrame:
    df = pd.json_normalize(registros) if registros else pd.DataFrame()
    # urlproceso llega como {"url": "..."}; json_normalize lo deja en "urlproceso.url".
    if "urlproceso.url" in df.columns:
        df = df.rename(columns={"urlproceso.url": "urlproceso"})
    for col in COLUMNAS_NUMERICAS:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    for col in df.columns:
        if col.startswith("fecha") and df[col].dtype == object:
            df[col] = pd.to_datetime(df[col], errors="coerce")
    return df


def ordenar_columnas(df: pd.DataFrame) -> pd.DataFrame:
    primeras = [c for c in COLUMNAS_PRINCIPALES if c in df.columns]
    return df[primeras + [c for c in df.columns if c not in primeras]]


def consolidar(por_busqueda: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Une todas las búsquedas en una tabla; un proceso aparece una sola vez
    y la columna `busquedas` indica en cuáles se encontró."""
    marcos = [df.assign(busquedas=nombre) for nombre, df in por_busqueda.items() if not df.empty]
    if not marcos:
        return pd.DataFrame()
    todo = pd.concat(marcos, ignore_index=True)
    if CLAVE not in todo.columns:
        return ordenar_columnas(todo)
    etiquetas = todo.groupby(CLAVE, sort=False)["busquedas"].agg(lambda s: ", ".join(dict.fromkeys(s)))
    unicos = todo.drop_duplicates(subset=CLAVE).drop(columns="busquedas")
    unicos = unicos.merge(etiquetas, left_on=CLAVE, right_index=True)
    return ordenar_columnas(unicos.reset_index(drop=True))


def resumen(por_busqueda: dict[str, pd.DataFrame], totales_api: dict[str, int]) -> pd.DataFrame:
    filas = []
    for nombre, df in por_busqueda.items():
        filas.append({
            "busqueda": nombre,
            "procesos_en_la_fuente": totales_api.get(nombre),
            "procesos_descargados": len(df),
            "entidades_distintas": df["entidad"].nunique() if "entidad" in df else None,
            "suma_precio_base": df["precio_base"].sum() if "precio_base" in df else None,
        })
    return pd.DataFrame(filas)


def por_entidad(todo: pd.DataFrame) -> pd.DataFrame:
    if todo.empty or "entidad" not in todo.columns:
        return pd.DataFrame()
    agg = {"procesos": (CLAVE if CLAVE in todo.columns else "entidad", "count")}
    if "precio_base" in todo.columns:
        agg["suma_precio_base"] = ("precio_base", "sum")
    return todo.groupby("entidad").agg(**agg).sort_values("procesos", ascending=False).reset_index()


def _nombre_hoja(nombre: str) -> str:
    # Excel: máximo 31 caracteres y sin []:*?/\
    return re.sub(r"[\[\]:*?/\\]", "_", nombre)[:31]


def _sin_zona_horaria(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    for col in df.select_dtypes(include=["datetimetz"]).columns:
        df[col] = df[col].dt.tz_localize(None)
    return df


def guardar(carpeta: Path, por_busqueda: dict[str, pd.DataFrame], totales_api: dict[str, int]) -> Path:
    carpeta.mkdir(parents=True, exist_ok=True)
    todo = consolidar(por_busqueda)

    for nombre, df in por_busqueda.items():
        ordenar_columnas(df).to_csv(carpeta / f"{nombre}.csv", index=False, encoding="utf-8-sig")
    todo.to_csv(carpeta / "todos_los_procesos.csv", index=False, encoding="utf-8-sig")

    excel = carpeta / "procesos_secop.xlsx"
    with pd.ExcelWriter(excel, engine="openpyxl") as w:
        resumen(por_busqueda, totales_api).to_excel(w, sheet_name="resumen", index=False)
        por_entidad(todo).to_excel(w, sheet_name="por_entidad", index=False)
        _sin_zona_horaria(todo).to_excel(w, sheet_name="todos", index=False)
        for nombre, df in por_busqueda.items():
            _sin_zona_horaria(ordenar_columnas(df)).to_excel(w, sheet_name=_nombre_hoja(nombre), index=False)
    return excel
