from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
import spotipy
from spotipy.oauth2 import SpotifyOAuth
import os
from dotenv import load_dotenv
from database import save_user_token
from pydantic import BaseModel
from chat_logic import generate_response_structure
from database import create_new_conversation, add_message_to_conversation, get_conversation_history, save_feedback, get_all_conversation_summaries, delete_conversation, delete_user_session, delete_all_conversations,add_summary_to_conversation, get_summary_context, update_conversation_title, save_user_profile, get_user_profile
from typing import Optional
from spotify_service import search_spotify_item, get_spotify_oauth_client, get_spotify_client
from spotipy.exceptions import SpotifyOauthError



load_dotenv()

app = FastAPI(title="Asistente Musical IA API")

class ChatRequest(BaseModel):
    message: str
    user_id: str
    conversation_id: Optional[str] = None

class newChatRequest(BaseModel):
    user_id: str

@app.post("/new_chat")
def new_chat_endpoint(request: newChatRequest):
    conv_id = create_new_conversation(request.user_id)
    return {"conversation_id": conv_id}

@app.post("/chat")
async def chat_endpoint(request: ChatRequest):
    current_conv_id = request.conversation_id
    is_new_conversation = False

    if not current_conv_id:
        current_conv_id = create_new_conversation(request.user_id)
    
    # Guardar mensaje del usuario 
    add_message_to_conversation(request.user_id, current_conv_id, 'user', request.message)
    #  Obtener contexto resumido
    summary_context = get_summary_context(request.user_id, current_conv_id)
    
    is_new_conversation = (summary_context.strip() == "")

    print(f"La conversación es nueva: {is_new_conversation}")

    #  Generar estructura con IA
    ai_data = await generate_response_structure(request.message, request.user_id, summary_context, is_new_conversation)
    
    if ai_data.get("conversation_title"):
        update_conversation_title(request.user_id, current_conv_id, ai_data["conversation_title"])

    final_response_text = ai_data['conversational_response']
    spotify_info = None
    #  Lógica de Spotify Link
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
            # Fallback natural 
            final_response_text += f"\n\n(Nota: No encontré el enlace directo en Spotify para '{ai_data['recommendation_query']}', pero vale la pena buscarlo en la web)."

    #  Guardar resumen en base de datos 
    add_summary_to_conversation(request.user_id, current_conv_id, ai_data['history_summary'])

    #  Guardar mensaje del bot completo 
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

# Configuración CORS para permitir peticiones desde React (Vite usa puerto 5173 por defecto)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", "http://127.0.0.1:8000", "https://recomendador-musical-front.vercel.app"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuración de Spotify Auth
sp_oauth = SpotifyOAuth(
    client_id=os.getenv("SPOTIFY_CLIENT_ID"),
    client_secret=os.getenv("SPOTIFY_CLIENT_SECRET"),
    redirect_uri=os.getenv("SPOTIFY_REDIRECT_URI"),
    scope="user-read-private user-read-email user-top-read user-read-recently-played" # Scopes necesarios para leer perfil y gustos
)

@app.get("/")
def read_root():
    return {"message": "API del Recomendador Musical activa"}

@app.get("/login")
def login():
    sp_oauth = get_spotify_oauth_client() 
    auth_url = sp_oauth.get_authorize_url()
    
    # Inyección de prompt=login
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

        # Obtenemos el objeto usuario completo de Spotify
        current_user = sp.current_user()
        user_id = current_user['id']

        # Extraemos los datos para el usuario
        profile_data = {
            "display_name": current_user.get('display_name'),
            "email": current_user.get('email'),
            "spotify_url": current_user.get('external_urls', {}).get('spotify')
        }

        # guardar todo
        save_user_profile(user_id, token_info, profile_data)

        return RedirectResponse(url=f"http://127.0.0.1:5173?uid={user_id}")

    except SpotifyOauthError as e:
        print(f"ERROR: Falló el canje: {e}")
        return RedirectResponse(url="http://127.0.0.1:5173")

@app.get("/user/{user_id}")
def get_user_info_endpoint(user_id: str):
    profile = get_user_profile(user_id)
    if profile:
        return profile
    return {"display_name": "Usuario", "id": user_id}


class FeedbackRequest(BaseModel):
    user_id: str
    rating: int
    pleasant_interaction: bool
    motivated_exploration: bool
    comments: str = ""

@app.post("/feedback")
def feedback_endpoint(request: FeedbackRequest):
    # Convertimos el modelo Pydantic a diccionario
    feedback_id = save_feedback(request.user_id, request.model_dump())
    return {"status": "success", "feedback_id": feedback_id}

# Endpoint para listar el historial (Consumido por el Sidebar)
@app.get("/conversations/{user_id}")
def get_conversations_endpoint(user_id: str):
    summaries = get_all_conversation_summaries(user_id)
    return {"summaries": summaries}

# Endpoint para cerrar sesión / desvincular cuenta (CU6)
@app.delete("/logout/{user_id}")
def logout_endpoint(user_id: str):
    delete_user_session(user_id)
    return {"status": "success", "message": "Sesión y datos de Spotify eliminados."}

# Endpoint para borrar un chat específico (CU5)
@app.delete("/conversations/{user_id}/{conversation_id}")
def delete_chat_endpoint(user_id: str, conversation_id: str):
    delete_conversation(user_id, conversation_id)
    return {"status": "success", "message": f"Conversación {conversation_id} eliminada."}

# Endpoint para borrar todo el historial de un usuario (Para el botón de Settings)
@app.delete("/conversations/{user_id}")
def delete_all_chats_endpoint(user_id: str):
    delete_all_conversations(user_id)
    return {"status": "success", "message": "Historial completo eliminado."}