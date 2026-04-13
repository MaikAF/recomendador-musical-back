from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.output_parsers import JsonOutputParser
import os
from dotenv import load_dotenv
from services.context_manager import get_user_musical_context

load_dotenv()

# Esquema de respuesta y parser JSON
response_schema = {
    "type": "object",
    "properties": {
        "intro": {"type": "string", "description": "Respuesta corta o recomendación directa."},
        "details": {"type": "string", "description": "Explicación detallada, historia o contexto emocional."},
        "recommendation_type": {"type": "string", "enum": ["artist", "album", "track", "genre", "info"]},
        "recommendation_query": {"type": "string", "nullable": True},
        "history_summary": {"type": "string"},
        "conversation_title": {"type": "string", "nullable": True}
    },
    "required": ["intro", "details", "recommendation_type", "recommendation_query", "history_summary", "conversation_title"]
}

parser = JsonOutputParser()

# Configuración del modelo LLM
llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",
    google_api_key=os.getenv("GOOGLE_API_KEY"),
    temperature=0.7,
    model_kwargs={
        "generation_config": {
            "response_mime_type": "application/json",
            "response_schema": response_schema
        }
    }
)

# Prompt del sistema
SYSTEM_INSTRUCTION = f"""
Eres un asistente musical experto y apasionado. Tu objetivo es generar conexiones emocionales y descubrimientos.

INSTRUCCIONES DE FORMATO:
{parser.get_format_instructions()}

REGLAS DE PERSONALIDAD:
1. Sé conversacional. Si el usuario solo chatea, responde corto y con chispa. 
2. No recomiendes NADA que esté en la lista de 'YA RECOMENDADOS'.
3. Si el usuario da descripciones creativas (ej. 'carnicería futurista'), úsalas para validar y profundizar.
4. 'intro' debe ser la respuesta inmediata. 'details' es el valor agregado (historia, contexto).

EJEMPLOS DE DIÁLOGO CORTO:
- Usuario: "Me gustó esa banda."
- IA: {{"intro": "¡Qué bueno! ¿Qué fue lo que más te enganchó?", "details": "A veces es el ritmo, otras la voz...", "recommendation_type": "info", "recommendation_query": null, "history_summary": "...", "conversation_title": "..."}}
"""

async def generate_response_structure(
    user_message: str, 
    user_id: str, 
    platform: str = "spotify", 
    summary_history: str = "", 
    is_first_message: bool = False,
    already_recommended: list = None
) -> dict:
    
    if already_recommended is None:
        already_recommended = []
        
    # Contexto musical de usuario
    user_context_data = "El usuario no está conectado. Pregúntale sus gustos."
    if user_id and user_id != "anonymous":
        user_context_data = get_user_musical_context(user_id, platform)

    # Prompt dinámico
    dynamic_context = f"""
    CONTEXTO MUSICAL DEL USUARIO: {user_context_data}
    RESUMEN DE CHARLA: {summary_history}
    YA RECOMENDADOS (PROHIBIDO REPETIR): {", ".join(already_recommended)}
    ¿ES INICIO DE CHARLA?: {is_first_message}
    """

    try:
        chain = llm | parser
        
        data = await chain.ainvoke([
            SystemMessage(content=SYSTEM_INSTRUCTION),
            SystemMessage(content=dynamic_context),
            HumanMessage(content=user_message)
        ])

        return {
            "conversational_response": f"{data.get('intro', '')} ||| {data.get('details', '')}",
            "recommendation_type": data.get('recommendation_type', 'info'),
            "recommendation_query": data.get('recommendation_query'),
            "history_summary": data.get('history_summary', summary_history),
            "conversation_title": data.get('conversation_title')
        }

    except Exception as e:
        print(f"❌ Error crítico en chat_logic: {e}")
        
        return {
            "conversational_response": "Tuve un hipo técnico procesando la información, pero aquí sigo. ||| Cuéntame más de lo que buscas.",
            "recommendation_type": "info",
            "recommendation_query": None,
            "history_summary": summary_history,
            "conversation_title": None
        }