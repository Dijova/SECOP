from pathlib import Path

import pandas as pd
import pytest

from secop import exportar
from secop.cli import main
from secop.cliente import ClienteSocrata, ErrorAPI
from secop.config import Busqueda, ConfigError, cargar_config
from secop.consulta import condicion_frase, quitar_tildes, variantes, where_completo

RAIZ = Path(__file__).resolve().parents[1]


class Respuesta:
    def __init__(self, datos, status=200):
        self.datos, self.status_code, self.text = datos, status, str(datos)

    def json(self):
        return self.datos


class SesionFalsa:
    """Simula la API: filtra nada, solo pagina sobre `registros`."""

    def __init__(self, registros, errores=()):
        self.registros, self.errores = registros, list(errores)
        self.headers, self.llamadas = {}, []

    def get(self, url, params, timeout):
        self.llamadas.append(params)
        if self.errores:
            return Respuesta({"message": "error"}, self.errores.pop(0))
        if params.get("$select", "").startswith("count"):
            return Respuesta([{"total": str(len(self.registros))}])
        ini = int(params.get("$offset", 0))
        return Respuesta(self.registros[ini:ini + int(params.get("$limit", 1000))])


def test_config_del_repositorio_es_valida():
    config = cargar_config(RAIZ / "config.toml")
    assert config.fuente.dataset == "p6dx-8zbt"
    assert {b.nombre for b in config.busquedas} >= {"servicios_logisticos", "salud_mental", "eventos"}


def test_config_invalida(tmp_path):
    ruta = tmp_path / "c.toml"
    ruta.write_text('[filtros]\nfecha_desde = "01/01/2024"\n[[busquedas]]\nnombre="x"\nfrases=["A"]\n')
    with pytest.raises(ConfigError, match="AAAA-MM-DD"):
        cargar_config(ruta)
    ruta.write_text('[[busquedas]]\nnombre="x"\n')
    with pytest.raises(ConfigError, match="frases"):
        cargar_config(ruta)


def test_tildes_y_variantes():
    assert quitar_tildes("LOGÍSTICOS CAMPAÑAS") == "LOGISTICOS CAMPAÑAS"
    assert variantes("servicios  logísticos") == ["SERVICIOS LOGÍSTICOS", "SERVICIOS LOGISTICOS"]
    assert variantes("eventos") == ["EVENTOS"]


def test_condicion_escapa_comillas():
    assert condicion_frase("D'ARTE", ["c"]) == "(upper(c) like '%D''ARTE%')"


def test_where_combina_frases_todas_y_filtros():
    config = cargar_config(RAIZ / "config.toml")
    config.filtros.fecha_desde, config.filtros.departamento = "2025-01-01", "Bogotá"
    b = Busqueda(nombre="x", frases=["EVENTOS", "FERIAS"], todas=["SALUD MENTAL"])
    w = where_completo(b, config)
    assert "upper(descripci_n_del_procedimiento) like '%EVENTOS%'" in w
    assert "upper(nombre_del_procedimiento) like '%SALUD MENTAL%'" in w
    assert "fecha_de_publicacion_del >= '2025-01-01T00:00:00'" in w
    assert "upper(departamento_entidad) like '%BOGOTA%'" in w
    assert w.count(" AND ") == 3


def test_paginacion_completa_y_maximo():
    registros = [{"id_del_proceso": str(i)} for i in range(25)]
    cliente = ClienteSocrata("https://x/resource/y.json", token="", sesion=SesionFalsa(registros))
    paginas = list(cliente.paginar("1=1", "fecha", 10))
    assert [len(p) for p in paginas] == [10, 10, 5]
    paginas = list(cliente.paginar("1=1", "fecha", 10, maximo=12))
    assert sum(len(p) for p in paginas) == 12


def test_reintenta_ante_429_y_falla_ante_400():
    sesion = SesionFalsa([{"a": 1}], errores=[429, 503])
    cliente = ClienteSocrata("https://x", token="T", sesion=sesion, espera_base=0)
    assert cliente.get({"$limit": 1}) == [{"a": 1}]
    assert sesion.headers["X-App-Token"] == "T"
    cliente = ClienteSocrata("https://x", token="", sesion=SesionFalsa([], errores=[400]), espera_base=0)
    with pytest.raises(ErrorAPI, match="400"):
        cliente.get({})


def test_consolidar_marca_las_busquedas_de_cada_proceso():
    a = exportar.a_tabla([{"id_del_proceso": "1", "precio_base": "100", "urlproceso": {"url": "u"}},
                          {"id_del_proceso": "2", "precio_base": "50"}])
    b = exportar.a_tabla([{"id_del_proceso": "1", "precio_base": "100"}])
    todo = exportar.consolidar({"eventos": a, "salud": b})
    assert len(todo) == 2
    assert todo.set_index("id_del_proceso").loc["1", "busquedas"] == "eventos, salud"
    assert todo.columns[0] == "busquedas" and a["precio_base"].sum() == 150
    assert "urlproceso" in a.columns


def test_buscar_genera_excel_y_csv(tmp_path, monkeypatch):
    registros = [{"id_del_proceso": f"CO1.{i}", "entidad": "ALCALDIA", "precio_base": "1000",
                  "fecha_de_publicacion_del": "2025-03-01T00:00:00.000"} for i in range(3)]
    monkeypatch.setattr("secop.cliente.requests.Session", lambda: SesionFalsa(registros))
    assert main(["-c", str(RAIZ / "config.toml"), "buscar", "--solo", "eventos", "salud_mental",
                 "--salida", str(tmp_path)]) == 0
    carpeta = next(tmp_path.iterdir())
    hojas = pd.read_excel(carpeta / "procesos_secop.xlsx", sheet_name=None)
    assert set(hojas) == {"resumen", "por_entidad", "todos", "eventos", "salud_mental"}
    assert len(hojas["todos"]) == 3
    assert (carpeta / "eventos.csv").exists()
