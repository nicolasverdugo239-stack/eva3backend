Dulce Arte — Gestión de pedidos, producción y despacho

Evaluación Parcial N.º 3 — Desarrollo Backend

Tecnologías: Django, Django REST Framework, PostgreSQL, Gunicorn, Nginx y AWS EC2.

Aplicación desplegada

\- Sitio web (HTTPS): https\://98.87.33.112/

\- Django Admin: https\://98.87.33.112/admin/

\- API REST: https\://98.87.33.112/api/

\- Repositorio: https\://github.com/nicolasverdugo239-stack/eva3backend

Nota: La instancia AWS EC2 utiliza la Elastic IP `98.87.33.112`, asociada al servidor Dulce Arte. Esta dirección permanece fija mientras la Elastic IP continúe asignada y el recurso no sea eliminado o restablecido por AWS Academy Learner Lab. El certificado de Let's Encrypt es de corta duración y requiere renovación periódica.



Descripción

Dulce Arte es una aplicación web para una pastelería artesanal. Centraliza la gestión de clientes, pedidos personalizados, cotizaciones, listas de materiales (BOM), inventario, producción y despachos. Integra una interfaz web, una API REST y el panel administrativo de Django, con autenticación y permisos diferenciados por rol.

Funcionalidades

\- Clientes y pedidos: registro, consulta, edición y gestión de pedidos personalizados, con fecha y hora de entrega, diseño, dirección y observaciones.

\- Cotizaciones: cálculo según costo de insumos BOM y mano de obra; envío, aprobación y rechazo.

\- Producción: tablero Kanban con etapas Recibido → En Preparación → Horneado/Decorado → Control de Calidad → Listo.

\- Inventario: validación de stock y descuento transaccional de insumos al iniciar producción; bloqueo si el stock es insuficiente.

\- Trazabilidad: registro de movimientos de inventario, responsables, saldos posteriores e historial de estados del pedido.

\- Cancelaciones: devolución controlada del stock reservado, evitando devoluciones duplicadas.

\- Despachos: planificación y registro de entrega, con comprobante de recepción, firma o imagen según el formulario utilizado.

\- Administración: Django Admin personalizado y API REST con controles de acceso.

Roles y seguridad

Los grupos de la aplicación son Ventas, Cocina, Bodega, Despacho y Administradores. Las consultas protegidas requieren inicio de sesión; las operaciones de escritura se restringen según el rol correspondiente. El administrador puede gestionar usuarios y grupos mediante Django Admin.



En producción se utilizan HTTPS, autenticación por sesión, permisos de Django/DRF, un proxy inverso Nginx y variables privadas para las credenciales. La base PostgreSQL no debe exponerse directamente a Internet.

Arquitectura

Navegador / cliente HTTP

          |

          | HTTPS (443)

          v

    Nginx en AWS EC2

      |           |

      |           +--> /static/ y /media/

      v

 Gunicorn (127.0.0.1:8000)

      |

      v

 Django + Django REST Framework

      |

      v

 PostgreSQL en la misma instancia EC2

Arquitectura 4+1

\- Vista lógica: modelos Customer, Order, OrderIngredient, Ingredient, InventoryMovement, OrderStatusHistory y Dispatch.

\- Vista de desarrollo: proyecto Django dulcearte y aplicación pedidos, con modelos, formularios, vistas, serializadores, rutas, permisos, Admin y pruebas.

\- Vista de procesos: autenticación, cotización, aprobación, consumo de insumos, transición de etapas y despacho.

\- Vista física: instancia Ubuntu 24.04 en AWS EC2, Nginx, Gunicorn, Django y PostgreSQL.

\- Escenarios (+1): registrar pedido; calcular y aprobar cotización; impedir producción sin stock; registrar ingreso de inventario; avanzar producción; confirmar entrega.

Tecnologías y requisitos

\- Python 3.11 o superior.

\- Django y Django REST Framework.

\- PostgreSQL para producción; SQLite como alternativa de desarrollo local cuando no se define DATABASE_URL.

\- Gunicorn como servidor WSGI en producción.

\- Nginx como proxy inverso y servidor de archivos estáticos.

\- AWS Academy Learner Lab / Amazon EC2 con Ubuntu 24.04.

\- Certbot y Let's Encrypt para HTTPS.

Las versiones exactas de los paquetes están definidas en requirements.txt.

Instalación local en Windows (PowerShell)

Desde la carpeta del repositorio:

python -m venv .venv

.\\.venv\Scripts\Activate.ps1

python -m pip install -r requirements.txt

$env:DJANGO_SECRET_KEY = "clave-local-de-desarrollo-cambiar"

$env:DJANGO_DEBUG = "True"

$env:DJANGO_ALLOWED_HOSTS = "127.0.0.1,localhost"

python manage.py migrate

python manage.py setup_roles

python manage.py createsuperuser

python manage.py runserver

Abrir http\://127.0.0.1:8000/ y acceder al panel administrativo en http\://127.0.0.1:8000/admin/.



Si PowerShell bloquea la activación del entorno virtual:

Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass

.\\.venv\Scripts\Activate.ps1

El comando setup_roles crea los grupos; para asignar usuarios, entrar a Admin → Usuarios y seleccionar sus grupos.

PostgreSQL local (opcional)

Crear una base de datos y un usuario PostgreSQL con permisos, y configurar DATABASE_URL en la consola:

$env:DATABASE_URL = "postgresql://USUARIO:CLAVE\@127.0.0.1:5432/NOMBRE_BASE"

python manage.py migrate

No guardar credenciales reales en archivos versionados.

API REST

La API se encuentra bajo /api/ y requiere una sesión autenticada y los permisos apropiados.

Recurso   Ruta

Clientes  /api/clientes/

Insumos   /api/insumos/

Pedidos   /api/pedidos/

Materiales de pedido (BOM)    /api/materiales-pedido/

Despachos /api/despachos/

Movimientos de inventario     /api/movimientos-inventario/





Acciones de negocio

\- POST /api/pedidos/{id}/quote/: gestionar cotización con quote_status (SENT, APPROVED, REJECTED; DRAFT para revisión cuando proceda).

\- POST /api/pedidos/{id}/advance/: avanzar a la siguiente etapa válida mediante status.

\- El stock de /api/insumos/ es de solo lectura; las entradas y salidas se registran en /api/movimientos-inventario/.

\- Los movimientos de inventario son auditables y no se editan ni eliminan desde la API.

\- Las acciones de la API respetan las mismas reglas de negocio que la interfaz web.

Despliegue real en AWS EC2

La aplicación fue desplegada en una instancia Ubuntu 24.04, dentro de AWS Academy, con los siguientes componentes:

Componente     Configuración desplegada

Instancia EC2, Ubuntu 24.04

IP pública utilizada     98.87.33.112

Carpeta del proyecto     /home/ubuntu/eva3backend

Entorno virtual     /home/ubuntu/eva3backend/.venv

Base de datos  PostgreSQL local en EC2

Base y usuario dulce_arte / dulce_arte_user

Servicio de aplicación   dulcearte.service (Gunicorn)

Proxy inverso  Nginx

HTTPS     Let's Encrypt, certificado para la IP pública

Puertos públicos    80 (redirección a HTTPS), 443 (HTTPS)

SSH  22, acceso restringido





1\. Preparación de la instancia

Instalar las dependencias del sistema en Ubuntu:

sudo apt update

sudo apt install -y python3-venv python3-dev build-essential libpq-dev postgresql nginx

En PostgreSQL, crear el usuario y la base de datos de producción con una contraseña privada. No abrir el puerto 5432 al público.

2\. Código y dependencias

cd /home/ubuntu

**# En una instalación nueva:**

git clone https\://github.com/nicolasverdugo239-stack/eva3backend.git

cd eva3backend

python3 -m venv .venv

source .venv/bin/activate

pip install -r requirements.txt

Para una instalación existente, actualizar el código con git pull y volver a instalar las dependencias si requirements.txt cambió.

El archivo de variables privadas .env del servidor debe configurarse fuera del control de versiones. Contiene DATABASE_URL, DJANGO_SECRET_KEY, DJANGO_DEBUG=False y DJANGO_ALLOWED_HOSTS. No se publica su contenido.



3\. Migraciones, roles y archivos estáticos

Con el entorno y las variables de producción correctamente cargados:

python manage.py migrate

python manage.py setup_roles

python manage.py collectstatic --noinput

python manage.py check

Crear un superusuario con python manage.py createsuperuser únicamente si todavía no existe.

4\. Gunicorn y Nginx

El servicio systemd dulcearte.service ejecuta Gunicorn con la aplicación dulcearte.wsgi:application y escucha en 127.0.0.1:8000. Nginx recibe el tráfico público, sirve archivos estáticos y multimedia y reenvía las solicitudes dinámicas a Gunicorn.



Comandos de comprobación:

sudo systemctl status dulcearte --no-pager

sudo systemctl status nginx --no-pager

sudo nginx -t

Para aplicar cambios de código o configuración del servicio, cuando corresponda:

sudo systemctl restart dulcearte

sudo systemctl reload nginx

5\. HTTPS y certificado

Se configuró Nginx para redirigir HTTP a HTTPS. El certificado de Let's Encrypt se emitió para 98.87.33.112 mediante validación webroot y perfil de corta duración. Se comprobó la conexión HTTPS y se ejecutó exitosamente una simulación de renovación con Certbot.



Comprobaciones realizadas:

curl -I https\://98.87.33.112

sudo certbot renew --dry-run

La respuesta 302 Found hacia /accounts/login/?next=/ es esperada cuando se solicita la página sin una sesión autenticada. La simulación de renovación finalizó correctamente.



Importante: la renovación real del certificado debe estar programada y Nginx debe recargar los certificados renovados. Revisar periódicamente el vencimiento, especialmente por tratarse de un certificado de corta duración y la Elastic IP asignada.

Validaciones y pruebas

En el entorno de desarrollo:

python manage.py check

python manage.py test

python manage.py makemigrations --check --dry-run

Antes de la defensa, repetir las pruebas que correspondan en el entorno de AWS y comprobar la disponibilidad pública del sitio, del panel Admin y de los endpoints autenticados. Los resultados deben mostrarse con evidencia real; no se asume que las pruebas automatizadas se hayan ejecutado en producción.

Guion de defensa práctica

1\. Abrir la URL pública HTTPS e iniciar sesión.

2\. Mostrar el tablero de pedidos y el panel Django Admin.

3\. Registrar un cliente, insumos y un pedido personalizado.

4\. Agregar materiales BOM y calcular la cotización.

5\. Enviar y aprobar la cotización; mostrar que no se puede producir sin aprobación.

6\. Demostrar el bloqueo por inventario insuficiente y registrar una entrada de bodega.

7\. Avanzar el pedido por las etapas de producción y comprobar el descuento de insumos y el historial.

8\. Planificar el despacho y registrar el comprobante de entrega.

9\. Mostrar las rutas de la API REST, los permisos por roles y las migraciones de PostgreSQL.

10\. Explicar la arquitectura 4+1 y el despliegue EC2 → Nginx → Gunicorn → Django → PostgreSQL.

Uso de inteligencia artificial

El archivo [\`prompts_ia.md\`]\(prompts_ia.md) registra las consultas y apoyos de herramientas de inteligencia artificial utilizados durante el desarrollo, la revisión de código y el despliegue, conforme a los requisitos de la evaluación.

Entrega

La entrega consiste en el enlace al repositorio GitHub, el código fuente completo, README.md, prompts_ia.md y la aplicación pública operativa en AWS EC2. La evaluación también contempla una defensa individual y una prueba escrita de selección múltiple.



No subir al repositorio: .env, contraseñas, claves SSH, secretos de Django, credenciales de AWS ni archivos privados de producción.