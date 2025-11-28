import firebase_admin
from firebase_admin import credentials, firestore
import os
import uuid
from datetime import datetime


# Evita inicializar la app múltiples veces si el servidor se recarga
if not firebase_admin._apps:
    # Carga las credenciales
    cred = credentials.Certificate("serviceAccountKey.json")
    firebase_admin.initialize_app(cred)

db = firestore.client()

def save_user_token(user_id, token_info):
    """
    Guarda los tokens de Spotify en la colección 'users' según tu modelo NoSQL.
    """
    users_ref = db.collection('users')
    users_ref.document(user_id).set(token_info, merge=True)
    print(f"Tokens guardados para el usuario {user_id}")

def get_user_token(user_id):
    #Recupera los tokens para hacer peticiones a Spotify
    doc = db.collection('users').document(user_id).get()
    if doc.exists:
        return doc.to_dict()
    return None

def create_new_conversation(user_id):
    """Crea una nueva conversación vacía y devuelve su ID."""
    conversation_id = str(uuid.uuid4())
    
    # Referencia al documento de la nueva conversación
    conv_ref = db.collection('users').document(user_id).collection('conversations').document(conversation_id)
    
    conv_data = {
        'conversation_id': conversation_id,
        'fecha_inicio': datetime.now(),
        'resumen': 'Nueva conversación', # Podríamos generar esto con IA luego
        'mensajes': [] # Array vacío inicial
    }
    
    conv_ref.set(conv_data)
    return conversation_id

def add_message_to_conversation(user_id, conversation_id, role, text):
    """Agrega un mensaje (usuario o bot) al array de mensajes."""
    conv_ref = db.collection('users').document(user_id).collection('conversations').document(conversation_id)
    
    new_message = {
        'role': role, # 'user' o 'bot'
        'text': text,
        'timestamp': datetime.now()
    }
    
    # Usamos ArrayUnion para agregar eficientemente sin sobrescribir
    conv_ref.update({
        'mensajes': firestore.ArrayUnion([new_message])
    })

def get_conversation_history(user_id, conversation_id):
    """Recupera los mensajes de una conversación específica."""
    conv_ref = db.collection('users').document(user_id).collection('conversations').document(conversation_id)
    doc = conv_ref.get()
    
    if doc.exists:
        return doc.to_dict().get('mensajes', [])
    return []
#SE VERA ESTO MAS TARDE
def check_conversation_limits(user_id, conversation_id):
    """
    Verifica si el usuario puede enviar mensajes.
    Retorna: (puede_enviar: bool, mensaje_error: str)
    """
    # 1. Verificar límite de mensajes en la conversación actual
    mensajes = get_conversation_history(user_id, conversation_id)
    # Contamos solo los del usuario para ser justos, o el total (user+bot)
    # Tu regla dice "10 mensajes emitidos por el usuario"
    user_msgs_count = sum(1 for m in mensajes if m['role'] == 'user')
    
    if user_msgs_count >= 10:
        return False, "Has alcanzado el límite de 10 mensajes en esta conversación."
        
    return True, ""

def check_new_chat_limit(user_id):
    """Verifica si el usuario puede crear más chats."""
    # Contar documentos en la subcolección 'conversations'
    convs_ref = db.collection('users').document(user_id).collection('conversations')
    # Nota: count() es más eficiente en Firestore moderno
    count = 0
    for _ in convs_ref.stream():
        count += 1
        
    if count >= 3:
        return False
    return True


def save_feedback(user_id, feedback_data):
    """
    Guarda la retroalimentación del usuario.
    Estructura basada en el diagrama de datos de la tesis.
    """
    feedback_ref = db.collection('feedback').document() # ID autogenerado
    
    # Preparamos el objeto según el esquema definido
    data_to_save = {
        'User_Hash': user_id, # Usamos el ID como hash identificador
        'Rating': feedback_data.get('rating'),
        'Respuestas_cualitativas': {
            'Interacción_agradable': feedback_data.get('pleasant_interaction'), # Binario
            'motivacion_exploracion': feedback_data.get('motivated_exploration'), # Binario
            'comentarios_adicionales': feedback_data.get('comments') # Texto libre
        },
        'Fecha_de_creación': datetime.now()
    }
    
    feedback_ref.set(data_to_save)
    return feedback_ref.id

def get_all_conversation_summaries(user_id):
    """Recupera el ID y el resumen de todos los chats de un usuario para la barra lateral."""
    
    convs_ref = db.collection('users').document(user_id).collection('conversations')
    
    # Obtenemos solo el ID del documento y el campo 'resumen'
    summaries = []
    # Utilizamos .stream() para iterar sobre los documentos
    for doc in convs_ref.stream():
        data = doc.to_dict()
        summaries.append({
            'id': doc.id,
            'resumen': data.get('resumen', 'Chat sin título'),
            'fecha': data.get('fecha_inicio', 'N/A')
        })
    return summaries


def delete_conversation(user_id, conversation_id):
    """Elimina un chat específico (CU5: Borrar historial de chat)."""
    conv_ref = db.collection('users').document(user_id).collection('conversations').document(conversation_id)
    conv_ref.delete()
    
def delete_all_conversations(user_id):
    """Elimina todos los chats de un usuario."""
    # Este es más complejo en Firestore ya que requiere batching para subcolecciones grandes,
    # pero para el MVP podemos usar una solución simple que itere y elimine.
    
    convs_ref = db.collection('users').document(user_id).collection('conversations')
    # Obtenemos todas las referencias
    docs = convs_ref.list_documents() 
    
    for doc in docs:
        doc.delete()

def delete_user_session(user_id):
    """
    Cierra sesión eliminando SOLO las credenciales de Spotify.
    Mantiene el historial de chat para cuando el usuario vuelva a ingresar.
    """
    user_ref = db.collection('users').document(user_id)
    
    # Eliminamos solo los campos que permiten la conexión
    # Asumiendo que guardamos el diccionario de Spotify tal cual
    updates = {
        'access_token': firestore.DELETE_FIELD,
        'refresh_token': firestore.DELETE_FIELD,
        'expires_in': firestore.DELETE_FIELD,
        'expires_at': firestore.DELETE_FIELD,
        'scope': firestore.DELETE_FIELD,
        'token_type': firestore.DELETE_FIELD
    }
    
    try:
        user_ref.update(updates)
        print(f"Sesión cerrada para {user_id}: Credenciales eliminadas, historial conservado.")
        return True
    except Exception as e:
        print(f"Error cerrando sesión: {e}")
        return False

def add_summary_to_conversation(user_id, conversation_id, summary_text):
    #Agrega un item de resumen estructurado al historial.
    conv_ref = db.collection('users').document(user_id).collection('conversations').document(conversation_id)
    
    # Guardamos en un campo array llamado 'summary_history'
    conv_ref.update({
        'summary_history': firestore.ArrayUnion([summary_text])
    })

def get_summary_context(user_id, conversation_id):
    #Recupera solo los resúmenes para dárselos a la IA como contexto.
    conv_ref = db.collection('users').document(user_id).collection('conversations').document(conversation_id)
    doc = conv_ref.get()
    
    if doc.exists:
        summaries = doc.to_dict().get('summary_history', [])
        # Unimos todo en un solo bloque de texto
        return "\n".join(summaries)
    return ""

def update_conversation_title(user_id, conversation_id, new_title):
    #Actualiza el título de una conversación.
    conv_ref = db.collection('users').document(user_id).collection('conversations').document(conversation_id)
    conv_ref.update({
        'resumen': new_title
    })
    print(f"Título actualizado para chat {conversation_id}: {new_title}")