# s.curriculums — Sistema RRHH con IA local

Sistema completo de automatización de RRHH con Ollama (LLaMA 3) 100% local.

## Stack
- **Backend:** Flask + SQLite
- **IA:** Ollama (LLaMA 3) — sin APIs externas
- **PDF:** PyMuPDF para extracción de texto
- **Auth:** Werkzeug (bcrypt hashing)

## Instalación

```bash
# 1. Clonar / descomprimir el proyecto
cd s_curriculums

# 2. Crear entorno virtual
python -m venv venv
source venv/bin/activate      # Linux/Mac
venv\Scripts\activate         # Windows

# 3. Instalar dependencias
pip install -r requirements.txt

# 4. Arrancar Ollama (en otra terminal)
ollama serve
ollama pull llama3             # si no lo tienes descargado

# 5. Ejecutar la app
python app.py
```

Abre http://localhost:5000

## Credenciales demo
- Email: `admin@empresa.com`
- Contraseña: `admin123`

## Funcionalidades

### Dashboard
- KPIs en tiempo real: candidatos, top picks, solicitudes pendientes
- Pipeline de selección visual
- Distribución de puntuaciones
- Tabla de candidatos recientes

### Currículos
- Listado con filtros por estado y puesto
- **Subir PDF** → extracción automática de texto con PyMuPDF → análisis con Ollama → puntuación IA → guardado en BD
- **Añadir manualmente** con formulario completo
- Ficha de detalle: contacto, habilidades, fase del proceso, notas, informe IA
- Marcar candidatos como favoritos (★)
- Cambiar fase del proceso (6 etapas)

### Solicitudes
- Gestión de vacaciones, permisos médicos, teletrabajo, formación…
- Aprobar/rechazar con un clic
- Recomendación IA de Ollama por cada solicitud
- Historial de acciones

### Asistente IA
- Chat con LLaMA 3 vía Ollama
- Especializado en RRHH español (ET, convenios, RGPD)
- Redacta políticas, plantillas, descripciones de puesto, onboarding…
- Contexto de conversación persistente en la sesión

### Auth
- Registro con validación y bcrypt
- Login con sesión Flask
- Usuario demo precargado

## Estructura
```
s_curriculums/
├── app.py                  # Flask app + rutas + API
├── database.db             # SQLite (se crea al arrancar)
├── requirements.txt
├── uploads/                # PDFs subidos
├── static/
│   ├── css/main.css
│   └── js/main.js
└── templates/
    ├── base.html
    ├── login.html
    ├── register.html
    ├── dashboard.html
    ├── curriculos.html
    ├── cv_detail.html
    ├── add_cv.html
    ├── solicitudes.html
    ├── add_solicitud.html
    └── asistente.html
```
