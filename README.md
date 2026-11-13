# FitLife

Aplicación web para controlar membresías, simular el ingreso al gimnasio y reservar clases grupales. El administrador trabaja desde un panel propio y los socios pueden consultar su membresía y sus reservas.

Acceso a la aplicación: [http://44.211.20.141](http://44.211.20.141)

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
prompts_ia.md           Registro de apoyo de IA
```

## Despliegue en AWS

El despliegue en EC2 está pendiente. La entrega requiere una instancia de AWS Academy con PostgreSQL y Django en la misma máquina, accesible mediante su IP pública o DNS. Cuando se realice el despliegue, este README debe incluir esa dirección y los pasos efectivos de instalación.

Será necesario configurar las variables de entorno, migraciones, archivos estáticos, servidor de aplicación y el proceso `revisar_esperas` como servicio. La configuración de desarrollo y la contraseña compartida no deben quedar expuestas en la instancia pública.

### Preparación de Ubuntu

Estos pasos suponen Ubuntu con el usuario `ubuntu`, una instancia nueva y el puerto 80 habilitado. El despliegue todavía no se ha verificado en EC2 y la IP pública debe añadirse aquí después de la instalación.

```bash
sudo apt update
sudo apt install -y git python3 python3-venv python3-pip postgresql postgresql-contrib nginx
cd /home/ubuntu
git clone https://github.com/wAstralChxrry/Control-Asistencia-y-Reserva-de-Clases-FitLife.git fitlife
cd fitlife
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt gunicorn
```

Crear el usuario y la base de PostgreSQL con `sudo -u postgres psql`. Elegir una contraseña propia y usarla también en `.env`:

```sql
CREATE USER fitlife WITH PASSWORD 'CAMBIAR_POR_UNA_CONTRASENA';
CREATE DATABASE fitlife OWNER fitlife;
\q
```

Generar una clave para Django con `python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"`. Crear `.env` con `nano .env`, reemplazando la clave, la IP elástica y la contraseña:

```env
DEBUG=False
SECRET_KEY=CLAVE_GENERADA
ALLOWED_HOSTS=IP_ELASTICA,localhost,127.0.0.1
POSTGRES_DB=fitlife
POSTGRES_USER=fitlife
POSTGRES_PASSWORD=CONTRASENA_DE_POSTGRESQL
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
```

```bash
chmod 600 .env
echo "STATIC_ROOT = BASE_DIR / 'staticfiles'" >> config/settings.py
python manage.py migrate
python manage.py collectstatic --noinput
python manage.py createsuperuser
```

La línea de `STATIC_ROOT` se añade solo una vez. La cuenta administradora creada en EC2 pertenece a la nueva base de datos; las cuentas y los datos del equipo local no se copian automáticamente.

### Servicios

Crear `/etc/systemd/system/fitlife.service`:

```ini
[Unit]
Description=Aplicacion FitLife
After=network.target postgresql.service

[Service]
User=ubuntu
Group=ubuntu
WorkingDirectory=/home/ubuntu/fitlife
ExecStart=/home/ubuntu/fitlife/.venv/bin/gunicorn --workers 2 --bind 127.0.0.1:8000 config.wsgi:application
Restart=always

[Install]
WantedBy=multi-user.target
```

Crear `/etc/systemd/system/fitlife-espera.service`:

```ini
[Unit]
Description=Revision de lista de espera FitLife
After=network.target postgresql.service

[Service]
User=ubuntu
Group=ubuntu
WorkingDirectory=/home/ubuntu/fitlife
ExecStart=/home/ubuntu/fitlife/.venv/bin/python manage.py revisar_esperas
Restart=always

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now fitlife fitlife-espera
sudo systemctl status fitlife --no-pager
sudo systemctl status fitlife-espera --no-pager
```

### Nginx

Permitir el acceso de Nginx a los archivos estáticos y crear `/etc/nginx/sites-available/fitlife`:

```bash
chmod o+x /home/ubuntu
chmod o+rx /home/ubuntu/fitlife
sudo nano /etc/nginx/sites-available/fitlife
```

```nginx
server {
    listen 80;
    server_name _;

    location /static/ {
        alias /home/ubuntu/fitlife/staticfiles/;
    }

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

En una instancia nueva, habilitar el sitio y deshabilitar el predeterminado de Nginx:

```bash
sudo ln -s /etc/nginx/sites-available/fitlife /etc/nginx/sites-enabled/fitlife
sudo rm /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl restart nginx
```

Abrir `http://IP_ELASTICA/` y entrar con la cuenta creada. El panel técnico está en `/admin/`. La conexión HTTP no cifra las contraseñas; usar una clave distinta para la evaluación y restringir el acceso a la instancia. La simulación QR no requiere cámara.

Para diagnosticar problemas:

```bash
sudo journalctl -u fitlife -n 50 --no-pager
sudo journalctl -u fitlife-espera -n 50 --no-pager
sudo tail -n 50 /var/log/nginx/error.log
```
