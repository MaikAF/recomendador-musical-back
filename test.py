import os
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
from dotenv import load_dotenv

load_dotenv()

def test_spotify_preview(query, type_filter='track'):
    try:
        client_credentials_manager = SpotifyClientCredentials(
            client_id=os.getenv("SPOTIFY_CLIENT_ID"),
            client_secret=os.getenv("SPOTIFY_CLIENT_SECRET")
        )
        sp = spotipy.Spotify(client_credentials_manager=client_credentials_manager)

        # AÑADIDO: market='CL' para buscar licencias locales
        results = sp.search(q=query, limit=1, type=type_filter, market='CL')
        items = results.get(f'{type_filter}s', {}).get('items', [])

        if not items:
            return False

        item = items[0]
        preview_url = item.get('preview_url')
        
        print(f"\n🎵 Probando: {item['name']} - {item['artists'][0]['name']}")
        
        if preview_url:
            print(f"   ✅ ¡ÉXITO! Preview encontrado:")
            print(f"   🔊 URL: {preview_url}")
            return True
        else:
            print("   ❌ Sin preview (Bloqueado por la disquera)")
            return False

    except Exception as e:
        print(f"🔴 Error: {e}")
        return False

if __name__ == "__main__":
    print("Buscando una canción que tenga el preview habilitado en la API...\n")
    
    # Lista estratégica: Mezclamos pop masivo con indie/math rock/midwest emo
    canciones_prueba = [
        "Blinding Lights The Weeknd",
        "Never Meant American Football",
        "Playing God Polyphia",
        "G.O.A.T. Polyphia",
        "Take on Me A-ha"
    ]
    
    for cancion in canciones_prueba:
        # Si encuentra una con preview, detenemos la búsqueda
        if test_spotify_preview(cancion):
            print("\n✨ Usa esta canción en tu frontend para probar el botón de Play.")
            break