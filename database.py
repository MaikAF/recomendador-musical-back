import firebase_admin
from firebase_admin import credentials, firestore
import os

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