import requests
import urllib.parse

def search_itunes_preview(query: str):
    """Replicación del servicio con prints de diagnóstico."""
    safe_query = urllib.parse.quote(query)
    url = f"https://itunes.apple.com/search?term={safe_query}&entity=song&limit=1"
    
    print(f"\n🔍 DEBUG - URL de búsqueda: {url}")
    
    try:
        response = requests.get(url, timeout=5)
        
        if response.status_code != 200:
            print(f"🔴 ERROR HTTP {response.status_code}: {response.text}")
            return None
            
        data = response.json()
        print(f"📦 DEBUG - Resultados encontrados: {data.get('resultCount', 0)}")
        
        if data.get("resultCount", 0) > 0:
            track = data["results"][0]
            
            if "previewUrl" in track:
                return {
                    "preview_url": track["previewUrl"],
                    "track_name": track["trackName"],
                    "artist_name": track["artistName"],
                    "cover_url": track.get("artworkUrl100", "")
                }
            else:
                print("⚠️ DEBUG - Se encontró la canción, pero Apple no entregó la llave 'previewUrl'.")
        return None
        
    except Exception as e:
        print(f"🔴 DEBUG - Error de conexión/código: {e}")
        return None

if __name__ == "__main__":
    print("🎵 --- TEST DE PREVIEWS DE iTUNES --- 🎵")
    print("Escribe el nombre de una canción y artista para buscar su audio.")
    
    while True:
        query = input("\n🎧 Ingresa tu búsqueda (o 'salir' para terminar): ")
        
        if query.lower() in ['salir', 'exit', 'quit']:
            break
            
            continue
            
        resultado = search_itunes_preview(query)
        
        if resultado:
            print("\n✅ ¡ÉXITO! Preview Encontrado:")
            print(f"   👤 Artista: {resultado['artist_name']}")
            print(f"   🎵 Canción: {resultado['track_name']}")
            print(f"   🖼️  Portada: {resultado['cover_url']}")
            print(f"   ▶️  Audio:   {resultado['preview_url']}")
        else:
            print("\n❌ FALLO: No se obtuvo un preview válido para esta búsqueda.")