import os
from flask import Flask, render_template, request, redirect, url_for, session, flash
from dotenv import load_dotenv
from backend.config.firebase_config import firebase_config
from firebase_admin import auth
import requests
import json
from datetime import datetime, date,timedelta
from backend.routes.usuarios import usuarios_bp
from backend.routes.pacientes import pacientes_bp
from backend.routes.servicios import servicios_bp
from backend.routes.citas import citas_bp
from backend.routes.reprogramaciones import reprogramaciones_bp

from functools import wraps



# Cargar variables de entorno
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "centro-paye-secret-2025")

app.register_blueprint(usuarios_bp)
app.register_blueprint(pacientes_bp)
app.register_blueprint(servicios_bp)
app.register_blueprint(citas_bp)
app.register_blueprint(reprogramaciones_bp)


# Configuración prroducción
if os.getenv('VERCEL_ENV') == 'production':
    app.config['SESSION_COOKIE_SECURE'] = True
    app.config['SESSION_COOKIE_HTTPONLY'] = True
    
    
def obtener_rol_usuario():
    """Obtiene el rol del usuario actual"""
    if 'user_id' not in session:
        return None
    
    try:
        db = firebase_config.get_db()
        # Buscar usuario por UID de Firebase
        usuarios_ref = db.collection('usuarios_sistema')
        usuarios = usuarios_ref.where('uid', '==', session['user_id']).limit(1).stream()
        
        for doc in usuarios:
            usuario_data = doc.to_dict()
            return usuario_data.get('rol', 'profesional')  # Default profesional
        
        return 'profesional' 
    except:
        return 'profesional'
    
    
def requiere_administrador(f):
    """Decorador para rutas que requieren rol administrador"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        
        rol_actual = obtener_rol_usuario()
        if rol_actual != 'administrador':
            flash('No tienes permisos para acceder a esta sección', 'error')
            return redirect(url_for('citas.calendario'))
        
        return f(*args, **kwargs)
    return decorated_function

def requiere_login(f):
    """Decorador básico para rutas que requieren estar logueado"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def requiere_rol(rol_requerido):
    """Decorador para verificar roles específicos"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user_id' not in session:
                return redirect(url_for('login'))
            
            rol_actual = obtener_rol_usuario()
            
            if rol_requerido == 'administrador' and rol_actual != 'administrador':
                flash('No tienes permisos para acceder a esta sección', 'error')
                return redirect(url_for('citas.calendario'))
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

@app.context_processor
def inject_user_role():
    """agrega el rol del usuario en todos los templates"""
    return {
        'user_role': obtener_rol_usuario() if 'user_id' in session else None
    }

@app.route("/")
def home():
    """Página principal, redirige según el estado de login"""
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
            # API Key de Firebase
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
      
      
#Horairos

def inicializar_horarios():
    """Crear configuración básica de horarios del centro"""
    try:
        db = firebase_config.get_db()
        horarios_ref = db.collection('horarios')
        
        # Verificar si ya existe configuración
        existing = horarios_ref.document('configuracion_centro').get()
        if existing.exists:
            return
        
        # Crear configuración por defecto
        config_data = {
            "hora_inicio": "09:00",
            "hora_termino": "18:00", 
            "activo": True,
            "fecha_creacion": datetime.now().isoformat()
        }
        
        horarios_ref.document('configuracion_centro').set(config_data)
        print("Configuración de horarios inicializada")
        
    except Exception as e:
        print(f"Error inicializando horarios: {e}")

def generar_horarios():
    """Genera horarios basados en configuración del centro"""
    try:
        db = firebase_config.get_db()
        config_doc = db.collection('horarios').document('configuracion_centro').get()
        
        if config_doc.exists:
            config = config_doc.to_dict()
            hora_inicio = int(config['hora_inicio'].split(':')[0])
            hora_termino = int(config['hora_termino'].split(':')[0])
        else:
            hora_inicio, hora_termino = 9, 18
        
        horarios = []
        for hora in range(hora_inicio, hora_termino + 1):
            horarios.append(f"{hora:02d}:00")
        
        return horarios
        
    except Exception as e:
        print(f"Error obteniendo configuración: {e}")
        return ["09:00", "10:00", "11:00", "12:00", "13:00", "14:00", "15:00", "16:00", "17:00", "18:00"]

@app.route("/horarios", methods=['GET', 'POST'])
@requiere_administrador 
def horarios():
    """Configurar horarios del centro"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        hora_inicio = request.form['hora_inicio']
        hora_termino = request.form['hora_termino']
        
        try:
            db = firebase_config.get_db()
            # ccolección horarios
            config_ref = db.collection('horarios').document('configuracion_centro')
            
            # Usar set() con merge=True para crear o actualizar
            config_ref.set({
                'hora_inicio': hora_inicio,
                'hora_termino': hora_termino,
                'activo': True,
                'fecha_modificacion': datetime.now().isoformat()
            }, merge=True)
            
            flash('Horarios actualizados correctamente', 'horarios_success')
            return redirect(url_for('horarios'))

            # flash('Horarios actualizados correctamente', 'success')
            
        except Exception as e:
            flash(f'Error: {str(e)}', 'error')
    
    # Obtener configuración actual
    try:
        db = firebase_config.get_db()
        config_doc = db.collection('horarios').document('configuracion_centro').get()
        
        if config_doc.exists:
            configuracion = config_doc.to_dict()
        else:
            # Inicializar si no existe
            configuracion = {"hora_inicio": "09:00", "hora_termino": "18:00"}
            db.collection('horarios').document('configuracion_centro').set(configuracion)
        
        return render_template('horarios.html', configuracion=configuracion)
        
    except Exception as e:
        flash(f'Error: {str(e)}', 'error')
        return render_template('horarios.html', configuracion={"hora_inicio": "09:00", "hora_termino": "18:00"})

# especialidaes

def inicializar_especialidades():
    """Crear especialidades básicas del centro"""
    try:
        db = firebase_config.get_db()
        especialidades_ref = db.collection('especialidades')
        
        # Verificar si ya existen
        existing = list(especialidades_ref.limit(1).stream())
        if existing:
            return
        
        # Crear especialidades básicas
        especialidades_default = [
            {
                "nombre": "Fonoaudiología Infantil",
                "descripcion": "Terapia del habla y lenguaje para niños",
                "codigo": "FLGA",
                "estado": "activa"
            },
            {
                "nombre": "Terapia Ocupacional", 
                "descripcion": "Desarrollo de habilidades funcionales y sensoriales",
                "codigo": "TO",
                "estado": "activa"
            },
            {
                "nombre": "Psicología Infantil",
                "descripcion": "Apoyo psicológico y emocional para niños", 
                "codigo": "PSI",
                "estado": "activa"
            },
           
        ]
        
        for especialidad in especialidades_default:
            especialidades_ref.add(especialidad)
        
        print("Especialidades inicializadas")
        
    except Exception as e:
        print(f"Error inicializando especialidades: {e}")

@app.route("/especialidades")
@requiere_administrador 
def especialidades():
    """Listar especialidades - SIMPLE"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    try:
        db = firebase_config.get_db()
        especialidades = []
        
        for doc in db.collection('especialidades').stream():
            especialidad_data = doc.to_dict()
            especialidad_data['id'] = doc.id
            especialidades.append(especialidad_data)
        
        return render_template('especialidades.html', especialidades=especialidades)
        
    except Exception as e:
        flash(f'Error: {str(e)}', 'error')
        return render_template('especialidades.html', especialidades=[])
    

# Inicializar datos base
inicializar_horarios()
inicializar_especialidades()

if __name__ == "__main__":
    
    app.run(debug=os.getenv('FLASK_ENV') != 'production')
    
app = app

