from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from backend.config.firebase_config import firebase_config
from datetime import datetime, date, timedelta
from functools import wraps


citas_bp = Blueprint('citas', __name__)

def requiere_login(f):
    """Decorador básico para login"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def requiere_administrador(f):
    """Decorador para rutas de administrador"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        
        # Importar función de app.py
        from app import obtener_rol_usuario
        if obtener_rol_usuario() != 'administrador':
            flash('No tienes permisos para esta acción', 'error')
            return redirect(url_for('citas.calendario'))
        
        return f(*args, **kwargs)
    return decorated_function

def generar_semana_actual(fecha_inicio=None):
    """Generar los días de una semana específica o actual"""
    dias_espanol = ['Lun', 'Mar', 'Mié', 'Jue', 'Vie', "Sab", "Dom"]
    
    if fecha_inicio:
        # Usar fecha específica
        inicio_semana = datetime.strptime(fecha_inicio, '%Y-%m-%d')
        inicio_semana = inicio_semana - timedelta(days=inicio_semana.weekday())  # Lunes
    else:
        # Usar semana actual
        hoy = datetime.now()
        inicio_semana = hoy - timedelta(days=hoy.weekday())  # Lunes
    
    dias_semana = []
    for i in range(7):  
        dia = inicio_semana + timedelta(days=i)
        
        dias_semana.append({
            'fecha': dia,
            'dia_nombre': f"{dias_espanol[i]} {dia.day}",
            'fecha_str': dia.strftime('%Y-%m-%d')
        })
    
    return dias_semana

def obtener_mes_espanol(fecha):
    """Obtiene el nombre del mes en español"""
    meses = ['Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
             'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre']
    
    return meses[fecha.month - 1]

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

def obtener_citas_semana(fecha_inicio, fecha_fin):
    """Obtiene citas de Firestore para la semana"""
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
            
            # Excluir citas pendientes y reprogramadas
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

@citas_bp.route("/calendario")
@requiere_login
def calendario():
    """Vista del calendario semanal"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    try:
        # Obtener fecha desde parámetros URL
        fecha_inicio = request.args.get('fecha_inicio')
        
        # Generar datos del calendario
        dias = generar_semana_actual(fecha_inicio)
        horarios = generar_horarios()
        
        # Obtener citas
        fecha_inicio_str = dias[0]['fecha_str']
        fecha_fin_str = dias[-1]['fecha_str']
        citas = obtener_citas_semana(fecha_inicio_str, fecha_fin_str)
        
        # Calcular fechas para navegación
        lunes_actual = datetime.strptime(dias[0]['fecha_str'], '%Y-%m-%d')
        semana_anterior = (lunes_actual - timedelta(days=7)).strftime('%Y-%m-%d')
        semana_siguiente = (lunes_actual + timedelta(days=7)).strftime('%Y-%m-%d')
        
        # Agregar mes en español
        mes_espanol = obtener_mes_espanol(dias[0]['fecha'])
        
        return render_template('calendario.html', 
                             dias=dias, 
                             horarios=horarios, 
                             citas=citas,
                             mes_espanol=mes_espanol,
                             semana_anterior=semana_anterior,
                             semana_siguiente=semana_siguiente)
    
    except Exception as e:
        flash(f'Error: {str(e)}', 'error')
        return redirect(url_for('dashboard'))

@citas_bp.route("/citas/nueva", methods=['GET', 'POST'])
@requiere_login
def nueva_cita():
    """Crear nueva cita"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    # Obtener fecha y hora de los parámetros GET
    fecha = request.args.get('fecha') or request.form.get('fecha')
    hora = request.args.get('hora') or request.form.get('hora')
    
    if not fecha or not hora:
        flash('Fecha y hora son requeridas', 'error')
        return redirect(url_for('citas.calendario'))
    
    if request.method == 'POST':
        # Obtener datos del formulario
        paciente_id = request.form['paciente_id'].strip()
        servicio_id = request.form['servicio_id'].strip()
        profesional_id = request.form['profesional_id'].strip()
        observaciones = request.form['observaciones'].strip()
        
        # Validación 
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
            
            # Lógica para que a crear cita se mantenga en el mismo calendarios
            # Calcular el lunes de la semana de la cita creada
            
            fecha_cita = datetime.strptime(fecha, '%Y-%m-%d')
            lunes_semana = fecha_cita - timedelta(days=fecha_cita.weekday())
            fecha_inicio = lunes_semana.strftime('%Y-%m-%d')
            
            # Redirigir a la semana de la cita creada
            return redirect(url_for('citas.calendario', fecha_inicio=fecha_inicio))
            
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
        
        # Obtener profesionales
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
        return redirect(url_for('citas.calendario'))

@citas_bp.route("/citas/<cita_id>/reprogramar", methods=['POST'])
@requiere_login
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
            return redirect(url_for('citas.calendario'))
        
        # Obtener motivo del formulario
        motivo = request.form.get('motivo', '').strip()
        
        # Cambiar estado para liberar horario y guardars motivo
        cita_ref.update({
            'estado': 'pendiente_reprogramacion',
            'motivo_reprogramacion': motivo,
            'fecha_reprogramacion': datetime.now().isoformat()
        })
        
        flash('Cita marcada para reprogramar. Horario liberado.', 'success')
        return redirect(url_for('citas.calendario'))
        
    except Exception as e:
        flash(f'Error: {str(e)}', 'error')
        return redirect(url_for('citas.calendario'))
    
@citas_bp.route("/citas/<cita_id>/eliminar", methods=['POST'])
@requiere_login
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
    
    return redirect(url_for('citas.calendario'))