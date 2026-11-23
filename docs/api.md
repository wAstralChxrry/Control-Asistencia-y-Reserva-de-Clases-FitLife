# API de FitLife

La API está en desarrollo y se sirve bajo `/api/`. El inicio de sesión y Django Admin existentes siguen usando sesiones de Django.

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

## Datos de demostración

Los endpoints administrativos `GET /api/demo/estado/` y `POST /api/demo/cargar/`, `/api/demo/eliminar/` y `/api/demo/acceso/` comparten las reglas de la interfaz Django. En desarrollo se conserva la clave de demostración `admin123`. Con `DEBUG=False`, se debe configurar `FITLIFE_DEMO_PASSWORD` con una clave que cumpla los validadores; la aplicación no cambia contraseñas de usuarios existentes automáticamente.

## Frontend local

Con Django en `127.0.0.1:8000`, ejecutar en otra terminal:

```bash
cd frontend
npm install
npm run dev
```

Vite entrega la interfaz en `http://127.0.0.1:5173/` y envía `/api/` al backend local. Este proxy es solo para desarrollo; la configuración de API Gateway, HTTPS y EC2 frontend todavía está pendiente. La sesión React se guarda en memoria y se cierra al recargar la página.

## Estado de verificación

Las pruebas `python manage.py test api` cubren autenticación, permisos, operaciones de planes y reservas, aforo y perfil. También se ejecutaron con PostgreSQL, incluyendo una prueba de dos reservas simultáneas para una clase con un solo cupo. Se comprobó localmente la combinación Django 6.1.3, DRF 3.18.3 y Simple JWT 5.5.1 que se prevé utilizar en la EC2; no se ha instalado ni probado en la instancia.
