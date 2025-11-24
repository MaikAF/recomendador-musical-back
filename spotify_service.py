import spotipy
import time
from database import get_user_token, save_user_token # Asumiendo que database.py tiene estas funciones
from spotipy.oauth2 import SpotifyOAuth
import os
from dotenv import load_dotenv
from database import get_user_token, save_user_token

load_dotenv()

# Reutilizamos la configuración de OAuth para refrescar tokens
sp_oauth = SpotifyOAuth(
    client_id=os.getenv("SPOTIFY_CLIENT_ID"),
    client_secret=os.getenv("SPOTIFY_CLIENT_SECRET"),
    redirect_uri=os.getenv("SPOTIFY_REDIRECT_URI"),
    scope="user-read-private user-read-email user-top-read user-read-recently-played"
)

def get_valid_sp_client(user_id):
    """Recupera el token, lo refresca si es necesario y devuelve el cliente de Spotify listo."""
    token_info = get_user_token(user_id)
    
    if not token_info:
        return None

    # Verificar si el token ha expirado (con un margen de 60 segundos)
    now = int(time.time())
    expires_at = token_info.get('expires_at')

    if expires_at is None:
        is_expired = True
    else:
        is_expired = expires_at - now < 60


    if is_expired:
        try:
            refresh_token = token_info.get('refresh_token')
            if not refresh_token:
                print(f"No hay refresh token para el usuario {user_id}, requiere login nuevamente.")
                return None
            new_token_info = sp_oauth.refresh_access_token(refresh_token)
            if 'refresh_token' not in new_token_info:
                new_token_info['refresh_token'] = refresh_token
            
            save_user_token(user_id, new_token_info) # Guardamos el nuevo token
            print(f"Token refrescado para usuario {user_id}")
            token_info = new_token_info
        except Exception as e:
            print(f"Error refrescando token: {e}")
            return None

    return spotipy.Spotify(auth=token_info['access_token'])

def get_user_context(user_id):
    """Descarga los gustos musicales del usuario para dárselos a la IA."""
    sp = get_valid_sp_client(user_id)
    if not sp:
        return "Usuario no conectado a Spotify o sesión expirada."

    try:
        # 1. Obtener Artistas Top (Largo plazo)
        top_artists_data = sp.current_user_top_artists(limit=15, time_range='medium_term')
        top_artists_info = []
        for artist in top_artists_data['items']:
            genres = ', '.join(artist['genres'][:2])
            top_artists_info.append(f"{artist['name']} ({genres})") 

        # 2. Obtener Canciones Recientes (Corto plazo)
        recent_data = sp.current_user_recently_played(limit=10)
        recent_tracks = [f"{item['track']['name']} - {item['track']['artists'][0]['name']}" for item in recent_data['items']]

        # Formatear el texto para el Prompt
        context_str = f"""
        PERFIL DE SPOTIFY:
        - Artistas Top: {', '.join(top_artists_info)}.
        - Canciones Recientes: {', '.join(recent_tracks)}.
        
        Usa esta información para personalizar tu recomendación. Si su gusto es X, no recomiendes X, recomienda algo compatible pero nuevo (Z).
        """
        print ("el contexto es:", context_str)
        return context_str

    except Exception as e:
        print(f"Error obteniendo datos de Spotify: {e}")
        return "No se pudo obtener el contexto musical detallado."