import spotipy
import time
from database import get_user_token, update_user_auth_data # Asumiendo que database.py tiene estas funciones
from spotipy.oauth2 import SpotifyOAuth
import os
from dotenv import load_dotenv
from spotipy.cache_handler import MemoryCacheHandler
from pathlib import Path
from difflib import SequenceMatcher

env_path = Path(__file__).parent.parent/ '.env'
load_dotenv(dotenv_path=env_path)

def similar(a, b):
    #Retorna un ratio de similitud entre 0 y 1.
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()

CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")
REDIRECT_URI = os.getenv("SPOTIFY_REDIRECT_URI")
SCOPE = "user-read-private user-read-email user-top-read user-read-recently-played"

if not CLIENT_ID:
    # Esto explotará si no encuentra el archivo .env, lo cual es bueno
    raise ValueError(f"Falta SPOTIFY_CLIENT_ID. Archivo .env buscado en: {env_path}")

def get_spotify_oauth_client():
    """Devuelve una nueva instancia de SpotifyOAuth limpia y robusta."""    

    return SpotifyOAuth(
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        redirect_uri=REDIRECT_URI,
        scope=SCOPE,
        cache_handler=MemoryCacheHandler() 
    )

def get_spotify_client(access_token):
    """Devuelve un objeto Spotipy para hacer llamadas a la API."""
    return spotipy.Spotify(auth=access_token)

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
            
            update_user_auth_data(user_id, new_token_info) # Guardamos el nuevo token
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
    

def search_spotify_item(query, type_filter):
    """
    Busca un elemento en Spotify y devuelve su URL externa.
    type_filter puede ser: 'artist', 'album', 'track', 'genre' (busca playlist), 'info'
    """
    if type_filter == 'info' or not query:
        return None

    # Mapeo de tipos para la API de Spotify
    spotify_type = type_filter
    if type_filter == 'genre':
        spotify_type = 'playlist' # Si es género, buscamos una playlist
        query = f"The Sound of {query}" 
    elif type_filter == 'song': # A veces la IA dice 'song' en vez de 'track'
        spotify_type = 'track'

    try:
        # Configuración del cliente de Spotify
        client_credentials_manager = spotipy.oauth2.SpotifyClientCredentials(
            client_id=os.getenv("SPOTIFY_CLIENT_ID"),
            client_secret=os.getenv("SPOTIFY_CLIENT_SECRET")
        )
        sp_search = spotipy.Spotify(client_credentials_manager=client_credentials_manager)

        results = sp_search.search(q=query, limit=1, type=spotify_type)
        
        items = results.get(f'{spotify_type}s', {}).get('items', [])
        
        if items:
            item = items[0]
            found_name = item['name']

            # Validación de similitud
            # Si es género/playlist, es menos estricta (0.4). Si es canción/artista, mas estricta (0.6).
            threshold = 0.4 
            similarity = similar(query, found_name)
            
            if similarity < threshold:
                print(f"Descartado por baja similitud: Buscado '{query}' vs Encontrado '{found_name}' ({similarity:.2f})")
                return None
            
            external_url = item['external_urls']['spotify']
            image_url = None
            
            # Lógica para extraer imagen según el tipo
            try:
                if spotify_type == 'track':
                    # Las canciones tienen la imagen en el álbum
                    if item.get('album') and item['album'].get('images'):
                        image_url = item['album']['images'][0]['url'] # 0 es la más grande
                else:
                    # Artistas, Albumes y Playlists tienen 'images' directo
                    if item.get('images'):
                        image_url = item['images'][0]['url']
            except IndexError:
                pass # Si no hay imagen, se queda en None

            preview_url = item.get('preview_url') if spotify_type == 'track' else None
            print(f"Encontrado en Spotify: '{found_name}' con similitud {similarity:.2f}. URL: {external_url}, Imagen: {image_url}")
            return {
                'url': external_url,
                'image': image_url,
                'preview_url': preview_url
            }
        
        return None

    except Exception as e:
        print(f"Error buscando en Spotify: {e}")
        return None