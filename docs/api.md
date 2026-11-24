# API de FitLife

La API se sirve bajo `/api/`. La interfaz React utiliza tokens JWT; las vistas Django y Django Admin usan sesiones de Django.

## Autenticación

`POST /api/token/` recibe `username` y `password` y devuelve tokens de acceso y renovación. `POST /api/token/refresh/` recibe el token de renovación. Las peticiones protegidas utilizan `Authorization: Bearer <token>`.

## Recursos

- `/api/socios/`, `/api/planes/`, `/api/membresias/` y `/api/pagos/`: operaciones CRUD para el administrador.
- `/api/clases/`: consulta para usuarios autenticados; escritura para el administrador. Incluye cupos disponibles.
- `/api/reservas/`: el administrador gestiona reservas; el socio ve las propias. Los socios usan `POST /api/reservas/reservar/` con `clase` y `POST /api/reservas/{id}/cancelar/`.
- `/api/mi-cuenta/`: consulta del usuario autenticado y edición parcial de datos del socio.
- `/api/mi-membresia/` y `/api/mi-qr/`: información y código QR del socio autenticado.
- `/api/aforo/`, `/api/resumen/` y `POST /api/accesos/`: funciones administrativas. El acceso recibe `codigo` y `tipo` (`entrada` o `salida`).

Las operaciones de reservas usan las reglas de membresía, límite de cupos y promoción de lista de espera. El código QR sigue siendo una simulación y no utiliza cámara.

Los planes usan `duracion_meses`. Al crear una membresía se puede omitir `fin`: se calcula por meses calendario desde `inicio`, incluyendo hasta el día anterior al aniversario. Las fechas existentes se conservan. Para reservar, la membresía debe cubrir también la fecha de la clase.

## Datos de demostración

Los endpoints administrativos `GET /api/demo/estado/` y `POST /api/demo/cargar/`, `/api/demo/eliminar/` y `/api/demo/acceso/` comparten las reglas de la interfaz Django. En desarrollo se usa la clave de demostración `admin123`. Con `DEBUG=False`, se debe configurar `FITLIFE_DEMO_PASSWORD` con una clave que cumpla los validadores. Al generar acceso se establece esa clave para un socio de demostración elegible.

## Frontend local

Con Django en `127.0.0.1:8000`, ejecutar en otra terminal:

```bash
cd frontend
npm install
npm run dev
```

Vite entrega la interfaz en `http://127.0.0.1:5173/` y envía `/api/` al backend local. En AWS, Nginx sirve el frontend y envía `/api/` a API Gateway. La sesión React se guarda en memoria y se cierra al recargar la página.

## Estado de verificación

Las pruebas `python manage.py test api gimnasio` cubren autenticación, permisos, planes, vigencias, reservas, aforo y perfil. Incluyen pruebas de concurrencia que requieren PostgreSQL.
