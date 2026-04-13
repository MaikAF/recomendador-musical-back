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
import urllib.parse
import requests
from services.itunes_service import search_itunes_preview
import re

from chat_logic import generate_response_structure
from services.spotify_service import search_spotify_item, get_spotify_oauth_client, get_spotify_client
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

class ChatRequest(BaseModel):
    message: str
    user_id: str
    conversation_id: Optional[str] = None

class newChatRequest(BaseModel):
    user_id: str

class LastFMLoginRequest(BaseModel):
    lastfm_username: str

class FeedbackRequest(BaseModel):
    user_id: str
    rating: int
    pleasant_interaction: bool
    motivated_exploration: bool
    comments: str = ""

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins, 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/new_chat")
def new_chat_endpoint(request: newChatRequest):
    conv_id = create_new_conversation(request.user_id)
    return {"conversation_id": conv_id}


@app.post("/chat")
async def chat_endpoint(request: ChatRequest):
    
    current_conv_id = request.conversation_id

    if not current_conv_id:
        current_conv_id = create_new_conversation(request.user_id)
    
    add_message_to_conversation(request.user_id, current_conv_id, 'user', request.message)
    
    summary_context = get_summary_context(request.user_id, current_conv_id)
    is_new_conversation = (summary_context.strip() == "")

    user_profile = get_user_profile(request.user_id)
    platform = "none"
    platform_user_id = "anonymous"

    if user_profile:
        platform = user_profile.get("platform", "none")
        platform_user_id = user_profile.get("platform_user_id", request.user_id)

    if platform == "lastfm":
        id_for_context = platform_user_id
    else:
        id_for_context = request.user_id 

    print(f"INFO: Procesando chat. BD ID: '{request.user_id}', Plataforma: '{platform}'.")

    ai_raw_response = await generate_response_structure(
        user_message=request.message, 
        user_id=id_for_context,
        platform=platform, 
        summary_history=summary_context, 
        is_first_message=is_new_conversation
    )
    
    if hasattr(ai_raw_response, "model_dump"):
        ai_data = ai_raw_response.model_dump()
    elif hasattr(ai_raw_response, "dict"):
        ai_data = ai_raw_response.dict()
    else:
        ai_data = ai_raw_response

    conv_title = ai_data.get("conversation_title")
    if conv_title:
        update_conversation_title(request.user_id, current_conv_id, conv_title)

    final_response_text = ai_data.get('conversational_response', "Hubo un pequeño error procesando la respuesta.")
    rec_type = ai_data.get('recommendation_type', 'info')
    rec_query = ai_data.get('recommendation_query', '')
    history_summary = ai_data.get('history_summary', summary_context)

    spotify_info = None
    audio_preview = None

    if rec_type != 'info' and rec_query:
        search_result = search_spotify_item(rec_query, rec_type)
        
        if search_result:
            spotify_info = {
                "url": search_result['url'],
                "type": rec_type,
                "name": rec_query,
                "image": search_result.get('image')
            }
        else:
            final_response_text += f"\n\n(Nota: No encontré el enlace directo en Spotify para '{rec_query}', pero vale la pena buscarlo en la web)."

        if rec_type == 'track':
            raw_query = rec_query
            
            clean_query = raw_query.replace('"', '').replace("'", "")
            clean_query = re.sub(r'\bby\b', '', clean_query, flags=re.IGNORECASE) 
            clean_query = re.sub(r'[-()]', ' ', clean_query)
            
            clean_query = " ".join(clean_query.split())
            
            print(f"🔍 DEBUG iTUNES: Buscando -> '{clean_query}' (Original: '{raw_query}')")

            itunes_data = search_itunes_preview(clean_query)
            if itunes_data:
                audio_preview = itunes_data
                print(f"✅ DEBUG iTUNES: Preview encontrado para '{clean_query}'. URL: {audio_preview['preview_url']}")
            else:
                print("⚠️ DEBUG iTUNES: No se encontró preview para esta canción limpia.")

    add_summary_to_conversation(request.user_id, current_conv_id, history_summary)
    add_message_to_conversation(request.user_id, current_conv_id, 'bot', final_response_text)

    return {
        "response": final_response_text,
        "conversation_id": current_conv_id,
        "spotify_data": spotify_info,
        "preview_data": audio_preview
    }

@app.get("/history/{user_id}/{conversation_id}")
def history_endpoint(user_id: str, conversation_id: str):
    messages = get_conversation_history(user_id, conversation_id)
    return {"messages": messages}

@app.get("/conversations/{user_id}")
def get_conversations_endpoint(user_id: str):
    summaries = get_all_conversation_summaries(user_id)
    return {"summaries": summaries}


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

@app.post("/login/lastfm")
def login_lastfm(request: LastFMLoginRequest):
    """Endpoint de login Last.FM."""
    username = request.lastfm_username.strip()
    
    internal_user_id = f"lastfm_{username.lower()}"

    save_or_update_user(
        user_id=internal_user_id,
        platform="lastfm",
        platform_user_id=username,
        display_name=username,
        auth_data=None
    )
    
    return {
        "status": "success", 
        "user_id": internal_user_id, 
        "display_name": username
    }

@app.get("/login/ytmusic")
def login_ytmusic():
    """Autorización de YouTube Data API."""
    google_client_id = os.getenv("GOOGLE_CLIENT_ID")
    redirect_uri = os.getenv("YTMUSIC_REDIRECT_URI")
    
    scopes = [
        "openid",
        "https://www.googleapis.com/auth/userinfo.profile",
        "https://www.googleapis.com/auth/userinfo.email",
        "https://www.googleapis.com/auth/youtube.readonly"
    ]
    
    auth_url = "https://accounts.google.com/o/oauth2/v2/auth"
    params = {
        "client_id": google_client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": " ".join(scopes),
        "access_type": "offline",
        "prompt": "consent"
    }
    
    url = f"{auth_url}?{urllib.parse.urlencode(params)}"
    return {"url": url}

@app.get("/callback/ytmusic")
def callback_ytmusic(code: str):
    """Callback de Google OAuth."""
    client_id = os.getenv("GOOGLE_CLIENT_ID")
    client_secret = os.getenv("GOOGLE_CLIENT_SECRET")
    redirect_uri = os.getenv("YTMUSIC_REDIRECT_URI")
    
    token_url = "https://oauth2.googleapis.com/token"
    data = {
        "code": code,
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": redirect_uri,
        "grant_type": "authorization_code"
    }
    
    response = requests.post(token_url, data=data)
    token_info = response.json()
    
    if "error" in token_info:
        print(f"🔴 ERROR en callback de Google: {token_info}")
        return RedirectResponse(url=f"{FRONT_URL}?error=ytmusic_auth_failed")
        
    headers = {"Authorization": f"Bearer {token_info['access_token']}"}
    profile_res = requests.get("https://www.googleapis.com/oauth2/v2/userinfo", headers=headers)
    profile_data = profile_res.json()
    
    google_user_id = profile_data['id']
    display_name = profile_data.get('name', 'Usuario de YouTube')
    
    internal_user_id = f"yt_{google_user_id}"
    
    save_or_update_user(
        user_id=internal_user_id,
        platform="ytmusic",
        platform_user_id=google_user_id,
        display_name=display_name,
        auth_data=token_info
    )
    
    return RedirectResponse(url=f"{FRONT_URL}?uid={internal_user_id}")

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