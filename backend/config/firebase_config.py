import firebase_admin
from firebase_admin import credentials, firestore, auth
import os
import json
from dotenv import load_dotenv

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
                # Verificar si estamos en Vercel (producción)
                if os.getenv('VERCEL_ENV'):
                    # En Vercel, usar variables de entorno para las credenciales
                    firebase_credentials = {
                        "type": os.getenv('FIREBASE_TYPE', 'service_account'),
                        "project_id": os.getenv('FIREBASE_PROJECT_ID'),
                        "private_key_id": os.getenv('FIREBASE_PRIVATE_KEY_ID'),
                        "private_key": os.getenv('FIREBASE_PRIVATE_KEY', '').replace('\\n', '\n'),
                        "client_email": os.getenv('FIREBASE_CLIENT_EMAIL'),
                        "client_id": os.getenv('FIREBASE_CLIENT_ID'),
                        "auth_uri": os.getenv('FIREBASE_AUTH_URI', 'https://accounts.google.com/o/oauth2/auth'),
                        "token_uri": os.getenv('FIREBASE_TOKEN_URI', 'https://oauth2.googleapis.com/token'),
                        "auth_provider_x509_cert_url": os.getenv('FIREBASE_AUTH_PROVIDER_CERT_URL', 'https://www.googleapis.com/oauth2/v1/certs'),
                        "client_x509_cert_url": os.getenv('FIREBASE_CLIENT_CERT_URL')
                    }
                    
                    # Validar que las credenciales estén completas
                    if not all([firebase_credentials['project_id'], 
                              firebase_credentials['private_key'], 
                              firebase_credentials['client_email']]):
                        raise ValueError("Credenciales Firebase incompletas en variables de entorno")
                    
                    cred = credentials.Certificate(firebase_credentials)
                    firebase_admin.initialize_app(cred)
                    print("Firebase inicializado con variables de entorno (Vercel)")
                
                else:
                    # Desarrollo local: usar archivo JSON
                    cred_path = os.getenv('FIREBASE_CREDENTIALS_PATH')
                    if not cred_path or not os.path.exists(cred_path):
                        raise FileNotFoundError("Archivo de credenciales Firebase no encontrado")
                    
                    cred = credentials.Certificate(cred_path)
                    firebase_admin.initialize_app(cred)
                    print("Firebase inicializado con archivo JSON (local)")
                
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
    
    def verify_token(self, id_token):
        """Verificar token de Firebase Auth"""
        try:
            decoded_token = auth.verify_id_token(id_token)
            return decoded_token
        except Exception as e:
            print(f"Error verificando token: {e}")
            return None

# Instancia global
firebase_config = FirebaseConfig()