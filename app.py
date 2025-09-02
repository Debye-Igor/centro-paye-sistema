import os
from flask import Flask
from dotenv import load_dotenv
from backend.config.firebase_config import firebase_config

# Cargar variables de entorno desde .env
load_dotenv()

# Crear aplicación Flask
app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "fallback-secret")  # clave para sesiones

@app.route("/")
def home():
    return "Flask corriendo correctamente 🎉"

@app.route("/test-firebase")
def test_firebase():
    """Ruta de prueba para verificar conexión a Firestore"""
    db = firebase_config.get_db()
    try:
        doc_ref = db.collection("test").document("prueba")
        doc_ref.set({"mensaje": "Prueba de conexión - Hola Centro Paye 🚀"})
        return "✅ Documento creado en Firestore"
    except Exception as e:
        return f"❌ Error conectando a Firestore: {e}"

if __name__ == "__main__":
    # Iniciar servidor Flask
    app.run(debug=True)
