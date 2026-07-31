# ALJ - Motor Narrativo de Librojuegos para Telegram & CLI

Sistema desacoplado e inteligente para transformar librojuegos en formato **EPUB** en experiencias narrativas interactivas por voz y botones mediante **Telegram**, **Piper / gTTS** y **OpenAI Whisper**.

---

## 🌟 Características Principales

1. **Importador EPUB $\rightarrow$ IR JSON + Assets + Audios**:
   - Transforma cualquier EPUB en una **Representación Intermedia (IR)** neutra basada en nodos (`book.json`).
   - Extrae e independiza imágenes y texto.
   - Pre-genera los audios de lectura con **Piper TTS** (con fallback automático a **gTTS** si Piper no está disponible) para garantizar latencia cero durante la partida.

2. **Motor Narrativo Generico (Node-based Engine)**:
   - Independiente del formato original del libro.
   - Persistencia completa del estado de cada jugador en **SQLite** (`data/game.db`).
   - Guardado automático de partidas e historial de pasos.
   - Arquitectura extensible con soporte para **Plugins** (inventarios, dados, variables, mecánicas RPG).

3. **Reconocimiento de Voz e Intención Híbrido (Whisper + Voice Parser)**:
   - Transcribe notas de voz enviadas por Telegram utilizando **OpenAI Whisper**.
   - **Parser Multicapa**:
     - *Capa 1*: Reconocimiento directo de números y palabras numéricas en español ("la 15", "página 17", "opción dos").
     - *Capa 2*: Coincidencia difusa de texto (Fuzzy matching) para frases naturales ("quiero investigar el agujero", "atacar trasgos").
     - *Capa 3*: Clasificador de intenciones semántico (vía LLM local como Qwen / Ollama si está configurado).

4. **Interfaz Multimodal en Telegram**:
   - Texto enriquecido con imágenes originales del libro.
   - Audios enviados como mensajes de voz / audio.
   - Botones **Inline Keyboard** para selección rápida de opciones.

---

## 📂 Estructura del Proyecto

```
/home/marti/Documentos/Personal/ALJ/
├── Libros/                          # Carpeta donde se depositan los EPUBs
│   └── [D&D Aventura sin fin] ... .epub
├── data/                            # Datos generados
│   ├── books/                       # Libros procesados (JSON, imágenes, audios)
│   │   └── d_d_aventura_sin_fin.../
│   │       ├── book.json
│   │       ├── images/
│   │       └── audios/
│   └── game.db                      # Base de datos SQLite
├── src/
│   ├── importer.py                  # Extractor de EPUB a JSON + Assets
│   ├── engine.py                    # Motor narrativo de nodos y partidas
│   ├── db.py                        # Gestor de base de datos SQLite
│   ├── tts.py                       # Gestor TTS (Piper / gTTS)
│   ├── stt.py                       # Transcriptor Whisper
│   ├── voice_parser.py              # Clasificador híbrido de intenciones
│   ├── bot.py                       # Bot de Telegram
│   └── plugins/                     # Plugins de mecánicas (inventario, dados)
├── config.py                        # Configuración general
├── main.py                          # CLI y punto de entrada
├── requirements.txt                 # Dependencias
└── README.md
```

---

## 🛠️ Instalación y Uso

### 1. Entorno Virtual e Instalación de Dependencias

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Importar Libros

Coloca tus archivos `.epub` en la carpeta `Libros/` y ejecuta:

```bash
python3 main.py import
```

*Si deseas omitir la pre-generación de audios:*
```bash
python3 main.py import --no-audios
```

### 3. Jugar en Consola (Modo CLI)

Puedes probar cualquier libro importado directamente desde la terminal:

```bash
python3 main.py cli
```

---

## ⚙️ Configuración (.env & Variables de Entorno)

Crea un archivo `.env` en la raíz del proyecto basándote en `.env.example`:

```env
# Credenciales del usuario Administrador inicial (para la primera instalación)
ADMIN_USERNAME=admin
ADMIN_PASSWORD=admin123

# Dominios / IPs autorizadas para CORS (separados por comas, o '*' para desarrollo local)
ALLOWED_ORIGINS=https://pathtale.martivich.es

# Duración de validez de las sesiones de usuario en días (por defecto: 7 días)
SESSION_EXPIRE_DAYS=7

# Configuración de Piper TTS
PIPER_BIN=piper
PIPER_MODEL_ES=/app/models/piper/es_ES-davefx-medium.onnx
PIPER_MODEL_EN=/app/models/piper/en_US-lessac-medium.onnx
```
- **LLM Local (Ollama)**:
  - `LLM_API_URL`: `http://localhost:11434/api/generate` (Predeterminado).
  - `LLM_MODEL_NAME`: `qwen2.5:3b` o similar.
