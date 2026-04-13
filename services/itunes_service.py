import requests
import urllib.parse

def search_itunes_preview(query: str):
    """Busca canción en iTunes API y recupera enlace de audio (.m4a) y portada."""
    safe_query = urllib.parse.quote(query)
    url = f"https://itunes.apple.com/search?term={safe_query}&entity=song&limit=1"
    
    try:
        response = requests.get(url, timeout=5)
        data = response.json()
        
        if data.get("resultCount", 0) > 0:
            track = data["results"][0]
            
            if "previewUrl" in track:
                return {
                    "preview_url": track["previewUrl"],
                    "track_name": track["trackName"],
                    "artist_name": track["artistName"],
                    "cover_url": track.get("artworkUrl100", "")
                }
        return None
    except Exception as e:
        print(f"🔴 Error buscando preview en iTunes: {e}")
        return None