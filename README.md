# PI Vision AI

Sistema web profesional para centros de monitoreo con análisis de video por IA, integración Dahua IVS y alertas inteligentes configurables.

## Arquitectura

```
┌─────────────┐     ┌──────────────┐     ┌─────────────────┐
│   Frontend  │────▶│   Backend    │────▶│   PostgreSQL    │
│  React/Nginx│     │   FastAPI    │     └─────────────────┘
└─────────────┘     └──────┬───────┘
                           │
              ┌────────────┼────────────┐
              ▼            ▼            ▼
        ┌──────────┐ ┌──────────┐ ┌──────────┐
        │  Redis   │ │ Worker   │ │ Worker   │
        │          │ │    AI    │ │ Ingest   │
        └──────────┘ └──────────┘ └──────────┘
```

### Servicios

| Servicio | Descripción |
|----------|-------------|
| `backend` | API REST + WebSocket |
| `frontend` | Panel web React + Tailwind |
| `postgres` | Base de datos |
| `redis` | Colas y cache |
| `worker-ai` | Procesamiento YOLO + reglas |
| `worker-ingest` | Dahua IVS + notificaciones |
| `worker-beat` | Tareas programadas |

## Requisitos

- Docker y Docker Compose
- Ubuntu Server (recomendado)
- NVIDIA GPU + CUDA (opcional, para aceleración IA)
- Coolify v4+ para despliegue

## Instalación en Coolify — Paso a paso

### 1. Preparar repositorio

Suba este proyecto a un repositorio Git (GitHub, GitLab, etc.).

### 2. Crear proyecto en Coolify

1. Ingrese a su panel Coolify
2. **Projects** → **New Project**
3. **Add Resource** → **Docker Compose** (no use Nixpacks)
4. Conecte su repositorio Git
5. Seleccione la rama principal
6. **Docker Compose location:** `docker-compose.yml` (raíz del repo)
7. **Base directory:** `/`

### 3. Configurar variables de entorno

En Coolify, vaya a **Environment Variables** y configure **antes del primer deploy**:

```env
POSTGRES_PASSWORD=una-contraseña-segura-larga
SECRET_KEY=generar-clave-aleatoria-32-caracteres-minimo
JWT_SECRET_KEY=otra-clave-aleatoria-32-caracteres
CORS_ORIGINS=https://su-dominio.com
VITE_API_URL=/api/v1
VITE_WS_URL=/ws
WEBHOOK_DEFAULT_URL=
MQTT_ENABLED=false
AI_DEVICE=cpu
```

**Importante:** Nunca suba `.env` al repositorio. Si falta `POSTGRES_PASSWORD`, el deploy fallará.

### 4. Configurar dominio (Reverse Proxy)

En Coolify, asigne un dominio al servicio **frontend** (no al backend):

- Dominio: `https://pivision.sudominio.com`
- Coolify generará certificado HTTPS automáticamente
- El nginx del frontend hace proxy a `/api/` y `/ws/` hacia el backend

### 5. Volúmenes persistentes

Coolify montará automáticamente el volumen `storage_data`. Contiene:

- `/data/storage/snapshots` — Capturas de eventos
- `/data/storage/clips` — Clips de evidencia
- `/data/storage/logs` — Logs del sistema

Verifique en Coolify que los volúmenes estén persistentes.

### 6. Desplegar

1. Click en **Deploy**
2. El build del **backend** puede tardar 10–20 min (PyTorch + YOLO). Si falla por memoria, aumente RAM del builder en Coolify.
3. La base de datos se inicializa sola al arrancar el backend (usuario `admin` / `admin123`)

### 7. Acceder al sistema

- **URL:** `https://pivision.sudominio.com`
- **Usuario:** `admin`
- **Contraseña:** `admin123`

Cambie la contraseña del administrador inmediatamente después del primer login.

### 8. GPU NVIDIA (opcional)

Para habilitar CUDA/TensorRT:

1. Instale NVIDIA Container Toolkit en el servidor
2. En `.env`: `AI_DEVICE=cuda:0`
3. Descomente la sección `deploy.resources` del servicio `worker-ai` en `docker-compose.yml`
4. Redespliegue

## Desarrollo local

```bash
# Copiar configuración
cp .env.example .env

# Levantar servicios
docker compose up -d --build

# Inicializar BD
docker exec -it pivision-backend python scripts/init_db.py

# Acceder
# Frontend: http://localhost
# API Docs: http://localhost:8000/docs
```

## MVP incluido

- [x] Docker Compose para Coolify
- [x] PostgreSQL + Redis
- [x] FastAPI con JWT
- [x] React + Tailwind (modo oscuro)
- [x] Alta de cámaras Dahua RTSP
- [x] Snapshot y test de conexión
- [x] Procesamiento IA (YOLOv8) en substream
- [x] Detección personas y vehículos
- [x] Reglas: cruce de línea e intrusión en zona
- [x] Horarios por regla (schedules)
- [x] Eventos en tiempo real (WebSocket)
- [x] Dashboard de eventos + modo operador
- [x] Guardado de snapshots
- [x] Webhook / MQTT
- [x] Panel básico de salud
- [x] Modelos PostgreSQL completos
- [x] Migraciones Alembic
- [x] Integración Dahua API (IVS polling)

## API

Documentación Swagger disponible en `/docs`.

### Endpoints principales

| Método | Ruta | Descripción |
|--------|------|-------------|
| POST | `/api/v1/auth/login` | Login JWT |
| GET | `/api/v1/cameras` | Listar cámaras |
| POST | `/api/v1/cameras` | Crear cámara |
| POST | `/api/v1/cameras/{id}/test` | Probar RTSP |
| POST | `/api/v1/cameras/{id}/snapshot` | Capturar snapshot |
| GET | `/api/v1/events` | Listar eventos |
| POST | `/api/v1/rules` | Crear regla |
| GET | `/api/v1/system/health` | Salud del sistema |
| WS | `/ws/events` | Eventos en tiempo real |

## Configuración de cámara Dahua

Al crear una cámara Dahua, las URLs RTSP se generan automáticamente:

```
Main:  rtsp://user:pass@IP:554/cam/realmonitor?channel=1&subtype=0
Sub:   rtsp://user:pass@IP:554/cam/realmonitor?channel=1&subtype=1
```

El substream se usa para análisis IA; el main stream para evidencia.

## Escalabilidad

- Workers IA independientes y escalables horizontalmente
- Preparado para TensorRT (`TENSORRT_ENABLED=true`)
- Modo degradado automático ante sobrecarga
- Soporta hasta 128 cámaras por instalación

## Seguridad

- Contraseñas de usuario con bcrypt
- Credenciales de cámaras no expuestas al frontend
- JWT con expiración configurable
- HTTPS vía Coolify reverse proxy
- Logs de auditoría

## Licencia

Proyecto privado — PI Vision AI © 2026
