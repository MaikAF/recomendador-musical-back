import os
import requests

LASTFM_BASE_URL = "http://ws.audioscrobbler.com/2.0/"

def get_lastfm_user_profile(username: str, limit: int = 10):
    """Obtiene perfil público de Last.FM del usuario."""
    api_key = os.getenv("LASTFM_API_KEY")
    
    if not api_key:
        print("🔴 Error: LASTFM_API_KEY no encontrada en las variables de entorno.")
        return None

    base_params = {
        "user": username,
        "api_key": api_key,
        "format": "json",
        "limit": limit
    }

    try:
        top_artists_params = {**base_params, "method": "user.gettopartists"}
        artists_response = requests.get(LASTFM_BASE_URL, params=top_artists_params)
        artists_data = artists_response.json()

        if "error" in artists_data:
            print(f"⚠️ Error de Last.FM: {artists_data.get('message')}")
            return {"error": artists_data.get('message')}

        recent_tracks_params = {**base_params, "method": "user.getrecenttracks"}
        tracks_response = requests.get(LASTFM_BASE_URL, params=recent_tracks_params)
        tracks_data = tracks_response.json()

        top_artists = []
        if "topartists" in artists_data and "artist" in artists_data["topartists"]:
            for artist in artists_data["topartists"]["artist"]:
                top_artists.append({
                    "name": artist["name"],
                    "playcount": int(artist["playcount"])
                })

        recent_tracks = []
        if "recenttracks" in tracks_data and "track" in tracks_data["recenttracks"]:
            for track in tracks_data["recenttracks"]["track"]:
                artist_name = track.get("artist", {}).get("#text", "Desconocido")
                album_name = track.get("album", {}).get("#text", "Desconocido")
                track_name = track.get("name", "Desconocido")
                
                recent_tracks.append({
                    "name": track_name,
                    "artist": artist_name,
                    "album": album_name
                })

        return {
            "username": username,
            "top_artists": top_artists,
            "recent_tracks": recent_tracks
        }

    except requests.exceptions.RequestException as e:
        print(f"🔴 Error de conexión con Last.FM: {e}")
        return {"error": "Error de conexión con el servicio de Last.FM"}
    except Exception as e:
        print(f"🔴 Error inesperado procesando Last.FM: {e}")
        return {"error": "Error interno del servidor"}