import os
import asyncio
import json
from dotenv import load_dotenv

# Ajusta la ruta de importación según dónde tengas tu chat_logic.py
try:
    # Si test.py está en la raíz y chat_logic dentro de 'app' o 'routers'
    from chat_logic import generate_response_structure
except ImportError:
    try:
        from app.chat_logic import generate_response_structure
    except ImportError as e:
        print(f"🔴 Error importando chat_logic. Revisa las rutas: {e}")
        exit(1)

async def run_test():
    print("Cargando variables de entorno...")
    load_dotenv()
    
    # Validamos que tengamos las llaves necesarias
    if not os.getenv("GOOGLE_API_KEY") or not os.getenv("LASTFM_API_KEY"):
        print("🔴 ERROR: Faltan GOOGLE_API_KEY o LASTFM_API_KEY en el .env")
        return

    # Configuración de la prueba solicitada
    test_username = "duwang_acagar"
    test_platform = "lastfm"
    test_prompt = "recomiendame una cancion"

    print(f"\n🤖 Iniciando prueba de la IA (Gemini)...")
    print(f"👤 Extrayendo contexto de: {test_username} vía {test_platform.upper()}")
    print(f"💬 Prompt del usuario: '{test_prompt}'\n")
    print("⏳ Consultando a la IA (esto puede tomar un par de segundos)...\n")

    try:
        # Llamamos a tu función asíncrona
        resultado = await generate_response_structure(
            user_message=test_prompt,
            user_id=test_username,
            platform=test_platform,
            is_first_message=True # Simulamos que es el inicio del chat
        )

        print("✅ Respuesta estructurada recibida:\n")
        # Imprimimos el JSON resultante de forma bonita
        print(json.dumps(resultado, indent=4, ensure_ascii=False))

    except Exception as e:
        print(f"🔴 Error durante la ejecución de la prueba: {e}")

if __name__ == "__main__":
    # Como la función base es async, necesitamos correrla dentro del loop de asyncio
    asyncio.run(run_test())