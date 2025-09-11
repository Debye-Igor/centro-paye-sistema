import os
from flask import Flask, render_template, request, redirect, url_for, session, flash
from dotenv import load_dotenv
from backend.config.firebase_config import firebase_config
from firebase_admin import auth
import requests
import json
from datetime import datetime, date,timedelta



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
        duracion = request.form['duracion'].strip()
        precio = request.form['precio'].strip()
        descripcion = request.form['descripcion'].strip()
        
        # Validación 
        if not all([nombre, duracion, precio]):
            flash('Campos marcados con * son obligatorios', 'error')
            return render_template('servicio_form.html')
        
        try:
            # Guardar en Firestore
            db = firebase_config.get_db()
            servicio_data = {
                'nombre': nombre,
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
    
    return render_template('servicio_form.html')

@app.route("/servicios/<servicio_id>/editar", methods=['GET', 'POST'])
def editar_servicio(servicio_id):
    """Editar servicio - MINIMALISTA"""
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
    """Eliminar servicio - MINIMALISTA"""
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

def generar_horarios():
    """Genera horarios de trabajo (9:00 a 18:00)"""
    horarios = []
    for hora in range(9, 19):  # 9:00 a 18:00
        horarios.append(f"{hora:02d}:00")
    return horarios



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

if __name__ == "__main__":
    app.run(debug=True)