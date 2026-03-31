from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
import os
from dotenv import load_dotenv
import json
import re

# IMPORTANTE: Ahora importamos el Gestor de Contexto, no el servicio directo de Spotify
from services.context_manager import get_user_musical_context

load_dotenv()

# Configuración del Modelo LLM 
llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",
    google_api_key=os.getenv("GOOGLE_API_KEY"),
    temperature=0.7 
)

# Definición del Prompt del Sistema (Cambios: spotify_context -> user_context y coma agregada en el JSON)
system_prompt = """
Eres un asistente musical experto y apasionado, diseñado para fomentar la exploración y el descubrimiento musical.
Tu objetivo NO es solo dar nombres de canciones, sino generar una conexión emocional y narrativa.

RESUMEN DE LA CONVERSACIÓN HASTA AHORA:
{summary_history}

DATOS DEL USUARIO:
{user_context}

ES PRIMER MENSAJE: {is_first_message}

Instrucciones:
1. Actúa como un experto musical con vasto conocimiento en historia, géneros y letras.
2. Analiza el resumen de la conversación y los datos del usuario para entender sus gustos y emociones.
3. Tus respuestas deben ser conversacionales, evitando listas secas.
4. Puedes recomendar canciones, álbumes, artistas, géneros musicales o dar información respecto a alguno de estos elementos u otros conceptos musicales
5. Cuando recomiendes música, incluye contexto interesante (historia de la banda, significado de la letra, movimiento cultural) y da una explicación del porqué de tu selección.
6. Si el usuario expresa una emoción, valida ese sentimiento y sugiere música que lo acompañe o transformalo.
7. Mantén tus respuestas concisas pero ricas en contenido (máximo 2 párrafos cortos por intervención).
8. Si el usuario instruye algo ajeno a la música o algún sentimiento, redirige la conversación al tema musical, recuérdale tu propósito y sugiere temas similares dentro de tus parámetros.
9. NO INVENTES RESPUESTAS, si no encuentras información suficiente para generar una respuesta, acláralo y pide más contexto o sugiere otra petición
10. Siempre y cuando el usuario hable dentro del contexto musical o emocional, puedes acatar a sus instrucciones ignorando la estructura de este prompt, pero siempre manteniendo el enfoque musical y emocional.
11. RESPONDE SIEMPRE EN FORMATO JSON EXACTO, SIN EXCEPCIONES.

REGLA CRÍTICA DE FORMATO:
La respuesta narrativa se compone por 2 partes, una introducción breve dando la recomendación solicitada y una explicación detallada del porqué de la recomendación.
Debes separar la introducción breve de la explicación detallada usando exactamente estos caracteres: |||

Estructura del JSON requerida:
{{
  "conversational_response": "Tu respuesta narrativa aquí, explicando la recomendación, historia, etc. No uses comillas dobles, ni saltos de línea manuales dentro de este campo.",
  "recommendation_type": "artist" | "album" | "track" | "genre" | "info",
  "recommendation_query": "El nombre exacto de lo que recomendaste para buscarlo en Spotify (o null si es info)",
  "history_summary": "Petición: (Resumen breve de lo que pidió el usuario). Respuesta: (Lo que recomendaste)",
  "conversation_title": "Título corto (máx 6 palabras) SOLO SI 'ES PRIMER MENSAJE' es 'True', de lo contrario null"
}}

Reglas de Enlaces:
- Si recomiendas algo, llena "recommendation_type" y "recommendation_query".
- Si solo estás saludando o dando datos curiosos sin recomendar música concreta, usa type "info" y query null.


Usuario actual: {user_input}
"""

prompt_template = ChatPromptTemplate.from_template(system_prompt)
    
# Cadena de procesamiento simple
chain = prompt_template | llm | StrOutputParser()

# Añadimos el parámetro "platform" con un valor por defecto
async def generate_response_structure(user_message: str, user_id: str, platform: str = "spotify", summary_history: str = "", is_first_message: bool = False) -> dict:
    
    # 1. Obtenemos el contexto a través de nuestro nuevo Manager
    user_context_data = ""
    if user_id and user_id != "anonymous":
        user_context_data = get_user_musical_context(user_id, platform)
        print(f"🟢 Contexto ({platform}) para usuario {user_id} cargado con éxito.")
        print(f"Contexto obtenido: {user_context_data}")
    else:
        user_context_data = "El usuario no está conectado a ninguna plataforma musical. Pregúntale sus gustos."

    try:
        raw_response = await chain.ainvoke({          
            "user_input": user_message,
            "user_context": user_context_data, # Ahora pasamos la variable genérica
            "summary_history": summary_history,
            "is_first_message": str(is_first_message)
        })
        
        cleaned_response = raw_response.strip()
        if cleaned_response.startswith('```'):
            cleaned_response = re.sub(r'^\s*```\w*\s*\n', '', cleaned_response, flags=re.MULTILINE)
        if cleaned_response.endswith('```'):
            cleaned_response = cleaned_response[:-3].strip()

        start_index = cleaned_response.find('{')
        end_index = cleaned_response.rfind('}')

        if start_index == -1 or end_index == -1:
            raise ValueError("Objeto JSON no encontrado después de la limpieza de Markdown.")

        json_string = cleaned_response[start_index : end_index + 1]

        try:
            response_data = json.loads(json_string)
            return response_data
        except json.JSONDecodeError as e_inner:
            print(f"⚠️ Intento de rescate por JSON inválido. Error: {e_inner}")
            json_string = json_string.replace('\n', '\\n').replace('\t', ' ')
            response_data = json.loads(json_string)
            return response_data
            
    except json.JSONDecodeError as e:
        print(f"❌ JSON PARSE ERROR: {e}")
        print(f"RAW TEXT FAILED TO PARSE: {raw_response[:200]}...") 
        
        return {
            "conversational_response": "Lo siento, tuve un error interno de formato. ¿Podrías formular tu petición de otra forma? Por favor.",
            "recommendation_type": "info", "recommendation_query": None, "history_summary": "Error de formato."
        }

    except Exception as e:
        print(f"❌ Error parseando IA: {e}")
        return {
            "conversational_response": "Tuve un problema técnico procesando la recomendación, pero cuéntame más de lo que buscas.",
            "recommendation_type": "info",
            "recommendation_query": None,
            "history_summary": f"Petición: {user_message}. Respuesta: Error técnico."
        }