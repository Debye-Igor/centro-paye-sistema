from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from backend.config.firebase_config import firebase_config
from datetime import datetime, timedelta
from functools import wraps

# Blueprint
reprogramaciones_bp = Blueprint('reprogramaciones', __name__)

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

@reprogramaciones_bp.route("/reprogramaciones")
@requiere_administrador
def reprogramaciones():
    """Ver citas pendientes de reprogramación"""
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
                # Obtener nombres
                paciente_doc = db.collection('pacientes').document(cita['paciente_id']).get()
                servicio_doc = db.collection('servicios').document(cita['servicio_id']).get()
                profesional_doc = db.collection('usuarios_sistema').document(cita['profesional_id']).get()
                
                reprogramaciones.append({
                    'id': cita['id'],
                    'paciente': paciente_doc.to_dict()['nombre_paciente'] if paciente_doc.exists else 'N/A',
                    'fecha_original': cita['fecha'],
                    'hora_original': cita['hora'],
                    'servicio': servicio_doc.to_dict()['nombre'] if servicio_doc.exists else 'N/A',
                    'profesional': profesional_doc.to_dict()['nombre'] if profesional_doc.exists else 'N/A',
                    'motivo': cita.get('motivo_reprogramacion', 'Sin motivo especificado')
                })
                
            except Exception as e:
                continue
        
        return render_template('reprogramaciones.html', reprogramaciones=reprogramaciones)
        
    except Exception as e:
        flash(f'Error: {str(e)}', 'error')
        return render_template('reprogramaciones.html', reprogramaciones=[])

@reprogramaciones_bp.route("/reprogramaciones/<cita_id>/reprogramar", methods=['GET', 'POST'])
@requiere_administrador
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
            return redirect(url_for('reprogramaciones.reprogramaciones'))
        
        cita_data = cita_doc.to_dict()
        
        # Verificar que esté en estado pendiente_reprogramacion
        if cita_data.get('estado') != 'pendiente_reprogramacion':
            flash('Esta cita no está pendiente de reprogramación', 'error')
            return redirect(url_for('reprogramaciones.reprogramaciones'))
        
        if request.method == 'POST':
            # rreprogramación
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
            return redirect(url_for('reprogramaciones.reprogramaciones'))
        
        # Mostrar formulario
        # Obtener datos para el formulario
        cita_original = obtener_datos_cita_para_form(db, cita_data)
        
        #
        horarios_disponibles = obtener_horarios_disponibles(db, fecha_sugerida, cita_data['profesional_id'])
        otros_profesionales = obtener_otros_profesionales(db, cita_data['profesional_id'])
        
        # Fecha mínima hoy y sugerida mañana
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
        return redirect(url_for('reprogramaciones.reprogramaciones'))

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
        return ["09:00", "10:00", "11:00", "12:00", "13:00", "14:00", "15:00", "16:00", "17:00", "18:00"]
    
    
def obtener_horarios_disponibles(db, fecha, profesional_id):
    """Obtiene horarios disponibles para una fecha y profesional específicos"""
    try:
        # Generar todos los horarios posibles
        todos_horarios = generar_horarios()
        
        # Consultar citas existentes para esa fecha y profesional
        citas_ocupadas = db.collection('citas')\
                          .where('fecha', '==', fecha)\
                          .where('profesional_id', '==', profesional_id)\
                          .where('estado', '==', 'programada')\
                          .stream()
        
        # Extraer horarios ocupados
        horarios_ocupados = set()
        for cita in citas_ocupadas:
            cita_data = cita.to_dict()
            horarios_ocupados.add(cita_data['hora'])
        
        # Filltrar horarios disponibles
        horarios_disponibles = [hora for hora in todos_horarios if hora not in horarios_ocupados]
        
        return horarios_disponibles
        
    except Exception as e:
        print(f"Error obteniendo horarios disponibles: {e}")
        return generar_horarios()