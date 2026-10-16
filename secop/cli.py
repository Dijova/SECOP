"""Línea de comandos: python -m secop {probar,contar,buscar} ..."""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime
from pathlib import Path

from secop.cliente import ClienteSocrata, ErrorAPI
from secop.config import Config, ConfigError, cargar_config
from secop.consulta import where_completo
from secop import exportar

log = logging.getLogger("secop")


def cmd_probar(config: Config, cliente: ClienteSocrata, args) -> int:
    print(f"Consultando {config.fuente.url} ...")
    filas = cliente.get({"$limit": 1})
    if not filas:
        print("La conexión funciona, pero el conjunto de datos no devolvió registros.")
        return 1
    print("Conexión correcta. Columnas disponibles y un valor de ejemplo:\n")
    for col, valor in filas[0].items():
        texto = str(valor).replace("\n", " ")
        print(f"  {col:<45} {texto[:70]}")

    faltan = [c for c in [*config.fuente.campos_busqueda, config.fuente.campo_fecha] if c not in filas[0]]
    if faltan:
        # Un registro puede omitir columnas vacías, así que solo se advierte.
        print(f"\nAviso: estas columnas de config.toml no aparecen en el ejemplo: {', '.join(faltan)}."
              "\nSi el nombre es distinto en la lista de arriba, corríjalo en la sección [fuente].")
    return 0


def _busquedas(config: Config, solo: list[str] | None):
    if not solo:
        return config.busquedas
    nombres = {b.nombre for b in config.busquedas}
    desconocidas = [s for s in solo if s not in nombres]
    if desconocidas:
        raise ConfigError(f"Búsquedas no definidas en la configuración: {', '.join(desconocidas)}")
    return [b for b in config.busquedas if b.nombre in solo]


def cmd_contar(config: Config, cliente: ClienteSocrata, args) -> int:
    for b in _busquedas(config, args.solo):
        where = where_completo(b, config)
        total = cliente.contar(where)
        print(f"{b.nombre:<30} {total:>10,} procesos")
        if args.mostrar_consulta:
            print(f"   {cliente.url_navegador({'$where': where, '$limit': 100})}\n")
    return 0


def cmd_buscar(config: Config, cliente: ClienteSocrata, args) -> int:
    por_busqueda, totales = {}, {}
    for b in _busquedas(config, args.solo):
        where = where_completo(b, config)
        totales[b.nombre] = cliente.contar(where)
        a_bajar = totales[b.nombre] if args.maximo is None else min(args.maximo, totales[b.nombre])
        print(f"[{b.nombre}] {totales[b.nombre]:,} procesos en la fuente; descargando {a_bajar:,} ...")
        if args.mostrar_consulta:
            print(f"   {cliente.url_navegador({'$where': where, '$limit': 100})}")

        registros = []
        for pagina in cliente.paginar(where, config.fuente.campo_fecha, config.fuente.tamano_pagina, args.maximo):
            registros.extend(pagina)
            print(f"   {len(registros):,} / {a_bajar:,}", end="\r", flush=True)
        print(f"   {len(registros):,} registros descargados.      ")
        por_busqueda[b.nombre] = exportar.a_tabla(registros)

    carpeta = Path(args.salida) / datetime.now().strftime("%Y%m%d_%H%M%S")
    excel = exportar.guardar(carpeta, por_busqueda, totales)
    print(f"\nListo. Resultados en: {carpeta}\n  Excel: {excel}")
    return 0


def construir_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="python -m secop",
        description="Extrae procesos de contratación de SECOP II (datos.gov.co) según config.toml.",
    )
    p.add_argument("-c", "--config", default="config.toml", help="archivo de configuración (por defecto config.toml)")
    p.add_argument("--token", default=None, help="App Token de datos.gov.co (o variable SOCRATA_APP_TOKEN)")
    p.add_argument("-v", "--verbose", action="store_true", help="mostrar detalles de cada consulta")
    sub = p.add_subparsers(dest="comando", required=True)

    sub.add_parser("probar", help="verificar la conexión y listar las columnas del conjunto de datos")

    for nombre, ayuda in (("contar", "contar resultados por búsqueda sin descargar"),
                          ("buscar", "descargar los procesos y guardarlos en CSV y Excel")):
        s = sub.add_parser(nombre, help=ayuda)
        s.add_argument("--solo", nargs="+", metavar="NOMBRE", help="ejecutar solo estas búsquedas")
        s.add_argument("--mostrar-consulta", action="store_true", help="imprimir la URL para abrirla en el navegador")
        if nombre == "buscar":
            s.add_argument("--maximo", type=int, default=None, help="máximo de registros por búsqueda")
            s.add_argument("--salida", default="salidas", help="carpeta de resultados (por defecto salidas/)")
    return p


def main(argv: list[str] | None = None) -> int:
    args = construir_parser().parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.WARNING,
                        format="%(levelname)s: %(message)s")
    try:
        config = cargar_config(args.config)
        cliente = ClienteSocrata(config.fuente.url, token=args.token)
        comando = {"probar": cmd_probar, "contar": cmd_contar, "buscar": cmd_buscar}[args.comando]
        return comando(config, cliente, args)
    except ConfigError as e:
        print(f"Error de configuración: {e}", file=sys.stderr)
    except ErrorAPI as e:
        print(f"Error de la API: {e}", file=sys.stderr)
    except KeyboardInterrupt:
        print("\nCancelado por el usuario.", file=sys.stderr)
    return 1
