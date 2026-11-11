# FitLife

Aplicación web para controlar membresías, simular el ingreso al gimnasio y reservar clases grupales. El administrador trabaja desde un panel propio y los socios pueden consultar su membresía y sus reservas.

## Funcionalidades

- Administración de socios, planes, pagos, membresías y clases.
- Membresías activas, vencidas o congeladas, con control de fechas.
- Registro simulado de entradas y salidas mediante el código del QR.
- Reservas con cupos y lista de espera; los cupos libres se asignan a socios habilitados por orden de llegada.
- Dashboard con aforo, próximos horarios y últimos movimientos. El aforo se consulta cada dos segundos.
- Datos de demostración que se pueden cargar y eliminar desde el dashboard.
- Django Admin para consultar y administrar modelos; accesos y reservas son de solo lectura en ese panel.

La aplicación utiliza Django, Django REST Framework, PostgreSQL y templates HTML con CSS y JavaScript. La interfaz se sirve desde Django; no se ha implementado una API pública para los flujos descritos.

## Requisitos

- Python y `pip`.
- PostgreSQL en ejecución, con una base de datos y un usuario con permisos sobre ella.
- PowerShell para los comandos de Windows que aparecen a continuación.

## Instalación local

Desde la carpeta del proyecto:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

Editar `.env` con el nombre, usuario, contraseña, servidor y puerto de PostgreSQL. Crear la base de datos antes de ejecutar las migraciones. El archivo `.env` no se debe subir al repositorio.

```powershell
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Abrir `http://127.0.0.1:8000/`. Django Admin está en `http://127.0.0.1:8000/admin/`.

Si no se define `POSTGRES_DB`, el proyecto usa SQLite para desarrollo. Para cumplir el caso se debe configurar PostgreSQL.

### Lista de espera

En otra terminal, con el entorno virtual activo, ejecutar:

```powershell
python manage.py revisar_esperas
```

Este proceso revisa las listas cada 30 segundos. Debe permanecer activo junto al servidor para que se asignen cupos cuando una membresía entre en vigencia por el paso del tiempo.

## Uso

### Administrador

1. Crear un plan y una cuenta desde **Socios**.
2. Asignar al socio una membresía con fechas y estado; registrar su pago en **Pagos**.
3. Crear clases con horario y cupos. Desde **Reservas** se pueden administrar las inscripciones y consultar participantes y espera.
4. En **Control de acceso**, ingresar el código del socio y seleccionar entrada o salida.

La entrada requiere una cuenta activa y una membresía vigente. Se puede registrar la salida aunque la membresía ya no esté vigente. El aforo se calcula con las entradas que aún no tienen una salida registrada.

El dashboard permite cargar datos de demostración y eliminarlos. Si hay registros ajenos vinculados que podrían verse afectados, la eliminación se detiene. Con la demo cargada, **Generar acceso de socio** muestra el usuario de una cuenta de prueba. Las cuentas existentes y las que crea la demo se configuraron con la contraseña `admin123` para la evaluación local. Los socios creados manualmente utilizan la contraseña asignada en el formulario. Esta clave compartida debe cambiarse antes de exponer el sistema públicamente.

Los horarios de la demostración están fijados para el 12, 13 y 14 de noviembre de 2026, en horario de Santiago. Deben actualizarse si se utiliza la demostración después de esas fechas.

### Socio

El administrador crea la cuenta; no hay registro público. El socio puede iniciar sesión, ver su plan y código QR, reservar o cancelar clases, consultar su posición en espera, editar sus datos y cambiar su contraseña.

La lectura QR es una **simulación**: se copia el código mostrado al socio y se ingresa en el panel de acceso. No hay lectura por cámara ni pagos en línea.

## Comprobación

```powershell
python manage.py check
python manage.py test
```

Las pruebas utilizan una base temporal. El usuario de PostgreSQL necesita permisos para crearla. La medición local del acceso y sus límites están en `docs/medicion-acceso-qr.md`.

## Estructura

```text
config/                 Configuración y rutas de Django
gimnasio/               Modelos, vistas, formularios, servicios y pruebas
  management/commands/  Revisión de espera y medición de acceso
  migrations/           Migraciones de base de datos
static/                 CSS, JavaScript e icono
templates/              Plantillas HTML
docs/                   Medición del acceso QR
prompts_ia.md           Registro reconstruido de apoyo de IA
```

## Despliegue en AWS

El despliegue en EC2 está pendiente. La entrega requiere una instancia de AWS Academy con PostgreSQL y Django en la misma máquina, accesible mediante su IP pública o DNS. Cuando se realice el despliegue, este README debe incluir esa dirección y los pasos efectivos de instalación.

Será necesario configurar las variables de entorno, migraciones, archivos estáticos, servidor de aplicación y el proceso `revisar_esperas` como servicio. La configuración de desarrollo y la contraseña compartida no deben quedar expuestas en la instancia pública.
