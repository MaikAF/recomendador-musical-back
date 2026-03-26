from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
import spotipy
from spotipy.oauth2 import SpotifyOAuth
import os
from dotenv import load_dotenv
from pydantic import BaseModel
from typing import Optional
from spotipy.exceptions import SpotifyOauthError

# Importaciones locales actualizadas
from chat_logic import generate_response_structure
from services.spotify_service import search_spotify_item, get_spotify_oauth_client, get_spotify_client

# NUEVO: Importamos las funciones actualizadas de database.py
from database import (
    create_new_conversation, add_message_to_conversation, get_conversation_history, 
    save_feedback, get_all_conversation_summaries, delete_conversation, 
    delete_user_session, delete_all_conversations, add_summary_to_conversation, 
    get_summary_context, update_conversation_title, save_or_update_user, get_user_profile
)

load_dotenv()

app = FastAPI(title="Asistente Musical IA API")

FRONT_URL = os.getenv("FRONT_URL")
print(f"INFO: Configurado para redirigir al Frontend en: {FRONT_URL}")

origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:8000",
    FRONT_URL 
]

# --- MODELOS PYDANTIC ---
class ChatRequest(BaseModel):
    message: str
    user_id: str
    conversation_id: Optional[str] = None

class newChatRequest(BaseModel):
    user_id: str

# NUEVO: Modelo para el login de Last.FM
class LastFMLoginRequest(BaseModel):
    lastfm_username: str

class FeedbackRequest(BaseModel):
    user_id: str
    rating: int
    pleasant_interaction: bool
    motivated_exploration: bool
    comments: str = ""

# --- CONFIGURACIÓN CORS ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins, 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Endpoint raíz
@app.get("/")
def read_root():
    return {"message": "API del Recomendador Musical activa (Multiplataforma)"}

# ==========================================
# RUTAS DE CHAT E IA
# ==========================================

@app.post("/new_chat")
def new_chat_endpoint(request: newChatRequest):
    conv_id = create_new_conversation(request.user_id)
    return {"conversation_id": conv_id}

@app.post("/chat")
async def chat_endpoint(request: ChatRequest):
    current_conv_id = request.conversation_id

    if not current_conv_id:
        current_conv_id = create_new_conversation(request.user_id)
    
    # Guardar mensaje del usuario 
    add_message_to_conversation(request.user_id, current_conv_id, 'user', request.message)
    
    # Obtener contexto resumido
    summary_context = get_summary_context(request.user_id, current_conv_id)
    is_new_conversation = (summary_context.strip() == "")

    # NUEVO: Buscar plataforma del usuario en la base de datos
    user_profile = get_user_profile(request.user_id)
    platform = "none"
    platform_user_id = "anonymous"

    if user_profile:
        platform = user_profile.get("platform", "none")
        # Es vital usar platform_user_id (el username real de last.fm o ID de spotify)
        platform_user_id = user_profile.get("platform_user_id", request.user_id)

    print(f"INFO: Procesando chat para usuario '{platform_user_id}' en plataforma '{platform}'.")

    # Generar estructura con IA (Pasamos la plataforma y el ID real)
    ai_data = await generate_response_structure(
        user_message=request.message, 
        user_id=platform_user_id, 
        platform=platform, # <--- Inyectamos la plataforma aquí
        summary_history=summary_context, 
        is_first_message=is_new_conversation
    )
    
    if ai_data.get("conversation_title"):
        update_conversation_title(request.user_id, current_conv_id, ai_data["conversation_title"])

    final_response_text = ai_data['conversational_response']
    spotify_info = None
    
    # Lógica de Spotify Link
    if ai_data['recommendation_type'] != 'info' and ai_data['recommendation_query']:
        search_result = search_spotify_item(ai_data['recommendation_query'], ai_data['recommendation_type'])
        
        if search_result:
            spotify_info = {
                "url": search_result['url'],
                "type": ai_data['recommendation_type'],
                "name": ai_data['recommendation_query'],
                "image": search_result.get('image')
            }
        else:
            final_response_text += f"\n\n(Nota: No encontré el enlace directo en Spotify para '{ai_data['recommendation_query']}', pero vale la pena buscarlo en la web)."

    # Guardar resumen y respuesta
    add_summary_to_conversation(request.user_id, current_conv_id, ai_data['history_summary'])
    add_message_to_conversation(request.user_id, current_conv_id, 'bot', final_response_text)

    return {
        "response": final_response_text,
        "conversation_id": current_conv_id,
        "spotify_data": spotify_info
    }

@app.get("/history/{user_id}/{conversation_id}")
def history_endpoint(user_id: str, conversation_id: str):
    messages = get_conversation_history(user_id, conversation_id)
    return {"messages": messages}

@app.get("/conversations/{user_id}")
def get_conversations_endpoint(user_id: str):
    summaries = get_all_conversation_summaries(user_id)
    return {"summaries": summaries}


# ==========================================
# RUTAS DE AUTENTICACIÓN (MULTI-PLATAFORMA)
# ==========================================

# 1. SPOTIFY
@app.get("/login")
def login():
    sp_oauth = get_spotify_oauth_client() 
    auth_url = sp_oauth.get_authorize_url()
    
    if "prompt" not in auth_url:
        separator = "&" if "?" in auth_url else "?"
        auth_url += f"{separator}prompt=login"
        
    return {"url": auth_url}

@app.get("/callback")
def callback(code: str):
    sp_oauth = get_spotify_oauth_client()

    try:
        token_info = sp_oauth.get_access_token(code)
        sp = get_spotify_client(token_info['access_token'])

        current_user = sp.current_user()
        user_id = current_user['id']
        display_name = current_user.get('display_name')

        # NUEVO: Guardar con la arquitectura unificada
        save_or_update_user(
            user_id=user_id,
            platform="spotify",
            platform_user_id=user_id,
            display_name=display_name,
            auth_data=token_info
        )
        
        return RedirectResponse(url=f"{FRONT_URL}?uid={user_id}")

    except SpotifyOauthError as e:
        print(f"ERROR: Falló el canje: {e}")
        return RedirectResponse(url=f"{FRONT_URL}")

# 2. LAST.FM (NUEVO)
@app.post("/login/lastfm")
def login_lastfm(request: LastFMLoginRequest):
    """
    Endpoint para registrar/iniciar sesión con un usuario de Last.FM.
    Retorna el ID interno generado para que el frontend lo guarde en LocalStorage.
    """
    username = request.lastfm_username.strip()
    
    # Creamos un ID interno único basado en el prefijo para evitar choques con IDs de Spotify
    internal_user_id = f"lastfm_{username.lower()}"

    save_or_update_user(
        user_id=internal_user_id,
        platform="lastfm",
        platform_user_id=username,
        display_name=username, # En Last.FM el display name suele ser el mismo username
        auth_data=None # Last.FM no requiere tokens
    )
    
    # Retornamos el ID interno. El frontend debe redirigir internamente y guardar esto.
    return {
        "status": "success", 
        "user_id": internal_user_id, 
        "display_name": username
    }

# ==========================================
# RUTAS DE USUARIO Y CONFIGURACIÓN
# ==========================================

@app.get("/user/{user_id}")
def get_user_info_endpoint(user_id: str):
    profile = get_user_profile(user_id)
    if profile:
        return profile
    return {"display_name": "Usuario", "id": user_id}

@app.post("/feedback")
def feedback_endpoint(request: FeedbackRequest):
    feedback_id = save_feedback(request.user_id, request.model_dump())
    return {"status": "success", "feedback_id": feedback_id}

@app.delete("/logout/{user_id}")
def logout_endpoint(user_id: str):
    delete_user_session(user_id)
    return {"status": "success", "message": "Sesión y datos de plataforma eliminados."}

@app.delete("/conversations/{user_id}/{conversation_id}")
def delete_chat_endpoint(user_id: str, conversation_id: str):
    delete_conversation(user_id, conversation_id)
    return {"status": "success", "message": f"Conversación {conversation_id} eliminada."}

@app.delete("/conversations/{user_id}")
def delete_all_chats_endpoint(user_id: str):
    delete_all_conversations(user_id)
    return {"status": "success", "message": "Historial completo eliminado."}