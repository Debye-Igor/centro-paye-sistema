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


# Cargar variables de entorno
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "centro-paye-secret-2025")

app.register_blueprint(usuarios_bp)
app.register_blueprint(pacientes_bp)
app.register_blueprint(servicios_bp)
app.register_blueprint(citas_bp)


# Configuración prroducción
if os.getenv('VERCEL_ENV') == 'production':
    app.config['SESSION_COOKIE_SECURE'] = True
    app.config['SESSION_COOKIE_HTTPONLY'] = True

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
    
@app.route("/reprogramaciones")
def reprogramaciones():
    """Ver citas pendientes de reprogramación - Simple"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    try:
        db = firebase_config.get_db()
        
        # Obtener solo citas pendientes de reprogramación
        citas_pendientes = db.collection('citas')\
                             .where('estado', '==', 'pendiente_reprogramacion')\
                             .stream()
        
        reprogramaciones = []
        
        for doc in citas_pendientes:
            cita = doc.to_dict()
            cita['id'] = doc.id
            
            try:
                # Obtener nombres (simple)
                paciente_doc = db.collection('pacientes').document(cita['paciente_id']).get()
                servicio_doc = db.collection('servicios').document(cita['servicio_id']).get()
                profesional_doc = db.collection('usuarios_sistema').document(cita['profesional_id']).get()
                
                reprogramaciones.append({
                    'id': cita['id'],
                    'paciente': paciente_doc.to_dict()['nombre_paciente'] if paciente_doc.exists else 'N/A',
                    'fecha_original': cita['fecha'],
                    'hora_original': cita['hora'],
                    'servicio': servicio_doc.to_dict()['nombre'] if servicio_doc.exists else 'N/A',
                    'profesional': profesional_doc.to_dict()['nombre'] if profesional_doc.exists else 'N/A'
                })
                
            except Exception as e:
                print(f"Error procesando: {e}")
                continue
        
        return render_template('reprogramaciones.html', reprogramaciones=reprogramaciones)
        
    except Exception as e:
        flash(f'Error: {str(e)}', 'error')
        return render_template('reprogramaciones.html', reprogramaciones=[])
    
    
# lÓGICA para reprogramar cita 
@app.route("/reprogramaciones/<cita_id>/nueva-fecha", methods=['GET', 'POST'])
def reprogramar_cita_form(cita_id):
    """Formulario para asignar nueva fecha a cita pendiente de reprogramación"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    db = firebase_config.get_db()
    
    try:
        # Obtener la cita pendiente de reprogramación
        cita_ref = db.collection('citas').document(cita_id)
        cita_doc = cita_ref.get()
        
        if not cita_doc.exists:
            flash('Cita no encontrada', 'error')
            return redirect(url_for('reprogramaciones'))
        
        cita_data = cita_doc.to_dict()
        
        # Verificar que esté en estado pendiente_reprogramacion
        if cita_data.get('estado') != 'pendiente_reprogramacion':
            flash('Esta cita no está pendiente de reprogramación', 'error')
            return redirect(url_for('reprogramaciones'))
        
        if request.method == 'POST':
            # Procesar la reprogramación
            nueva_fecha = request.form['nueva_fecha'].strip()
            nueva_hora = request.form['nueva_hora'].strip()
            profesional_id = request.form['profesional_id'].strip()
            observaciones = request.form['observaciones'].strip()
            
            # Validaciones
            if not all([nueva_fecha, nueva_hora, profesional_id]):
                flash('Todos los campos marcados con * son obligatorios', 'error')
                return redirect(request.url)
            
            # Verificar que no haya conflicto de horario
            conflicto = verificar_conflicto_horario(db, nueva_fecha, nueva_hora, profesional_id)
            if conflicto:
                flash('Ya existe una cita en ese horario para el profesional seleccionado', 'error')
                return redirect(request.url)
            
            # Crear la nueva cita
            nueva_cita_data = {
                'fecha': nueva_fecha,
                'hora': nueva_hora,
                'paciente_id': cita_data['paciente_id'],
                'servicio_id': cita_data['servicio_id'],
                'profesional_id': profesional_id,
                'estado': 'programada',
                'observaciones': f"Reprogramada desde {cita_data['fecha']} {cita_data['hora']}. {observaciones}",
                'cita_original_id': cita_id,
                'fecha_creacion': datetime.now().isoformat(),
                'reprogramado_por': session.get('user_id')
            }
            
            # Guardar nueva cita
            db.collection('citas').add(nueva_cita_data)
            
            # Actualizar cita original a estado "reprogramada"
            cita_ref.update({
                'estado': 'reprogramada',
                'fecha_reprogramacion_final': datetime.now().isoformat(),
                'nueva_fecha': nueva_fecha,
                'nueva_hora': nueva_hora
            })
            
            flash('Cita reprogramada exitosamente', 'success')
            return redirect(url_for('reprogramaciones'))
        
        # Mostrar formulario
        # Obtener datos para el formulario
        cita_original = obtener_datos_cita_para_form(db, cita_data)
        horarios_disponibles = generar_horarios()
        otros_profesionales = obtener_otros_profesionales(db, cita_data['profesional_id'])
        
        # Fecha mínima (hoy) y sugerida (mañana)
        fecha_minima = datetime.now().strftime('%Y-%m-%d')
        fecha_sugerida = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
        
        return render_template('reprogramar_form.html',
                             cita_original=cita_original,
                             horarios_disponibles=horarios_disponibles,
                             otros_profesionales=otros_profesionales,
                             fecha_minima=fecha_minima,
                             fecha_sugerida=fecha_sugerida)
    
    except Exception as e:
        flash(f'Error: {str(e)}', 'error')
        return redirect(url_for('reprogramaciones'))

def verificar_conflicto_horario(db, fecha, hora, profesional_id):
    """Verifica si ya existe una cita en el horario especificado"""
    try:
        citas_conflicto = db.collection('citas')\
                           .where('fecha', '==', fecha)\
                           .where('hora', '==', hora)\
                           .where('profesional_id', '==', profesional_id)\
                           .where('estado', '==', 'programada')\
                           .limit(1)\
                           .stream()
        
        return len(list(citas_conflicto)) > 0
    except:
        return False

def obtener_datos_cita_para_form(db, cita_data):
    """Obtiene datos completos de la cita para mostrar en el formulario"""
    try:
        # Obtener nombres completos
        paciente_doc = db.collection('pacientes').document(cita_data['paciente_id']).get()
        servicio_doc = db.collection('servicios').document(cita_data['servicio_id']).get()
        profesional_doc = db.collection('usuarios_sistema').document(cita_data['profesional_id']).get()
        
        return {
            'id': cita_data.get('id'),
            'paciente': paciente_doc.to_dict()['nombre_paciente'] if paciente_doc.exists else 'N/A',
            'fecha_original': cita_data['fecha'],
            'hora_original': cita_data['hora'],
            'servicio': servicio_doc.to_dict()['nombre'] if servicio_doc.exists else 'N/A',
            'profesional': profesional_doc.to_dict()['nombre'] if profesional_doc.exists else 'N/A',
            'profesional_id': cita_data['profesional_id']
        }
    except Exception as e:
        return {
            'id': cita_data.get('id'),
            'paciente': 'Error cargando datos',
            'fecha_original': cita_data.get('fecha', ''),
            'hora_original': cita_data.get('hora', ''),
            'servicio': 'Error',
            'profesional': 'Error',
            'profesional_id': cita_data.get('profesional_id', '')
        }

def obtener_otros_profesionales(db, profesional_actual_id):
    """Obtiene lista de otros profesionales disponibles"""
    try:
        profesionales = []
        for doc in db.collection('usuarios_sistema').where('rol', '==', 'profesional').stream():
            profesional_data = doc.to_dict()
            if doc.id != profesional_actual_id:  # Excluir el profesional actual
                profesionales.append({
                    'id': doc.id,
                    'nombre': profesional_data.get('nombre', 'Sin nombre')
                })
        return profesionales
    except:
        return []


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

