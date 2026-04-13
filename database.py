import firebase_admin
from firebase_admin import credentials, firestore
import os
import uuid
from datetime import datetime
import json
import hashlib

def hash_user_id_securely(user_id):
    """Genera hash anónimo para user ID."""
    salt = os.getenv("FEEDBACK_SECRET_SALT", "default_salt_change_me")
    combined_string = f"{user_id}{salt}"
    return hashlib.sha256(combined_string.encode('utf-8')).hexdigest()

if not firebase_admin._apps:
    try:
        service_account_json = os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON")
        if service_account_json:
            cred_dict = json.loads(service_account_json)
            cred = credentials.Certificate(cred_dict)
            print("INFO: Firebase inicializado con variable de entorno (Producción).")
        else:
            cred = credentials.Certificate("serviceAccountKey.json")
            print("INFO: Firebase inicializado con archivo local (Desarrollo).")
            
        firebase_admin.initialize_app(cred)
    except Exception as e:
        print(f"ERROR FATAL: No se pudo inicializar Firebase. Motivo: {e}")
        raise e

db = firestore.client()

# ==========================================
# GESTIÓN DE USUARIOS MULTIPLATAFORMA
# ==========================================

def save_or_update_user(user_id: str, platform: str, platform_user_id: str, display_name: str = None, auth_data: dict = None):
    """Guarda o actualiza la información del usuario."""
    users_ref = db.collection('users').document(user_id)
    
    data_to_save = {
        "platform": platform,
        "platform_user_id": platform_user_id,
        "last_login": datetime.now()
    }
    
    if display_name:
        data_to_save["display_name"] = display_name
        
    if auth_data is not None:
        data_to_save["auth_data"] = auth_data

    users_ref.set(data_to_save, merge=True)
    print(f"Perfil guardado para {user_id} vía {platform}")

def update_user_auth_data(user_id: str, auth_data: dict):
    """Actualiza tokens de autenticación del usuario."""
    users_ref = db.collection('users').document(user_id)
    users_ref.update({"auth_data": auth_data})
    print(f"Tokens actualizados para {user_id}")

def get_user_profile(user_id):
    """Obtiene perfil público del usuario."""
    doc = db.collection('users').document(user_id).get()
    if doc.exists:
        data = doc.to_dict()
        return {
            "id": user_id,
            "display_name": data.get("display_name", "Usuario"),
            "platform": data.get("platform"),
            "platform_user_id": data.get("platform_user_id")
        }
    return None

def get_user_token(user_id):
    """Obtiene data de autenticación."""
    doc = db.collection('users').document(user_id).get()
    if doc.exists:
        return doc.to_dict().get("auth_data")
    return None

def delete_user_session(user_id):
    """Cierra sesión eliminando data de autenticación (conservador historial)."""
    user_ref = db.collection('users').document(user_id)
    
    try:
        user_ref.update({
            'auth_data': firestore.DELETE_FIELD
        })
        print(f"Sesión cerrada para {user_id}: Credenciales eliminadas, historial conservado.")
        return True
    except Exception as e:
        print(f"Error cerrando sesión: {e}")
        return False

# ==========================================
# GESTIÓN DE CONVERSACIONES
# ==========================================

def create_new_conversation(user_id):
    conversation_id = str(uuid.uuid4())
    conv_ref = db.collection('users').document(user_id).collection('conversations').document(conversation_id)
    
    conv_data = {
        'conversation_id': conversation_id,
        'fecha_inicio': datetime.now(),
        'resumen': 'Nueva conversación',
        'mensajes': [] 
    }
    conv_ref.set(conv_data)
    return conversation_id

def add_message_to_conversation(user_id, conversation_id, role, text):
    conv_ref = db.collection('users').document(user_id).collection('conversations').document(conversation_id)
    new_message = {
        'role': role,
        'text': text,
        'timestamp': datetime.now()
    }
    conv_ref.update({
        'mensajes': firestore.ArrayUnion([new_message])
    })

def get_conversation_history(user_id, conversation_id):
    conv_ref = db.collection('users').document(user_id).collection('conversations').document(conversation_id)
    doc = conv_ref.get()
    if doc.exists:
        return doc.to_dict().get('mensajes', [])
    return []

def check_conversation_limits(user_id, conversation_id):
    mensajes = get_conversation_history(user_id, conversation_id)
    user_msgs_count = sum(1 for m in mensajes if m['role'] == 'user')
    if user_msgs_count >= 10:
        return False, "Has alcanzado el límite de 10 mensajes en esta conversación."
    return True, ""

def check_new_chat_limit(user_id):
    convs_ref = db.collection('users').document(user_id).collection('conversations')
    count = 0
    for _ in convs_ref.stream():
        count += 1
    if count >= 3:
        return False
    return True

def get_all_conversation_summaries(user_id):
    convs_ref = db.collection('users').document(user_id).collection('conversations')
    summaries = []
    for doc in convs_ref.stream():
        data = doc.to_dict()
        summaries.append({
            'id': doc.id,
            'resumen': data.get('resumen', 'Chat sin título'),
            'fecha': data.get('fecha_inicio', 'N/A')
        })
    return summaries

def delete_conversation(user_id, conversation_id):
    conv_ref = db.collection('users').document(user_id).collection('conversations').document(conversation_id)
    conv_ref.delete()
    
def delete_all_conversations(user_id):
    convs_ref = db.collection('users').document(user_id).collection('conversations')
    docs = convs_ref.list_documents() 
    for doc in docs:
        doc.delete()

def add_summary_to_conversation(user_id, conversation_id, summary_text):
    conv_ref = db.collection('users').document(user_id).collection('conversations').document(conversation_id)
    conv_ref.update({
        'summary_history': firestore.ArrayUnion([summary_text])
    })

def get_summary_context(user_id, conversation_id):
    conv_ref = db.collection('users').document(user_id).collection('conversations').document(conversation_id)
    doc = conv_ref.get()
    if doc.exists:
        summaries = doc.to_dict().get('summary_history', [])
        return "\n".join(summaries)
    return ""

def update_conversation_title(user_id, conversation_id, new_title):
    conv_ref = db.collection('users').document(user_id).collection('conversations').document(conversation_id)
    conv_ref.update({
        'resumen': new_title
    })
    print(f"Título actualizado para chat {conversation_id}: {new_title}")

# ==========================================
# GESTIÓN DE FEEDBACK
# ==========================================

def save_feedback(user_id, feedback_data):
    user_hash = hash_user_id_securely(user_id)
    feedback_ref = db.collection('feedback').document(user_hash) 
    data_to_save = {
        'User_Hash': user_hash, 
        'Rating': feedback_data.get('rating'),
        'Respuestas_cualitativas': {
            'Interacción_agradable': feedback_data.get('pleasant_interaction'), 
            'motivacion_exploracion': feedback_data.get('motivated_exploration'),
            'comentarios_adicionales': feedback_data.get('comments') 
        },
        'Fecha_de_creación': datetime.now()
    }
    feedback_ref.set(data_to_save)
    return user_hash