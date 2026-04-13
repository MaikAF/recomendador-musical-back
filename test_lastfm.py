import os
import json
from dotenv import load_dotenv

try:
    from services.lastfm_service import get_lastfm_user_profile
except ImportError:
    from services.lastfm_service import get_lastfm_user_profile

def test_lastfm():
    print("Cargando variables de entorno...")
    load_dotenv()
    
    if not os.getenv("LASTFM_API_KEY"):
        print("🔴 ERROR: No se encontró LASTFM_API_KEY en el archivo .env")
        return

    test_username = input("Ingresa un usuario de Last.FM para probar (presiona Enter para usar 'rj'): ")
    if not test_username.strip():
        test_username = "rj"

    print(f"\n🔍 Consultando el perfil de: '{test_username}'...")
    
    # Llamamos a la función
    resultado = get_lastfm_user_profile(test_username, limit=5)

    if resultado and "error" not in resultado:
        print("\n✅ Conexión exitosa. Aquí están los datos procesados:\n")
        # Usamos json.dumps para imprimir el diccionario de forma bonita y legible
        print(json.dumps(resultado, indent=4, ensure_ascii=False))
        
        print("\n✨ ¡Todo listo! Este es el JSON exacto que tu backend le enviará al frontend y a Gemini.")
    else:
        print(f"\n❌ Hubo un problema con la consulta: {resultado}")

if __name__ == "__main__":
    test_lastfm()