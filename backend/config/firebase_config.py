import firebase_admin
from firebase_admin import credentials, firestore, auth
import os
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

class FirebaseConfig:
    def __init__(self):
        self.db = None
        self.auth = None
        self.initialize()
    
    def initialize(self):
        """Inicializar Firebase Admin SDK"""
        if not firebase_admin._apps:
            try:
                cred_path = os.getenv('FIREBASE_CREDENTIALS_PATH')
                if not cred_path or not os.path.exists(cred_path):
                    raise FileNotFoundError("Archivo de credenciales Firebase no encontrado")
                
                cred = credentials.Certificate(cred_path)
                firebase_admin.initialize_app(cred)
                print("Firebase inicializado correctamente")
                
            except Exception as e:
                print(f"Error inicializando Firebase: {e}")
                return False
        
        self.db = firestore.client()
        self.auth = auth
        return True
    
    def get_db(self):
        """Obtener cliente de Firestore"""
        return self.db
    
    def get_auth(self):
        """Obtener cliente de Authentication"""
        return self.auth

# Instancia global
firebase_config = FirebaseConfig()