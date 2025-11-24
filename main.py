from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
import spotipy
from spotipy.oauth2 import SpotifyOAuth
import os
from dotenv import load_dotenv
from database import save_user_token
from pydantic import BaseModel
from chat_logic import generate_response


load_dotenv()

app = FastAPI(title="Asistente Musical IA API")

class ChatRequest(BaseModel):
    message: str
    user_id: str


# Configuración CORS para permitir peticiones desde React (Vite usa puerto 5173 por defecto)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", "http://127.0.0.1:8000"], 
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
    # Redirige al usuario a Spotify para autenticarse 
    auth_url = sp_oauth.get_authorize_url()
    return {"url": auth_url}

@app.get("/callback")
def callback(code: str):
    # Intercambia el código por un token de acceso
    token_info = sp_oauth.get_access_token(code)
    sp = spotipy.Spotify(auth=token_info['access_token'])
    current_user = sp.current_user()
    user_id = current_user['id']
    save_user_token(user_id, token_info)
    return RedirectResponse(url=f"http://127.0.0.1:5173?uid={user_id}")

# Endpoint para el chat 
@app.post("/chat")
async def chat_endpoint(request: ChatRequest):
    response_text = await generate_response(request.message, request.user_id)
    return {"response": response_text}