import requests
import urllib.parse

def search_itunes_preview(query: str):
    """
    Busca una canción en la API pública de iTunes y devuelve el enlace al archivo de audio (.m4a)
    y la portada del álbum. No requiere autenticación.
    """
    # Codificamos la búsqueda para que soporte espacios y caracteres raros
    safe_query = urllib.parse.quote(query)
    url = f"https://itunes.apple.com/search?term={safe_query}&entity=song&limit=1"
    
    try:
        response = requests.get(url, timeout=5)
        data = response.json()
        
        if data.get("resultCount", 0) > 0:
            track = data["results"][0]
            
            # Verificamos que realmente tenga el preview de audio
            if "previewUrl" in track:
                return {
                    "preview_url": track["previewUrl"],
                    "track_name": track["trackName"],
                    "artist_name": track["artistName"],
                    "cover_url": track.get("artworkUrl100", "") # Portada en 100x100
                }
        return None
    except Exception as e:
        print(f"🔴 Error buscando preview en iTunes: {e}")
        return None