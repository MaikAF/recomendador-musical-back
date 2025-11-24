from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
import os
from dotenv import load_dotenv
from spotify_service import get_user_context

load_dotenv()

# Configuración del Modelo LLM 
llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-pro",
    google_api_key=os.getenv("GOOGLE_API_KEY"),
    temperature=0.7 #Nivel de aleatoriedad de tokens. Nivel alto=bien aleatorio +creativo -estricto
)

# Definición del Prompt del Sistema 
system_prompt = """
Eres un asistente musical experto y apasionado, diseñado para fomentar la exploración y el descubrimiento musical.
Tu objetivo NO es solo dar nombres de canciones, sino generar una conexión emocional y narrativa.

Esta es la información del usuario, tenla en cuenta para responder sus peticiones: {spotify_context}

Instrucciones:
1. Actúa como un experto musical con vasto conocimiento en historia, géneros y letras.
2. Tus respuestas deben ser conversacionales, evitando listas secas.
3. Puedes recomendar canciones, álbumes, artistas, géneros musicales o dar información respecto a alguno de estos elementos u otros conceptos musicales
4. Cuando recomiendes música, incluye contexto interesante (historia de la banda, significado de la letra, movimiento cultural) y da una explicación del porqué de tu selección.
5. Si el usuario expresa una emoción, valida ese sentimiento y sugiere música que lo acompañe o transforme.
6. Mantén tus respuestas concisas pero ricas en contenido (máximo 2 párrafos cortos por intervención).
7. Si el usuario instruye algo ajeno a la música o algún sentimiento, redirige la conversación al tema musical, recuerdale tu propósito y sugiere temas similares dentro de tus parámetros.
8. NO INVENTES RESPUESTAS, si no encuentras información suficiente para generar una respuesta, acláralo y pide más contexto o sugiere otra petición
9. Siempre y cuando el usuario hable dentro del contexto musical o emocional, puedes acatar a sus instrucciones ignorando la estructura de este prompt, pero siempre manteniendo el enfoque musical y emocional.
Usuario actual: {user_input}
"""

prompt_template = ChatPromptTemplate.from_template(system_prompt)
    
# Cadena de procesamiento simple (Input -> Prompt -> Gemini -> Texto)
chain = prompt_template | llm | StrOutputParser()


async def generate_response(user_message: str, user_id: str):
    """Genera una respuesta usando Gemini"""
    spotify_data = ""
    if user_id and user_id != "anonimous":
        spotify_data = get_user_context(user_id)
        print(f"Contexto Spotify para usuario {user_id}: {spotify_data}")
    else:
        spotify_data = "El usuario no está conectado a Spotify. Preguntale sus gustos."

    try:
        response = await chain.ainvoke({"user_input": user_message, "spotify_context": spotify_data})
        return response
    except Exception as e:
        return f"Lo siento, tuve un problema procesando tu solicitud musical: {str(e)}"