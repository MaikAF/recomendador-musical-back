import os
import requests
import urllib.parse
from dotenv import load_dotenv

def test_google_oauth():
    print("Cargando variables de entorno...")
    load_dotenv()
    
    client_id = os.getenv("GOOGLE_CLIENT_ID")
    client_secret = os.getenv("GOOGLE_CLIENT_SECRET")
    redirect_uri = os.getenv("YTMUSIC_REDIRECT_URI")
    
    if not all([client_id, client_secret, redirect_uri]):
        print("🔴 ERROR: Faltan credenciales de Google en tu archivo .env")
        return

    # 1. Generar URL de Autorización
    scopes = [
        "openid",
        "https://www.googleapis.com/auth/userinfo.profile",
        "https://www.googleapis.com/auth/userinfo.email",
        "https://www.googleapis.com/auth/youtube.readonly"
    ]
    
    auth_url = "https://accounts.google.com/o/oauth2/v2/auth"
    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": " ".join(scopes),
        "access_type": "offline",
        "prompt": "consent"
    }
    
    login_url = f"{auth_url}?{urllib.parse.urlencode(params)}"
    
    print("\n" + "="*50)
    print("🌐 PASO 1: Abre este enlace en tu navegador y autoriza la aplicación:")
    print("="*50)
    print(f"\n{login_url}\n")
    print("="*50)
    
    # 2. Esperar el código de redirección
    redirected_url = input("PASO 2: Pega aquí la URL COMPLETA a la que te redirigió Google (la que dice localhost...): ").strip()
    
    try:
        # Extraer el código de la URL
        parsed_url = urllib.parse.urlparse(redirected_url)
        query_params = urllib.parse.parse_qs(parsed_url.query)
        
        if 'code' not in query_params:
            print("🔴 ERROR: No se encontró el parámetro 'code' en la URL proporcionada.")
            return
            
        code = query_params['code'][0]
        print("\n✅ Código extraído correctamente. Intercambiando por tokens...")
        
        # 3. Intercambiar código por tokens
        token_url = "https://oauth2.googleapis.com/token"
        data = {
            "code": code,
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code"
        }
        
        response = requests.post(token_url, data=data)
        token_info = response.json()
        
        if "error" in token_info:
            print(f"🔴 ERROR al obtener tokens: {token_info}")
            return
            
        access_token = token_info['access_token']
        print("✅ Tokens obtenidos con éxito.")
        
        # 4. Probar la API (Obtener perfil)
        print("\n🔍 Consultando perfil del usuario...")
        headers = {"Authorization": f"Bearer {access_token}"}
        profile_res = requests.get("https://www.googleapis.com/oauth2/v2/userinfo", headers=headers)
        profile_data = profile_res.json()
        
        print(f"   👤 Nombre: {profile_data.get('name')}")
        print(f"   📧 Correo: {profile_data.get('email')}")
        print(f"   🆔 Google ID: {profile_data.get('id')}")
        
        # 5. Probar YouTube Data API (Obtener Playlists)
        print("\n🎵 Consultando listas de reproducción de YouTube...")
        yt_res = requests.get(
            "https://www.googleapis.com/youtube/v3/playlists?part=snippet&mine=true&maxResults=5", 
            headers=headers
        )
        yt_data = yt_res.json()
        
        if "items" in yt_data and yt_data["items"]:
            print("   ✅ Playlists encontradas:")
            for item in yt_data["items"]:
                print(f"      - {item['snippet']['title']}")
        else:
            print("   ⚠️ No se encontraron playlists (o el canal de YouTube no está inicializado).")
            
        print("\n✨ ¡Prueba finalizada con éxito! La integración OAuth2 de Google funciona perfecto.")

    except Exception as e:
        print(f"\n🔴 Error inesperado durante la prueba: {e}")

if __name__ == "__main__":
    test_google_oauth()