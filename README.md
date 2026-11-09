# Dulce Arte — pedidos, producción y despacho

Aplicación web para la pastelería artesanal Dulce Arte. Administra clientes, cotizaciones personalizadas, lista de materiales (BOM), existencias, etapas de cocina y comprobantes de entrega. Está construida con Django, Django REST Framework y PostgreSQL. SQLite queda disponible para comenzar el desarrollo local sin instalar PostgreSQL.

## Funcionalidades

- Registro y edición de clientes y pedidos personalizados, con fecha/hora de entrega, diseño, dirección y notas.
- Cálculo de cotización a partir del costo de los insumos BOM más la mano de obra; acciones para enviar, aprobar o rechazar.
- Tablero Kanban: Recibido → En Preparación → Horneado/Decorado → Control de Calidad → Listo.
- Al avanzar a producción, valida y descuenta el inventario en una transacción; si no hay stock suficiente, no cambia ni el pedido ni las existencias. Cancelar un pedido devuelve una sola vez el stock reservado.
- Movimientos de bodega auditables: cada entrada, salida, consumo de BOM y devolución por cancelación registra responsable y saldo posterior; la existencia no se edita directamente desde formularios, API o Admin.
- Registro de los cambios de estado para trazabilidad.
- CRUD de clientes, insumos, pedidos y despachos, alertas visuales de stock bajo y evidencia de recepción mediante firma dibujada o comprobante fotográfico.
- Roles de aplicación: **Ventas**, **Cocina**, **Bodega**, **Despacho** y **Administradores**. Las lecturas requieren inicio de sesión; las escrituras exigen el rol correspondiente. La cuenta staff/superusuario administra el panel Django.
- Admin de Django personalizado y API REST protegida por sesión y permisos de rol.

## Requisitos

- Python 3.11 o superior (probado en Python 3.13).
- Para desarrollo local: SQLite incluido con Python.
- Para producción: PostgreSQL 14 o superior y una instancia Linux (para esta evaluación, AWS EC2).

## Ejecución local en Windows PowerShell

Desde la carpeta del proyecto. Si `py` no existe en tu Windows, usa `python` como se muestra:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
$env:DJANGO_SECRET_KEY = "clave-local-de-desarrollo"
$env:DJANGO_DEBUG = "True"
$env:DJANGO_ALLOWED_HOSTS = "127.0.0.1,localhost"
python manage.py migrate
python manage.py setup_roles
python manage.py createsuperuser
python manage.py runserver
```

Abre `http://127.0.0.1:8000/` e inicia sesión con la cuenta creada. Admin: `http://127.0.0.1:8000/admin/`. La aplicación exige autenticación; crea usuarios adicionales desde **Admin → Usuarios**. Para salir se usa el botón del menú.

En PowerShell, si la política de ejecución bloquea el entorno virtual, ejecuta `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` y vuelve a activar `.\.venv\Scripts\Activate.ps1`. En cada consola configura las variables `$env:`; Django no lee `.env` automáticamente. No guardes claves reales en el repositorio.

Después de crear el superusuario, entra a **Admin → Usuarios**, selecciona las cuentas y asígnales sus grupos en **Grupos disponibles**. El comando `setup_roles` crea los grupos, pero no asigna usuarios automáticamente.

## Usar PostgreSQL localmente

1. Crea una base `dulcearte` y un usuario con permisos sobre ella en PostgreSQL.
2. En la misma consola, configura la URL de conexión:

```powershell
$env:DATABASE_URL = "postgresql://dulcearte_user:tu_clave@127.0.0.1:5432/dulcearte"
python manage.py migrate
```

La app usa `DATABASE_URL` cuando está definida; si no, usa `db.sqlite3` para facilitar el desarrollo. **La base local comprobada en esta auditoría es SQLite. No se verificó conexión real a PostgreSQL porque no se configuró `DATABASE_URL`.** Para cumplir la evaluación, configura PostgreSQL y comprueba la conexión y las migraciones antes de presentar. En producción define `DATABASE_URL` como variable privada del servicio y nunca la escribas en el código ni en Git.

## API REST

Las rutas están bajo `/api/` y requieren una sesión autenticada. Inicia sesión en el navegador; DRF ofrece su interfaz navegable:

- `/api/clientes/`
- `/api/insumos/`
- `/api/pedidos/` — `POST /api/pedidos/{id}/quote/` acepta `quote_status` (`SENT`, `APPROVED`, `REJECTED`); `POST /api/pedidos/{id}/advance/` recibe `status` con el siguiente estado válido. `status` y `quote_status` no se pueden cambiar mediante los endpoints CRUD genéricos.
- `/api/materiales-pedido/` — CRUD de líneas BOM antes de enviar o aprobar la cotización y antes de iniciar la producción.
- `/api/despachos/`
- `/api/movimientos-inventario/` — `GET` para consultar y `POST` para registrar entradas/salidas con el rol Bodega. Los movimientos quedan como bitácora: no se editan ni eliminan.

Las operaciones de cambio de etapa aplican las mismas reglas de negocio que el tablero web. Enviar una cotización: `{"quote_status":"SENT"}`; aprobar/rechazar: `{"quote_status":"APPROVED"}` o `{"quote_status":"REJECTED"}`; restablecer una cotización rechazada para revisarla: `{"quote_status":"DRAFT"}`. El stock en `/api/insumos/` es de solo lectura; usa `/api/movimientos-inventario/`. Asigna grupos de rol según corresponda. Django Admin se encuentra en `/admin/`.

## Arquitectura 4+1

- **Vista lógica:** `Customer`, `Order`, `OrderIngredient`, `Ingredient`, `InventoryMovement`, `OrderStatusHistory` y `Dispatch` representan clientes, pedidos, BOM, existencias, bitácora de bodega, trazabilidad y entrega. Las reglas de costo, stock y estados se ejecutan en modelos/servicios.
- **Vista de desarrollo:** el proyecto Django `dulcearte` configura seguridad, sesiones, almacenamiento y URLs; la aplicación `pedidos` mantiene modelos, formularios, vistas web, serializadores, API, Admin y pruebas.
- **Vista de procesos:** el navegador/API autentica por sesión; ventas registra pedido y BOM, la cotización debe aprobarse, cocina avanza por estados consecutivos y el servicio transaccional reserva insumos; despacho registra ruta y comprobante de entrega.
- **Vista física:** navegador → Nginx (estáticos y proxy) → Gunicorn → Django → PostgreSQL local en EC2. Las imágenes de comprobantes quedan en `media/`; las claves están fuera del código, en el entorno del servicio.
- **Escenarios (+1):** registrar/cotizar pedido; aprobar e iniciar producción con stock válido; bloquear inicio por falta de stock; cancelar y reponer stock; avanzar calidad a listo; planificar ruta y confirmar entrega.

## Despliegue en AWS EC2 (Ubuntu 24.04)

El despliegue requiere que el estudiante cree y administre la instancia en AWS Academy; este repositorio no contiene credenciales ni una IP pública. Usa una instancia EC2 Ubuntu, reserva/identifica su IP pública y abre en el Security Group SSH (22, solo tu IP), HTTP (80) y, si vas a configurar TLS, HTTPS (443). No expongas PostgreSQL (5432) a Internet: déjalo accesible solo localmente en la instancia.

### 1. Instalar servicios

Conéctate por SSH a la instancia:

```bash
sudo apt update
sudo apt install -y python3-venv python3-dev build-essential libpq-dev postgresql nginx
sudo -u postgres createuser --pwprompt dulcearte_user
sudo -u postgres createdb -O dulcearte_user dulcearte
```

### 2. Copiar y configurar el proyecto

Clona el repositorio en `/opt/dulcearte` y luego:

```bash
cd /opt/dulcearte
sudo python3 -m venv .venv
sudo .venv/bin/pip install -r requirements.txt
sudo nano /etc/dulcearte.env
```

Contenido del archivo de entorno (reemplaza todos los ejemplos; usa una clave larga generada para Django):

```text
DJANGO_SECRET_KEY=PEGA_AQUI_UNA_CLAVE_ALEATORIA_LARGA
DJANGO_DEBUG=False
DJANGO_ALLOWED_HOSTS=IP_PUBLICA_EC2,tu-dominio-si-tienes
DATABASE_URL=postgresql://dulcearte_user:CONTRASENA@127.0.0.1:5432/dulcearte
DJANGO_SECURE_COOKIES=False
```

Protege ese archivo: `sudo chown root:www-data /etc/dulcearte.env && sudo chmod 640 /etc/dulcearte.env`. Cambia `CONTRASENA` por la contraseña asignada al usuario PostgreSQL; codifica caracteres especiales de la URL. No compartas el archivo ni lo subas al repositorio.

```bash
cd /opt/dulcearte
sudo .venv/bin/python manage.py migrate
sudo .venv/bin/python manage.py setup_roles
sudo .venv/bin/python manage.py createsuperuser
sudo .venv/bin/python manage.py collectstatic --noinput
```

### 3. Configurar Gunicorn y Nginx

Crea `/etc/systemd/system/dulcearte.service`:

```ini
[Unit]
Description=Dulce Arte Django application
After=network.target postgresql.service

[Service]
User=www-data
Group=www-data
WorkingDirectory=/opt/dulcearte
EnvironmentFile=/etc/dulcearte.env
ExecStart=/opt/dulcearte/.venv/bin/gunicorn dulcearte.wsgi:application --bind 127.0.0.1:8000 --workers 3
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

Da al servicio acceso al código y a la carpeta `media` (por ejemplo, asignando `/opt/dulcearte` al usuario/grupo `www-data`; limita permisos de escritura a `media`). Configura Nginx con un bloque `server` para el puerto 80:

```nginx
server {
    listen 80;
    server_name IP_PUBLICA_EC2;
    client_max_body_size 10M;

    location /static/ {
        alias /opt/dulcearte/staticfiles/;
    }
    location /media/ {
        alias /opt/dulcearte/media/;
    }
    location / {
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_pass http://127.0.0.1:8000;
    }
}
```

Guárdalo como `/etc/nginx/sites-available/dulcearte` y habilítalo:

```bash
sudo ln -s /etc/nginx/sites-available/dulcearte /etc/nginx/sites-enabled/dulcearte
sudo chown -R root:www-data /opt/dulcearte
sudo chmod -R g+rX /opt/dulcearte
sudo chown -R www-data:www-data /opt/dulcearte/media
sudo chmod -R u+rwX,g+rwX /opt/dulcearte/media
```

Valida la configuración y activa los servicios:

```bash
sudo nginx -t
sudo systemctl daemon-reload
sudo systemctl enable --now dulcearte
sudo systemctl reload nginx
sudo systemctl status dulcearte --no-pager
```

Comprueba `http://IP_PUBLICA_EC2/`, el inicio de sesión y `/admin/`. Si configuras HTTPS con un dominio y certificado, agrega el dominio a `DJANGO_ALLOWED_HOSTS`, cambia `DJANGO_SECURE_COOKIES=True` y reinicia el servicio. Guarda la IP real y los pasos ejecutados en este README antes de entregar; no inventes una IP mientras no despliegues.

El ejemplo de Nginx anterior sirve HTTP para facilitar la primera comprobación y **no cifra credenciales ni sesiones en tránsito**. Antes de usar datos reales o presentar un servicio público con seguridad completa, configura TLS en Nginx (por ejemplo, con un dominio y un certificado), redirige el puerto 80 a HTTPS y define también `DJANGO_SECURE_SSL_REDIRECT=True` y `DJANGO_SECURE_COOKIES=True` en `/etc/dulcearte.env`. El código activa HSTS solo cuando está habilitada la redirección a HTTPS.

## Preparación de la defensa práctica

1. Inicia sesión y muestra resumen y tablero Kanban.
2. Crea cliente, insumo(s) y un pedido con BOM; revisa el cálculo de la cotización.
3. Envía y aprueba la cotización; demuestra que el pedido no puede producirse antes de aprobarse.
4. Intenta avanzar con stock insuficiente y verifica que pedido e inventario permanecen iguales.
5. Repón stock con una **entrada de bodega**, avanza a **En Preparación** y muestra el descuento BOM en el historial; continúa las etapas hasta **Listo** y el historial de trazabilidad.
6. Planifica una ruta para el pedido listo y registra la confirmación (firma textual/comprobante o imagen).
7. Muestra filtros/búsqueda en Admin y la API autenticada.
8. Explica las vistas 4+1: lógica (modelos/reglas), desarrollo (apps Django), proceso (solicitud HTTP y transacción), física (EC2, Nginx, Gunicorn y PostgreSQL), escenarios (ciclo de pedido y entrega). Muestra además los grupos de rol y los movimientos de inventario asociados a la fabricación.

La prueba escrita indicada en la pauta es independiente del código: son 20 preguntas de selección múltiple y representa el 40% de la evaluación.

## Validación automatizada

```powershell
python manage.py check
python manage.py test
python manage.py makemigrations --check --dry-run
```

Las pruebas de esta entrega se ejecutaron con la base SQLite de desarrollo, no contra PostgreSQL ni en AWS.
