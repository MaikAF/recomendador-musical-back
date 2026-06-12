# Recomendador Musical con IA - Backend

Backend en FastAPI para el Recomendador Musical impulsado por IA. Utiliza el LLM Gemini para generar recomendaciones personalizadas y dinámicas a partir del historial musical del usuario recopilado de plataformas como Spotify, Last.fm y YouTube Music.

## 🚀 Funcionalidades

El backend ofrece las siguientes características principales:

1. **Chat Asistente con IA (Gemini)**:
   - Integración con el modelo `gemini-2.5-flash` a través de LangChain (`langchain_google_genai`).
   - Genera respuestas conversacionales y dinámicas basadas en los gustos e intereses del usuario.
   - Retorna respuestas estructuradas en formato JSON que separan la introducción/respuesta directa (`intro`) del contexto/detalles adicionales (`details`).
   - Evita la repetición de canciones o artistas que ya han sido recomendados en la misma conversación (`already_recommended`).
2. **Contexto Musical Multiplataforma**:
   - **Spotify**: Sincronización mediante OAuth para obtener los artistas top y las canciones escuchadas recientemente del usuario para personalizar las respuestas del LLM.
   - **Last.fm**: Obtención de artistas top y reproducciones recientes utilizando únicamente el nombre de usuario (perfil público, sin necesidad de contraseña/OAuth).
   - **YouTube Music**: Conexión con Google OAuth para leer listas de reproducción e historial de videos de música que le gustan al usuario (`liked_songs`).
3. **Tarjeta de Recomendaciones y Previsualizaciones**:
   - Búsqueda automática en la API de Spotify para obtener enlaces directos e imágenes de portada de los artistas, álbumes, canciones o géneros recomendados.
   - Integración con la API de iTunes para obtener fragmentos de audio (`preview_url` de 30 segundos en formato `.m4a`) y portadas de canciones recomendadas, permitiendo escuchar un fragmento directamente en el reproductor integrado de la aplicación.
4. **Gestión de Sesiones e Historial (Firebase Firestore)**:
   - Base de datos NoSQL Firestore para registrar usuarios, tokens de acceso y conversaciones.
   - Límite de control: máximo 3 chats por usuario y hasta 10 mensajes por conversación.
   - Persistencia de resúmenes de chat (`summary_history`) para que el LLM mantenga memoria contextual del flujo de la conversación actual.
   - Eliminación segura de tokens en el cierre de sesión, manteniendo intacto el historial de conversaciones del usuario si este lo desea.
5. **Retroalimentación Anónima (Feedback)**:
   - Endpoint para registrar la valoración y experiencia de interacción del usuario.
   - Anonimización de los IDs de usuario en la base de datos de retroalimentación mediante un hashing criptográfico con sal (`FEEDBACK_SECRET_SALT`).

---

## 🔑 Variables de Entorno y API Keys (.env)

Para ejecutar este proyecto, debes crear un archivo `.env` en la raíz del backend con los siguientes parámetros:

```env
# URL del Frontend (CORS y redirecciones)
FRONT_URL=http://localhost:5173

# Google Gemini API (LangChain)
GOOGLE_API_KEY=tu_google_api_key_aqui

# Spotify API (Registra tu app en developer.spotify.com)
SPOTIFY_CLIENT_ID=tu_spotify_client_id_aqui
SPOTIFY_CLIENT_SECRET=tu_spotify_client_secret_aqui
SPOTIFY_REDIRECT_URI=http://localhost:8000/callback

# Google OAuth / YouTube Music API (Registra credenciales en Google Cloud Console)
GOOGLE_CLIENT_ID=tu_google_client_id_aqui
GOOGLE_CLIENT_SECRET=tu_google_client_secret_aqui
YTMUSIC_REDIRECT_URI=http://localhost:8000/callback/ytmusic

# Last.fm API (Registra tu cuenta de desarrollador en last.fm/api)
LASTFM_API_KEY=tu_lastfm_api_key_aqui

# Seguridad & Base de Datos
FEEDBACK_SECRET_SALT=una_cadena_secreta_para_hashear_los_ids_de_retroalimentacion
# Opcional (si usas variable de entorno para Firebase en producción, de lo contrario se busca el archivo serviceAccountKey.json):
# FIREBASE_SERVICE_ACCOUNT_JSON={"type": "service_account", ...}
```

### Configuración de Firebase Firestore
El backend utiliza Firebase Admin SDK para interactuar con Firestore.
* **Desarrollo local**: Descarga el archivo JSON de credenciales de tu cuenta de servicio de Firebase, renombralo a `serviceAccountKey.json` y colócalo en la raíz del proyecto.
* **Producción**: Define la variable de entorno `FIREBASE_SERVICE_ACCOUNT_JSON` con el contenido completo del archivo JSON en formato de texto plano stringificado.

---

## 🛠️ Instalación y Configuración

Sigue estos pasos para levantar el servidor de desarrollo localmente:

### 1. Clonar el repositorio y acceder a la carpeta
```bash
cd recomendador-musical-back
```

### 2. Crear y activar un entorno virtual
* **En Windows (PowerShell):**
  ```powershell
  python -m venv venv
  .\venv\Scripts\Activate.ps1
  ```
* **En macOS o Linux:**
  ```bash
  python -m venv venv
  source venv/bin/activate
  ```

### 3. Instalar las dependencias
```bash
pip install -r requirements.txt
```

### 4. Configurar las credenciales de Firebase y Variables de Entorno
* Coloca tu archivo `serviceAccountKey.json` en la raíz del backend.
* Crea y configura el archivo `.env` según la sección de variables de entorno.

### 5. Iniciar el servidor local
El backend utiliza FastAPI y Uvicorn. Ejecuta el servidor con el siguiente comando:
```bash
uvicorn main:app --reload
```
Por defecto, el servidor se iniciará en `http://localhost:8000`. Puedes probar los endpoints y ver la documentación interactiva accediendo a:
* **Swagger UI:** `http://localhost:8000/docs`
* **Redoc:** `http://localhost:8000/redoc`

---

## 🔗 Resumen de Endpoints Principales

### Chats y Mensajes
* `POST /new_chat`: Crea una nueva conversación en Firestore.
* `POST /chat`: Envía un mensaje a la IA y obtiene la recomendación estructurada (con enlace de Spotify y preview de audio de iTunes si aplica).
* `GET /history/{user_id}/{conversation_id}`: Recupera el historial completo de mensajes de un chat específico.
* `GET /conversations/{user_id}`: Lista todas las conversaciones y resúmenes creados por un usuario.
* `DELETE /conversations/{user_id}/{conversation_id}`: Elimina un chat específico.
* `DELETE /conversations/{user_id}`: Elimina todo el historial del usuario de la base de datos.

### Autenticación y Cuentas
* `GET /login`: Inicia el flujo de autenticación OAuth de Spotify.
* `GET /callback`: Maneja la redirección y almacenamiento de tokens de Spotify.
* `POST /login/lastfm`: Vincula el perfil público de Last.fm usando únicamente el nombre de usuario.
* `GET /login/ytmusic`: Inicia el flujo de autenticación de Google (YouTube Music).
* `GET /callback/ytmusic`: Maneja la redirección y almacenamiento de tokens de Google.
* `GET /user/{user_id}`: Obtiene información del perfil del usuario (nombre y plataforma vinculada).
* `DELETE /logout/{user_id}`: Cierra la sesión activa borrando los tokens asociados.

### Calidad y Retroalimentación
* `POST /feedback`: Guarda una valoración de la conversación, anonimizando el ID de usuario mediante un hash seguro.
