import os
from flask import Flask, render_template, request, redirect, url_for, session, flash
from dotenv import load_dotenv
from backend.config.firebase_config import firebase_config
from firebase_admin import auth
import requests
import json
from datetime import datetime, date



# Cargar variables de entorno
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "centro-paye-secret-2025")

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
    """Listar usuarios del sistema"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    try:
        db = firebase_config.get_db()
        usuarios_ref = db.collection('usuarios_sistema')
        usuarios = []
        
        for doc in usuarios_ref.stream():
            usuario_data = doc.to_dict()
            usuario_data['id'] = doc.id
            usuarios.append(usuario_data)
        
        return render_template('usuarios.html', usuarios=usuarios)
        
    except Exception as e:
        flash(f'Error: {str(e)}', 'error')
        return render_template('usuarios.html', usuarios=[])
    
@app.route("/usuarios/nuevo", methods=['GET', 'POST'])
def nuevo_usuario():
    """Crear nuevo usuario del sistema"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        # 4 campos 
        nombre = request.form['nombre'].strip()
        email = request.form['email'].strip()
        password = request.form['password'].strip()
        rol = request.form['rol'].strip()
        
        # Validación 
        if not all([nombre, email, password, rol]):
            flash('Todos los campos son obligatorios', 'error')
            return render_template('usuario_form.html')
        
        try:
            # Crear en Firebase Auth
            api_key = os.getenv('FIREBASE_WEB_API_KEY')
            url = f"https://identitytoolkit.googleapis.com/v1/accounts:signUp?key={api_key}"
            
            payload = {
                "email": email,
                "password": password,
                "returnSecureToken": True
            }
            
            response = requests.post(url, data=json.dumps(payload))
            result = response.json()
            
            if response.status_code == 200:
                # Guardar en Firestore
                db = firebase_config.get_db()
                usuario_data = {
                    'uid': result['localId'],
                    'nombre': nombre,
                    'email': email,
                    'rol': rol,
                    'estado': 'activo'
                }
                
                db.collection('usuarios_sistema').add(usuario_data)
                flash('Usuario creado correctamente', 'success')
                return redirect(url_for('usuarios'))
            else:
                flash('Error creando usuario', 'error')
                
        except Exception as e:
            flash(f'Error: {str(e)}', 'error')
    
    return render_template('usuario_form.html')


from datetime import datetime, date

def calcular_edad(fecha_nacimiento):
    """Calcular edad en años"""
    hoy = date.today()
    nacimiento = datetime.strptime(fecha_nacimiento, '%Y-%m-%d').date()
    edad = hoy.year - nacimiento.year
    if hoy.month < nacimiento.month or (hoy.month == nacimiento.month and hoy.day < nacimiento.day):
        edad -= 1
    return edad

@app.route("/pacientes")
def pacientes():
    """Listar pacientes"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    try:
        db = firebase_config.get_db()
        pacientes_ref = db.collection('pacientes')
        pacientes = []
        
        for doc in pacientes_ref.stream():
            paciente_data = doc.to_dict()
            paciente_data['id'] = doc.id
            
            # Calcular edad
            if 'fecha_nacimiento' in paciente_data:
                paciente_data['edad'] = calcular_edad(paciente_data['fecha_nacimiento'])
            
            pacientes.append(paciente_data)
        
        return render_template('pacientes.html', pacientes=pacientes)
        
    except Exception as e:
        flash(f'Error: {str(e)}', 'error')
        return render_template('pacientes.html', pacientes=[])

@app.route("/pacientes/nuevo", methods=['GET', 'POST'])
def nuevo_paciente():
    """Crear nuevo paciente"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        # Campos esenciales
        nombre_paciente = request.form['nombre_paciente'].strip()
        fecha_nacimiento = request.form['fecha_nacimiento'].strip()
        nombre_apoderado = request.form['nombre_apoderado'].strip()
        telefono = request.form['telefono'].strip()
        email = request.form['email'].strip()
        
        # Validación 
        if not all([nombre_paciente, fecha_nacimiento, nombre_apoderado,]):
            flash('Campos marcados con * son obligatorios', 'error')
            return render_template('paciente_form.html')
        
        try:
            # Guardar en Firestore
            db = firebase_config.get_db()
            paciente_data = {
                'nombre_paciente': nombre_paciente,
                'fecha_nacimiento': fecha_nacimiento,
                'nombre_apoderado': nombre_apoderado,
                'telefono': telefono,
                'email': email if email else '',
                'estado': 'activo',
                'fecha_registro': datetime.now().isoformat()
            }
            
            db.collection('pacientes').add(paciente_data)
            flash('Paciente registrado correctamente', 'success')
            return redirect(url_for('pacientes'))
            
        except Exception as e:
            flash(f'Error: {str(e)}', 'error')
    
    return render_template('paciente_form.html')


@app.route("/pacientes/<paciente_id>/editar", methods=['GET', 'POST'])
def editar_paciente(paciente_id):
    """Editar paciente - MINIMALISTA"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    db = firebase_config.get_db()
    
    try:
        # Obtener datos del paciente
        doc_ref = db.collection('pacientes').document(paciente_id)
        doc = doc_ref.get()
        
        if not doc.exists:
            flash('Paciente no encontrado', 'error')
            return redirect(url_for('pacientes'))
        
        paciente = doc.to_dict()
        paciente['id'] = paciente_id
        
        if request.method == 'POST':
            # Actualizar datos
            nombre_paciente = request.form['nombre_paciente'].strip()
            fecha_nacimiento = request.form['fecha_nacimiento'].strip()
            nombre_apoderado = request.form['nombre_apoderado'].strip()
            telefono = request.form['telefono'].strip()
            email = request.form['email'].strip()
            
            # Validación 
            if not all([nombre_paciente, fecha_nacimiento, nombre_apoderado, telefono]):
                flash('Campos marcados con * son obligatorios', 'error')
                return render_template('paciente_edit_form.html', paciente=paciente)
            
            # Actualizar en Firestore
            update_data = {
                'nombre_paciente': nombre_paciente,
                'fecha_nacimiento': fecha_nacimiento,
                'nombre_apoderado': nombre_apoderado,
                'telefono': telefono,
                'email': email if email else '',
                'fecha_modificacion': datetime.now().isoformat()
            }
            
            doc_ref.update(update_data)
            flash('Paciente actualizado correctamente', 'success')
            return redirect(url_for('pacientes'))
        
        return render_template('paciente_edit_form.html', paciente=paciente)
        
    except Exception as e:
        flash(f'Error: {str(e)}', 'error')
        return redirect(url_for('pacientes'))
    
    
@app.route("/pacientes/<paciente_id>/eliminar", methods=['POST'])
def eliminar_paciente(paciente_id):
    """Eliminar paciente - MINIMALISTA"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    try:
        db = firebase_config.get_db()
        doc_ref = db.collection('pacientes').document(paciente_id)
        
        # Verificar que existe
        doc = doc_ref.get()
        if not doc.exists:
            flash('Paciente no encontrado', 'error')
        else:
            # Eliminar
            doc_ref.delete()
            flash('Paciente eliminado correctamente', 'success')
    
    except Exception as e:
        flash(f'Error al eliminar: {str(e)}', 'error')
    
    return redirect(url_for('pacientes'))

if __name__ == "__main__":
    app.run(debug=True)