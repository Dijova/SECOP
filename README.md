# Extracción de procesos SECOP II

Programa en Python que descarga procesos de contratación pública de **SECOP II**
desde el portal de datos abiertos de Colombia ([datos.gov.co](https://www.datos.gov.co))
y los guarda en **Excel y CSV**, filtrados por palabras clave como:

- servicios logísticos
- procesos de salud mental / riesgo psicosocial / redes de apoyo comunitario
- eventos
- capacitaciones
- procesos de formación

La fuente es el conjunto de datos **SECOP II – Procesos de Contratación**
(identificador `p6dx-8zbt`). La documentación del proceso completo, paso a paso, está más abajo.

---

## Índice

1. [Cómo funciona](#1-cómo-funciona)
2. [Paso 1 – Instalar Python](#paso-1--instalar-python)
3. [Paso 2 – Descargar este proyecto](#paso-2--descargar-este-proyecto)
4. [Paso 3 – Crear el entorno virtual e instalar dependencias](#paso-3--crear-el-entorno-virtual-e-instalar-dependencias)
5. [Paso 4 – (Recomendado) Obtener un App Token de datos.gov.co](#paso-4--recomendado-obtener-un-app-token-de-datosgovco)
6. [Paso 5 – Probar la conexión con la fuente](#paso-5--probar-la-conexión-con-la-fuente)
7. [Paso 6 – Configurar qué buscar](#paso-6--configurar-qué-buscar-configtoml)
8. [Paso 7 – Contar resultados antes de descargar](#paso-7--contar-resultados-antes-de-descargar)
9. [Paso 8 – Descargar los datos](#paso-8--descargar-los-datos)
10. [Paso 9 – Revisar los resultados](#paso-9--revisar-los-resultados)
11. [Verificar una consulta en el navegador](#verificar-una-consulta-en-el-navegador)
12. [Problemas comunes](#problemas-comunes)
13. [Estructura del proyecto](#estructura-del-proyecto)
14. [Detalles técnicos de la API](#detalles-técnicos-de-la-api)

---

## 1. Cómo funciona

```
config.toml ──► secop/consulta.py ──► secop/cliente.py ──► datos.gov.co (API SODA)
 (qué buscar)    arma el filtro         descarga por                │
                 SoQL ($where)          páginas, con reintentos     ▼
                                                        secop/exportar.py
                                                   salidas/AAAAMMDD_HHMMSS/
                                                   ├─ procesos_secop.xlsx
                                                   ├─ todos_los_procesos.csv
                                                   └─ <una_por_busqueda>.csv
```

1. Usted define las palabras a buscar en `config.toml`.
2. El programa convierte cada búsqueda en una condición de filtro (`$where`) del
   lenguaje de consulta de Socrata (SoQL). Busca en la **descripción** y en el
   **nombre** del procedimiento, sin importar mayúsculas y con y sin tildes.
3. Primero pregunta a la API cuántos procesos coinciden y luego los descarga en
   páginas de 10.000 registros, reintentando si la API está saturada.
4. Guarda una hoja de Excel por búsqueda, una hoja consolidada sin duplicados y
   un resumen por entidad.

---

## Paso 1 – Instalar Python

Necesita **Python 3.11 o superior**.

- **Windows:** descárguelo de <https://www.python.org/downloads/>. En el instalador
  marque la casilla **"Add Python to PATH"**.
- **macOS:** `brew install python@3.12`, o el instalador de python.org.
- **Linux (Ubuntu/Debian):** `sudo apt install python3 python3-venv python3-pip`

Verifique la instalación en una terminal (en Windows, *PowerShell* o *Símbolo del sistema*):

```bash
python --version      # en macOS/Linux puede ser: python3 --version
```

Debe mostrar `Python 3.11.x` o superior.

---

## Paso 2 – Descargar este proyecto

**Opción A – con Git:**

```bash
git clone https://github.com/Dijova/SECOP.git
cd SECOP
```

**Opción B – sin Git:** en GitHub pulse **Code → Download ZIP**, descomprima el
archivo y abra una terminal dentro de la carpeta descomprimida.

> Todos los comandos siguientes se ejecutan **dentro de la carpeta del proyecto**
> (donde está `config.toml`).

---

## Paso 3 – Crear el entorno virtual e instalar dependencias

El entorno virtual aísla las librerías del proyecto del resto de su computador.

**Windows (PowerShell):**

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

> Si PowerShell bloquea la activación, ejecute una vez
> `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` y vuelva a intentarlo.

**macOS / Linux:**

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Cuando el entorno está activo, la terminal muestra `(.venv)` al inicio de la línea.
**Cada vez que abra una terminal nueva** debe activarlo otra vez (solo la línea
`Activate.ps1` o `source ...`).

Se instalan tres librerías: `requests` (conexión a la API), `pandas` (tablas) y
`openpyxl` (escritura de Excel).

---

## Paso 4 – (Recomendado) Obtener un App Token de datos.gov.co

Sin token la API funciona, pero limita el número de consultas y puede responder
`HTTP 429 – Too Many Requests` en descargas grandes. El token es gratuito:

1. Entre a <https://www.datos.gov.co> y pulse **Iniciar sesión** → cree una cuenta.
2. Vaya a su perfil → **Configuración del desarrollador** (*Developer Settings*):
   <https://www.datos.gov.co/profile/edit/developer_settings>
3. Pulse **Crear nuevo token de aplicación** (*Create New App Token*), escriba un
   nombre (ej. "Extraccion SECOP") y guarde.
4. Copie el valor de **App Token** (no el *Secret Token*).
5. Configúrelo como variable de entorno en la terminal donde ejecutará el programa:

   **Windows (PowerShell):**
   ```powershell
   $env:SOCRATA_APP_TOKEN = "su_token_aqui"
   ```
   Para dejarlo permanente: `setx SOCRATA_APP_TOKEN "su_token_aqui"` y abra una terminal nueva.

   **macOS / Linux:**
   ```bash
   export SOCRATA_APP_TOKEN="su_token_aqui"
   ```
   Para dejarlo permanente, agregue esa línea a `~/.bashrc` o `~/.zshrc`.

También puede pasarlo directamente: `python -m secop --token su_token_aqui buscar`.

> No suba el token a GitHub ni lo escriba en `config.toml`.

---

## Paso 5 – Probar la conexión con la fuente

```bash
python -m secop probar
```

Resultado esperado: la frase `Conexión correcta` y la lista de **columnas** del
conjunto de datos con un valor de ejemplo, por ejemplo:

```
  entidad                                       ALCALDIA MUNICIPAL DE ...
  departamento_entidad                          Antioquia
  id_del_proceso                                CO1.REQ.1234567
  descripci_n_del_procedimiento                 PRESTAR SERVICIOS ...
  fecha_de_publicacion_del                      2025-03-01T00:00:00.000
  precio_base                                   45000000
  urlproceso                                    {'url': 'https://community.secop.gov.co/...'}
  ...
```

Si aparece un **Aviso** de que alguna columna de `config.toml` no existe, busque
en la lista el nombre correcto y corríjalo en la sección `[fuente]` de `config.toml`.

---

## Paso 6 – Configurar qué buscar (`config.toml`)

Abra `config.toml` con cualquier editor de texto (Bloc de notas, VS Code…).

### 6.1 Filtros generales (sección `[filtros]`)

Se aplican a **todas** las búsquedas. Deje `""` para no usar un filtro.

| Clave | Ejemplo | Efecto |
|---|---|---|
| `fecha_desde` | `"2024-01-01"` | procesos publicados desde esa fecha |
| `fecha_hasta` | `"2025-12-31"` | procesos publicados hasta esa fecha |
| `departamento` | `"Antioquia"` | solo entidades de ese departamento |
| `ciudad` | `"Medellín"` | solo entidades de esa ciudad |
| `entidad_contiene` | `"SECRETARIA DE SALUD"` | el nombre de la entidad contiene el texto |
| `where_extra` | `"estado_del_procedimiento = 'Adjudicado'"` | condición SoQL libre (avanzado) |

### 6.2 Búsquedas (bloques `[[busquedas]]`)

Cada bloque es una búsqueda y produce su propia hoja en el Excel:

```toml
[[busquedas]]
nombre = "servicios_logisticos"          # nombre de la hoja/archivo (sin espacios)
frases = ["SERVICIOS LOGÍSTICOS", "OPERADOR LOGÍSTICO"]   # CUALQUIERA de estas

[[busquedas]]
nombre = "salud_mental"
todas = ["SALUD MENTAL", "PSICOSOCIAL"]  # deben aparecer TODAS
```

Reglas:

- **`frases`**: el proceso entra si contiene *al menos una* de las frases (O).
- **`todas`**: el proceso entra solo si contiene *todas* las frases (Y). Sirve
  para objetos largos: en lugar del párrafo completo, use 2 o 3 frases que lo
  identifiquen (ej. `"SALUD MENTAL"` + `"PSICOSOCIAL"`).
- Se pueden combinar `frases` y `todas` en el mismo bloque.
- No importan las mayúsculas. **Escriba con tilde**: el programa agrega solo la
  versión sin tilde (`CAPACITACIÓN` también encuentra `CAPACITACION`).
- Se busca en la descripción y en el nombre del procedimiento (`campos_busqueda`).

La configuración incluida ya trae las búsquedas de: servicios logísticos, salud
mental (por palabras clave y por el texto exacto del objeto), eventos,
capacitaciones y procesos de formación.

> **Ojo:** `EVENTOS` y `CAPACITACIONES` son palabras muy comunes y pueden
> devolver decenas de miles de procesos. Acote con `fecha_desde`, `departamento`
> o `entidad_contiene`, o combine en `todas` (ej. `todas = ["EVENTOS", "LOGÍSTIC"]`).

---

## Paso 7 – Contar resultados antes de descargar

```bash
python -m secop contar
```

Ejemplo de salida:

```
servicios_logisticos                1.234 procesos
salud_mental                          587 procesos
eventos                            18.902 procesos
...
```

Use esto para ajustar los filtros antes de descargar. Para contar solo algunas
búsquedas: `python -m secop contar --solo eventos capacitaciones`.

---

## Paso 8 – Descargar los datos

```bash
python -m secop buscar
```

Opciones útiles:

| Comando | Para qué |
|---|---|
| `python -m secop buscar --solo salud_mental` | ejecutar solo una o varias búsquedas |
| `python -m secop buscar --maximo 500` | descargar como máximo 500 procesos por búsqueda (prueba rápida) |
| `python -m secop buscar --salida D:\reportes` | guardar en otra carpeta |
| `python -m secop buscar --mostrar-consulta` | imprimir la URL de cada consulta |
| `python -m secop -c otra_config.toml buscar` | usar otro archivo de configuración |
| `python -m secop -v buscar` | ver detalles (reintentos, etc.) |

Durante la descarga verá el avance (`3.000 / 18.902`). Para cancelar: `Ctrl + C`.

---

## Paso 9 – Revisar los resultados

Cada ejecución crea una carpeta nueva con fecha y hora, por ejemplo
`salidas/20261016_153000/`, con:

| Archivo | Contenido |
|---|---|
| `procesos_secop.xlsx` | Excel con las hojas descritas abajo |
| `todos_los_procesos.csv` | todos los procesos, sin duplicados |
| `<nombre_busqueda>.csv` | un CSV por búsqueda |

Hojas del Excel:

- **resumen**: por búsqueda, procesos en la fuente, procesos descargados,
  entidades distintas y suma del precio base.
- **por_entidad**: número de procesos y suma del precio base por entidad.
- **todos**: todos los procesos sin repetir; la columna `busquedas` indica en
  qué búsquedas apareció cada uno (ej. `eventos, capacitaciones`).
- **una hoja por búsqueda**.

Las primeras columnas son las más útiles (entidad, departamento, ciudad, id y
referencia del proceso, descripción, estado, modalidad, fecha, precio base,
proveedor, `urlproceso` con el enlace al proceso en SECOP II). Las demás
columnas de la fuente van a continuación.

Los CSV usan UTF-8 con BOM, así Excel muestra bien las tildes al abrirlos.

---

## Verificar una consulta en el navegador

Con `--mostrar-consulta` el programa imprime una URL como:

```
https://www.datos.gov.co/resource/p6dx-8zbt.json?%24where=...&%24limit=100
```

Péguela en el navegador para ver los primeros 100 registros en JSON. También
puede escribir consultas a mano, por ejemplo:

```
https://www.datos.gov.co/resource/p6dx-8zbt.json?$q=servicios logisticos&$limit=50
https://www.datos.gov.co/resource/p6dx-8zbt.json?$where=upper(descripci_n_del_procedimiento) like '%SALUD MENTAL%'&$limit=50
```

Y la ficha del conjunto de datos, con la lista oficial de columnas:
<https://www.datos.gov.co/Gastos-Gubernamentales/SECOP-II-Procesos-de-Contrataci-n/p6dx-8zbt>

---

## Problemas comunes

| Síntoma | Causa y solución |
|---|---|
| `python` no se reconoce | Python no está en el PATH. Reinstale marcando "Add Python to PATH", o use `py` (Windows) / `python3` (macOS/Linux). |
| `No module named 'requests'` (o pandas) | El entorno virtual no está activo o faltó el paso 3. Actívelo e instale con `pip install -r requirements.txt`. |
| `No module named 'tomllib'` | Su Python es anterior a 3.11. Instale una versión más nueva. |
| `Error de configuración: ...` | El mensaje indica qué corregir en `config.toml` (ej. formato de fecha `AAAA-MM-DD`). |
| `HTTP 429` o muchos reintentos | Demasiadas consultas sin token. Configure el App Token (paso 4). |
| `HTTP 400 ... no-such-column` | Un nombre de columna no existe. Ejecute `python -m secop probar` y corrija `[fuente]` o `where_extra`. |
| `No fue posible conectarse` | Sin internet, o un proxy/firewall bloquea `www.datos.gov.co`. Pruebe abrir la URL en el navegador. |
| La descarga es muy lenta | La búsqueda es muy amplia. Revise `contar` y acote con filtros o `--maximo`. |
| 0 resultados | Revise la ortografía, quite palabras de `todas`, o amplíe las fechas. Pruebe la consulta en el navegador. |

---

## Estructura del proyecto

```
SECOP/
├─ config.toml           ← lo que usted edita: fuente, filtros y búsquedas
├─ requirements.txt      ← librerías necesarias
├─ secop/
│  ├─ cli.py             ← comandos probar / contar / buscar
│  ├─ config.py          ← lectura y validación de config.toml
│  ├─ consulta.py        ← construcción del filtro SoQL ($where)
│  ├─ cliente.py         ← conexión a la API: token, paginación y reintentos
│  └─ exportar.py        ← limpieza, consolidación, CSV y Excel
└─ tests/                ← pruebas automáticas (pytest)
```

Para ejecutar las pruebas:

```bash
pip install -r requirements-dev.txt
python -m pytest
```

---

## Detalles técnicos de la API

- **Endpoint usado:** `https://www.datos.gov.co/resource/p6dx-8zbt.json` (API SODA 2.1
  de Socrata), consultado con `GET`.
- El endpoint `https://www.datos.gov.co/api/v3/views/p6dx-8zbt/query.json` (SODA 3)
  devuelve los mismos datos, pero exige token y peticiones `POST` con la consulta en
  el cuerpo. El 2.1 es más simple y no requiere token, por eso se usa aquí.
- **Parámetros SoQL:** `$where` (filtro), `$order` (orden), `$limit` y `$offset`
  (paginación, máximo 50.000 por página), `$select=count(*)` (conteo).
- La paginación ordena por fecha de publicación descendente y luego por `:id`
  (identificador interno de la fila), para que ningún registro se repita ni se
  pierda entre páginas.
- **Reintentos:** ante errores de conexión o respuestas HTTP 429/500/502/503/504
  se reintenta hasta 4 veces, esperando 2, 4, 8 y 16 segundos.
- **Token:** se envía en el encabezado `X-App-Token`.
- Documentación oficial de SoQL: <https://dev.socrata.com/docs/queries/>
