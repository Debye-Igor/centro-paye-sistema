import os
from flask import Flask, render_template, request, redirect, url_for, session, flash
from dotenv import load_dotenv
from backend.config.firebase_config import firebase_config
from firebase_admin import auth
import requests
import json

# Cargar variables de entorno
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "centro-paye-secret-2024")

@app.route("/")
def home():
    """Página principal - redirige según el estado de login"""
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route("/login", methods=['GET', 'POST'])
def login():
    """Login con Firebase Auth REST API"""
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        
        try:
            # API Key de Firebase (la obtienes de Project Settings > General)
            api_key = os.getenv('FIREBASE_WEB_API_KEY')  
            
            # Endpoint de Firebase Auth REST API
            url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={api_key}"
            
            payload = {
                "email": email,
                "password": password,
                "returnSecureToken": True
            }
            
            response = requests.post(url, data=json.dumps(payload))
            result = response.json()
            
            if response.status_code == 200:
                # Login exitoso
                session['user_id'] = result['localId']
                session['user_email'] = result['email']
                session['id_token'] = result['idToken']
                session['user_role'] = "administrador"
                flash('Login exitoso', 'success')
                return redirect(url_for('dashboard'))
            else:
                # Error de autenticación
                error_message = result.get('error', {}).get('message', 'Credenciales incorrectas')
                flash(f'Error: {error_message}', 'error')
                
        except Exception as e:
            flash(f'Error al iniciar sesión: {str(e)}', 'error')
    
    return render_template('login.html')

@app.route("/dashboard")
def dashboard():
    """Dashboard principal - requiere login"""
    if 'user_id' not in session:
        flash('Debes iniciar sesión', 'error')
        return redirect(url_for('login'))
    
    return render_template('dashboard.html', user_email=session.get('user_email'))

@app.route("/logout")
def logout():
    """Cerrar sesión"""
    session.clear()
    flash('Sesión cerrada correctamente', 'info')
    return redirect(url_for('login'))

@app.route("/usuarios")
def usuarios():
    """Listar usuarios/pacientes"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    # Obtener usuarios de Firestore
    db = firebase_config.get_db()
    usuarios_ref = db.collection('usuarios')
    usuarios = []
    
    try:
        docs = usuarios_ref.stream()
        for doc in docs:
            usuario_data = doc.to_dict()
            usuario_data['id'] = doc.id
            usuarios.append(usuario_data)
    except Exception as e:
        flash(f'Error cargando usuarios: {str(e)}', 'error')
    
    return render_template('usuarios.html', usuarios=usuarios)

@app.route("/usuarios/nuevo", methods=['GET', 'POST'])
def nuevo_usuario():
    """Crear nuevo usuario/paciente"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        # Obtener datos del formulario
        nombre = request.form['nombre']
        rut = request.form['rut']
        email = request.form['email']
        telefono = request.form['telefono']
        fecha_nacimiento = request.form['fecha_nacimiento']
        apoderado = request.form['apoderado']
        
        # Validaciones básicas
        if not all([nombre, rut, email]):
            flash('Nombre, RUT y email son obligatorios', 'error')
            return render_template('usuario_form.html')
        
        # Guardar en Firestore
        db = firebase_config.get_db()
        try:
            usuario_data = {
                'nombre': nombre,
                'rut': rut,
                'email': email,
                'telefono': telefono,
                'fecha_nacimiento': fecha_nacimiento,
                'apoderado': apoderado,
                'estado': 'activo'
            }
            
            db.collection('usuarios').add(usuario_data)
            flash('Usuario creado exitosamente', 'success')
            return redirect(url_for('usuarios'))
            
        except Exception as e:
            flash(f'Error creando usuario: {str(e)}', 'error')
    
    return render_template('usuario_form.html')

if __name__ == "__main__":
    app.run(debug=True)