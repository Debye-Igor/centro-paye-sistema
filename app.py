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



# Cargar variables de entorno
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "centro-paye-secret-2025")

app.register_blueprint(usuarios_bp)
app.register_blueprint(pacientes_bp)



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
    

@app.route("/servicios")
def servicios():
    """Listar servicios"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    try:
        db = firebase_config.get_db()
        servicios_ref = db.collection('servicios')
        servicios = []
        
        for doc in servicios_ref.stream():
            servicio_data = doc.to_dict()
            servicio_data['id'] = doc.id
            
            # Obtener código de especialidad si existe
            if 'especialidad_id' in servicio_data:
                try:
                    esp_doc = db.collection('especialidades').document(servicio_data['especialidad_id']).get()
                    if esp_doc.exists:
                        servicio_data['especialidad_codigo'] = esp_doc.to_dict()['codigo']
                except:
                    servicio_data['especialidad_codigo'] = 'Error'
            
            servicios.append(servicio_data)
        
        return render_template('servicios.html', servicios=servicios)
        
    except Exception as e:
        flash(f'Error: {str(e)}', 'error')
        return render_template('servicios.html', servicios=[])

@app.route("/servicios/nuevo", methods=['GET', 'POST'])
def nuevo_servicio():
    """Crear nuevo servicio"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        # Campos 
        nombre = request.form['nombre'].strip()
        especialidad_id = request.form['especialidad_id'].strip() 
        duracion = request.form['duracion'].strip()
        precio = request.form['precio'].strip()
        descripcion = request.form['descripcion'].strip()
        
        # Validación 
        if not all([nombre, especialidad_id, duracion, precio]):  
            flash('Campos marcados con * son obligatorios', 'error')
            return render_template('servicio_form.html')
        
        try:
            # Guardar en Firestore
            db = firebase_config.get_db()
            servicio_data = {
                'nombre': nombre,
                'especialidad_id': especialidad_id,  
                'duracion': int(duracion),
                'precio': int(precio),
                'descripcion': descripcion if descripcion else '',
                'estado': 'activo',
                'fecha_creacion': datetime.now().isoformat()
            }
            
            db.collection('servicios').add(servicio_data)
            flash('Servicio creado correctamente', 'success')
            return redirect(url_for('servicios'))
            
        except Exception as e:
            flash(f'Error: {str(e)}', 'error')
    
    # Obtener especialidades para el dropdown
    try:
        db = firebase_config.get_db()
        especialidades = []
        for doc in db.collection('especialidades').stream():
            esp_data = doc.to_dict()
            esp_data['id'] = doc.id
            especialidades.append(esp_data)
        
        return render_template('servicio_form.html', especialidades=especialidades)
    except:
        return render_template('servicio_form.html', especialidades=[])

@app.route("/servicios/<servicio_id>/editar", methods=['GET', 'POST'])
def editar_servicio(servicio_id):
    """Editar servicio"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    db = firebase_config.get_db()
    
    try:
        # Obtener datos del servicio
        doc_ref = db.collection('servicios').document(servicio_id)
        doc = doc_ref.get()
        
        if not doc.exists:
            flash('Servicio no encontrado', 'error')
            return redirect(url_for('servicios'))
        
        servicio = doc.to_dict()
        servicio['id'] = servicio_id
        
        if request.method == 'POST':
            # Actualizar datos
            nombre = request.form['nombre'].strip()
            duracion = request.form['duracion'].strip()
            precio = request.form['precio'].strip()
            descripcion = request.form['descripcion'].strip()
            estado = request.form['estado'].strip()
            
            # Validación 
            if not all([nombre, duracion, precio]):
                flash('Campos marcados con * son obligatorios', 'error')
                return render_template('servicio_edit_form.html', servicio=servicio)
            
            # Actualizar en Firestore
            update_data = {
                'nombre': nombre,
                'duracion': int(duracion),
                'precio': int(precio),
                'descripcion': descripcion if descripcion else '',
                'estado': estado,
                'fecha_modificacion': datetime.now().isoformat()
            }
            
            doc_ref.update(update_data)
            flash('Servicio actualizado correctamente', 'success')
            return redirect(url_for('servicios'))
        
        return render_template('servicio_edit_form.html', servicio=servicio)
        
    except Exception as e:
        flash(f'Error: {str(e)}', 'error')
        return redirect(url_for('servicios'))

@app.route("/servicios/<servicio_id>/eliminar", methods=['POST'])
def eliminar_servicio(servicio_id):
    """Eliminar servicio """
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    try:
        db = firebase_config.get_db()
        doc_ref = db.collection('servicios').document(servicio_id)
        
        # Verificar que existe
        doc = doc_ref.get()
        if not doc.exists:
            flash('Servicio no encontrado', 'error')
        else:
            # Eliminar
            doc_ref.delete()
            flash('Servicio eliminado correctamente', 'success')
    
    except Exception as e:
        flash(f'Error al eliminar: {str(e)}', 'error')
    
    return redirect(url_for('servicios'))



# Calendariov 

def generar_semana_actual():
    """Genera los días de la semana actual (Lunes a dOMINGO)"""
    
    # Diccionario simple para días 
    dias_espanol = ['Lun', 'Mar', 'Mié', 'Jue', 'Vie',"Sab", "Dom"]
    
    hoy = datetime.now()
    inicio_semana = hoy - timedelta(days=hoy.weekday())  # Lunes
    
    dias_semana = []
    for i in range(7):  # Solo días laborables
        dia = inicio_semana + timedelta(days=i)
        
        dias_semana.append({
            'fecha': dia,
            'dia_nombre': f"{dias_espanol[i]} {dia.day}",  # "Lun 15", "Mar 16", etc.
            'fecha_str': dia.strftime('%Y-%m-%d')  # "2025-01-15"
        })
    
    return dias_semana

def obtener_mes_espanol(fecha):
    """Obtiene el nombre del mes en español"""
    meses = ['Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
             'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre']
    
    return meses[fecha.month - 1]  # -1 porque los meses van de 1-12, arrays de 0-11


@app.route("/calendario")
def calendario():
    """Vista del calendario semanal - CON MES EN ESPAÑOL"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    try:
        # Generar datos del calendario
        dias = generar_semana_actual()
        horarios = generar_horarios()
        
        # Obtener citas (por ahora vacío)
        fecha_inicio = dias[0]['fecha_str']
        fecha_fin = dias[-1]['fecha_str']
        citas = obtener_citas_semana(fecha_inicio, fecha_fin)
        
        # Agregar mes en español
        mes_espanol = obtener_mes_espanol(dias[0]['fecha'])
        
        return render_template('calendario.html', 
                             dias=dias, 
                             horarios=horarios, 
                             citas=citas,
                             mes_espanol=mes_espanol)  # <- Nuevo parámetro
    
    except Exception as e:
        flash(f'Error: {str(e)}', 'error')
        return redirect(url_for('dashboard'))


#Gestión de citas

@app.route("/citas/nueva", methods=['GET', 'POST'])
def nueva_cita():
    """Crear nueva cita - MINIMALISTA"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    # Obtener fecha y hora de los parámetros GET
    fecha = request.args.get('fecha') or request.form.get('fecha')
    hora = request.args.get('hora') or request.form.get('hora')
    
    if not fecha or not hora:
        flash('Fecha y hora son requeridas', 'error')
        return redirect(url_for('calendario'))
    
    if request.method == 'POST':
        # Obtener datos del formulario
        paciente_id = request.form['paciente_id'].strip()
        servicio_id = request.form['servicio_id'].strip()
        profesional_id = request.form['profesional_id'].strip()
        observaciones = request.form['observaciones'].strip()
        
        # Validación mínima
        if not all([paciente_id, servicio_id, profesional_id]):
            flash('Paciente, servicio y profesional son obligatorios', 'error')
            return render_template('cita_form.html', 
                                 fecha=fecha, hora=hora, 
                                 pacientes=[], servicios=[], profesionales=[])
        
        try:
            # Guardar cita en Firestore
            db = firebase_config.get_db()
            cita_data = {
                'fecha': fecha,
                'hora': hora,
                'paciente_id': paciente_id,
                'servicio_id': servicio_id,
                'profesional_id': profesional_id,
                'observaciones': observaciones if observaciones else '',
                'estado': 'programada',
                'fecha_creacion': datetime.now().isoformat(),
                'creado_por': session.get('user_id')
            }
            
            db.collection('citas').add(cita_data)
            flash('Cita agendada correctamente', 'success')
            return redirect(url_for('calendario'))
            
        except Exception as e:
            flash(f'Error: {str(e)}', 'error')
    
    # Obtener datos para los dropdowns
    try:
        db = firebase_config.get_db()
        
        # Obtener pacientes
        pacientes = []
        for doc in db.collection('pacientes').stream():
            paciente_data = doc.to_dict()
            paciente_data['id'] = doc.id
            pacientes.append(paciente_data)
        
        # Obtener servicios activos
        servicios = []
        for doc in db.collection('servicios').where('estado', '==', 'activo').stream():
            servicio_data = doc.to_dict()
            servicio_data['id'] = doc.id
            servicios.append(servicio_data)
        
        # Obtener profesionales (usuarios del sistema con rol profesional)
        profesionales = []
        for doc in db.collection('usuarios_sistema').where('rol', '==', 'profesional').stream():
            profesional_data = doc.to_dict()
            profesional_data['id'] = doc.id
            profesionales.append(profesional_data)
        
        return render_template('cita_form.html', 
                             fecha=fecha, hora=hora,
                             pacientes=pacientes, 
                             servicios=servicios, 
                             profesionales=profesionales)
    
    except Exception as e:
        flash(f'Error cargando datos: {str(e)}', 'error')
        return redirect(url_for('calendario'))


def obtener_citas_semana(fecha_inicio, fecha_fin):
    """Obtiene citas reales de Firestore para la semana"""
    try:
        db = firebase_config.get_db()
        citas_ref = db.collection('citas')
        
        # Obtener citas del rango de fechas
        citas = citas_ref.where('fecha', '>=', fecha_inicio)\
                         .where('fecha', '<=', fecha_fin)\
                         .stream()
        
        citas_dict = {}
        
        for doc in citas:
            cita_data = doc.to_dict()
            cita_data['id'] = doc.id
            
            #  Excluir tanto citas pendientes como reprogramadas
            if cita_data.get('estado') in ['pendiente_reprogramacion', 'reprogramada']:
                continue  
            
            # Obtener nombres de paciente, servicio y profesional
            try:
                # Obtener paciente
                paciente_doc = db.collection('pacientes').document(cita_data['paciente_id']).get()
                paciente_nombre = paciente_doc.to_dict()['nombre_paciente'] if paciente_doc.exists else 'Paciente'
                
                # Obtener servicio
                servicio_doc = db.collection('servicios').document(cita_data['servicio_id']).get()
                servicio_nombre = servicio_doc.to_dict()['nombre'] if servicio_doc.exists else 'Servicio'
                
                # Obtener profesional
                profesional_doc = db.collection('usuarios_sistema').document(cita_data['profesional_id']).get()
                profesional_nombre = profesional_doc.to_dict()['nombre'] if profesional_doc.exists else 'Profesional'
                
                # Crear clave para el diccionario (fecha_hora)
                cita_key = f"{cita_data['fecha']}_{cita_data['hora']}"
                
                # Agregar al diccionario
                citas_dict[cita_key] = {
                    'id': cita_data['id'],
                    'paciente': paciente_nombre,
                    'servicio': servicio_nombre,
                    'profesional': profesional_nombre,
                    'estado': cita_data.get('estado', 'programada'),
                    'observaciones': cita_data.get('observaciones', '')
                }
                
            except Exception as e:
                print(f"Error procesando cita {doc.id}: {e}")
                continue
        
        return citas_dict
        
    except Exception as e:
        print(f"Error obteniendo citas: {e}")
        return {}


@app.route("/citas/<cita_id>/reprogramar", methods=['POST'])
def reprogramar_cita(cita_id):
    """Marcar cita como pendiente de reprogramación"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    try:
        db = firebase_config.get_db()
        cita_ref = db.collection('citas').document(cita_id)
        
        # Verificar que la cita existe
        if not cita_ref.get().exists:
            flash('Cita no encontrada', 'error')
            return redirect(url_for('calendario'))
        
        # INNOVACIÓN: Cambiar estado para liberar horario
        cita_ref.update({
            'estado': 'pendiente_reprogramacion',
            'fecha_reprogramacion': datetime.now().isoformat()
        })
        
        flash('Cita marcada para reprogramar. Horario liberado.', 'success')
        return redirect(url_for('calendario'))
        
    except Exception as e:
        flash(f'Error: {str(e)}', 'error')
        return redirect(url_for('calendario'))


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
        
        # GET: Mostrar formulario
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

#Lógica para elimar cita

@app.route("/citas/<cita_id>/eliminar", methods=['POST'])
def eliminar_cita(cita_id):
    """Eliminar cita definitivamente"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    try:
        db = firebase_config.get_db()
        cita_ref = db.collection('citas').document(cita_id)
        
        # Verificar que la cita existe
        cita_doc = cita_ref.get()
        if not cita_doc.exists:
            flash('Cita no encontrada', 'error')
        else:
            # Eliminar la cita
            cita_ref.delete()
            flash('Cita eliminada correctamente', 'success')
    
    except Exception as e:
        flash(f'Error al eliminar: {str(e)}', 'error')
    
    return redirect(url_for('calendario'))


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

