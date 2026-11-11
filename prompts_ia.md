# Registro de uso de inteligencia artificial

## 1. Entender el caso y planificar

> Lee el caso de FitLife y su rúbrica. Organiza un roadmap para construir el sistema con Django, Django REST Framework y PostgreSQL. Separa membresías, pagos, control de acceso, clases, lista de espera y aforo. El gimnasio debe tener un dashboard propio y Django Admin debe quedar habilitado aparte.

**Apoyo:** se organizó el trabajo por etapas y se definieron los perfiles de administrador y socio.

## 2. Precisar el alcance

> Considera pagos registrados por el administrador, entradas y salidas mediante simulación de QR y asignación automática de cupos. La cámara es opcional. Deja el despliegue en EC2 para el final y considera que la cámara puede necesitar HTTPS.

**Apoyo:** se aclararon las decisiones de implementación y las limitaciones de la simulación.

## 3. Construir la aplicación

> Implementa el roadmap con Django y PostgreSQL. Crea modelos, migraciones, formularios, vistas y templates responsivos. El administrador debe gestionar el gimnasio desde su dashboard y el socio debe consultar su membresía y reservas. Mantén los directorios y el código ordenados.

**Apoyo:** se generó y ajustó la estructura inicial del proyecto y sus funcionalidades.

## 4. Configurar la base de datos

> Conecta el proyecto a PostgreSQL, aplica las migraciones y comprueba que el backend pueda trabajar con la base de datos. Mantén las credenciales fuera de los archivos que se suben al repositorio.

**Apoyo:** se configuró la conexión local mediante variables de entorno y se aplicaron las migraciones.

## 5. Revisar y mejorar la interfaz

> Revisa las pantallas de FitLife. Usa templates de Django y crea una interfaz propia para un gimnasio, con navegación clara y un inicio de sesión sencillo. Comprueba que los estilos y el favicon carguen correctamente.

**Apoyo:** se modificaron las plantillas, los estilos y el icono; se revisó la pantalla de acceso en el navegador.

## 6. Auditar contra la rúbrica

> Revisa el sistema como administrador y como socio según el informe. Comprueba permisos, CRUD, membresías, control de acceso, aforo, reservas y Django Admin. Indica los errores encontrados antes de corregirlos y trabaja con datos aislados.

**Apoyo:** se emplearon subagentes para revisar los recorridos y señalar problemas de contraseñas, cupos, estados, permisos y visibilidad de datos.

## 7. Corregir reglas y permisos

> Corrige los problemas detectados: conservar la contraseña al editar un socio, respetar los cupos ante operaciones simultáneas, proteger el historial en Django Admin y mostrar correctamente las membresías vencidas. Permite al socio editar sus propios datos y al administrador gestionar reservas.

**Apoyo:** se ajustaron formularios, permisos, operaciones transaccionales, listas de espera y pantallas administrativas.

## 8. Preparar datos de demostración

> Añade un control en el dashboard para cargar y retirar datos de ejemplo: planes Bronce, Plata y Oro, socios, pagos, clases, reservas y movimientos. Evita borrar registros reales al retirar la demo.

**Apoyo:** se creó la carga identificada de datos de prueba y se corrigió el caso de reservas reasignadas a datos reales.

## 9. Resolver los últimos hallazgos

> Corrige la hora de las reservas, advierte que eliminar una clase borra sus inscripciones, mejora la actualización del aforo y revisa automáticamente la espera cuando comienza la vigencia de una membresía. Permite acceder con un socio de prueba y mide la simulación QR.

**Apoyo:** se ajustó la hora local, se añadió una revisión periódica de espera y se registró una medición local de la vista de acceso. Para la evaluación local se solicitó usar `admin123` en las cuentas existentes y las creadas por la demo.

## 10. Documentar

> Actualiza el README con la instalación, configuración, roles, uso y limitaciones. Reconstruye los prompts de la conversación en un archivo separado e indica que no son citas textuales. Deja claro que el despliegue en EC2 sigue pendiente.

**Apoyo:** se prepararon el README y este registro. Los resultados y la configuración deben revisarse durante la preparación de la entrega.

## 11. Ajustar fechas y preparar el repositorio

> Ajusta los datos de demostración para que las clases comiencen el jueves y sirvan para una presentación el viernes. Actualiza la documentación y prepara un repositorio público en GitHub, sin incluir archivos de configuración local ni la base de datos.

**Apoyo:** se programaron las clases de ejemplo para el 12, 13 y 14 de noviembre de 2026 y se prepararon los archivos para el repositorio. La publicación en AWS permanece pendiente.

## 12. Preparar la instalación en AWS

> La instancia EC2 de Ubuntu ya está creada con IP elástica y grupos de seguridad. Explica cómo clonar el repositorio, configurar PostgreSQL y Django, iniciar la aplicación y mantener activa la revisión de la lista de espera.

**Apoyo:** se prepararon instrucciones para instalar dependencias, configurar la base de datos y las variables de entorno, ejecutar Gunicorn y el proceso de espera con systemd y servir la aplicación con Nginx. La instalación en EC2 aún debe verificarse.
