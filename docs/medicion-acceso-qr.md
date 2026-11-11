# Medición local del acceso QR

Fecha: 11 de noviembre de 2026.

Se midió la vista Django que procesa la simulación de entrada, con PostgreSQL local y una membresía activa en una base de datos temporal. Se ejecutaron 20 muestras secuenciales; cada operación se revirtió y la base temporal se eliminó al finalizar.

| Indicador | Tiempo |
| --- | ---: |
| Mínimo | 3,97 ms |
| Promedio | 5,11 ms |
| Máximo | 24,34 ms |

La medición cubre el procesamiento local de la vista y la base de datos. No incluye red, navegador, cámara ni usuarios simultáneos, y no garantiza los tiempos que se obtendrán en EC2.

Para repetir la medición en una base de prueba con un administrador y una membresía existentes:

```powershell
python manage.py medir_acceso_qr --membresia ID --muestras 20
```

El comando revierte los registros y cambios de aforo, pero PostgreSQL puede avanzar el contador interno de identificadores. Por ello conviene utilizar una base de prueba.
