from services.lastfm_service import get_lastfm_user_profile
from services.spotify_service import get_user_context as get_spotify_user_data
from services.ytmusic_service import get_ytmusic_user_data
from database import get_user_token # Asegúrate de importar esto


def build_ytmusic_context(user_id: str) -> str:
    """Extrae y formatea los datos de YouTube Music para el LLM."""
    # Obtenemos los tokens desde la base de datos (campo auth_data)
    auth_data = get_user_token(user_id)
    
    print(f"🔍 DEBUG YT: Buscando tokens para ID: {user_id}")
    print(f"🔍 DEBUG YT: Lo que trajo la BD: {auth_data}")

    if not auth_data or "access_token" not in auth_data:
        return "El usuario no tiene una cuenta de YouTube Music vinculada."

    data = get_ytmusic_user_data(auth_data["access_token"])
    
    if not data:
        return "No se pudo recuperar la información de YouTube Music."

    contexto = "Historial musical del usuario (basado en YouTube Music):\n"
    
    if data["playlists"]:
        contexto += f"- Sus listas de reproducción incluyen: {', '.join(data['playlists'])}.\n"
    
    if data["recent_likes"]:
        contexto += f"- Le han gustado recientemente estos videos/canciones: {', '.join(data['recent_likes'])}.\n"
    
    return contexto

def build_lastfm_context(username: str) -> str:
    """Extrae y formatea los datos de Last.FM en texto plano para el LLM."""
    data = get_lastfm_user_profile(username)
    
    if not data or "error" in data:
        return "El usuario no tiene historial disponible en Last.FM."

    artistas = [artist['name'] for artist in data.get('top_artists', [])]
    canciones = [f"{t['name']} de {t['artist']}" for t in data.get('recent_tracks', [])]

    contexto = "Historial musical del usuario (basado en Last.FM):\n"
    if artistas:
        contexto += f"- Artistas más escuchados: {', '.join(artistas)}.\n"
    if canciones:
        contexto += f"- Escuchado recientemente: {', '.join(canciones)}.\n"
    
    return contexto

def build_spotify_context(user_id: str) -> str:
    """Extrae y formatea los datos de Spotify."""
    data = get_spotify_user_data(user_id)
    
    if not data:
        return "El usuario no tiene historial disponible en Spotify."

    # Si tu función ya devolvía un string formateado, lo pasamos directo
    if isinstance(data, str):
        return data

    # Si devuelve un diccionario, lo estructuramos para Gemini
    contexto = "Historial musical del usuario (basado en Spotify):\n"
    
    # Manejo dinámico asumiendo que data tiene 'top_artists' y 'top_tracks'
    top_artists = data.get('top_artists', [])
    top_tracks = data.get('top_tracks', [])
    
    if top_artists:
        # Extrae el nombre si es un diccionario, o lo usa directo si es string
        artistas = [a['name'] if isinstance(a, dict) else a for a in top_artists]
        contexto += f"- Artistas más escuchados: {', '.join(artistas)}.\n"
    
    if top_tracks:
        canciones = [t['name'] if isinstance(t, dict) else t for t in top_tracks]
        contexto += f"- Canciones destacadas: {', '.join(canciones)}.\n"
        
    return contexto

def get_user_musical_context(user_id: str, platform: str) -> str:
    """
    Router principal de contexto.
    """
    platform = platform.lower()
    
    if platform == 'lastfm':
        return build_lastfm_context(user_id)
    elif platform == 'spotify':
        return build_spotify_context(user_id)
    elif platform == 'ytmusic':
        return build_ytmusic_context(user_id)
    else:
        return "Sin contexto musical previo. El usuario es nuevo o anónimo."