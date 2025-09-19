from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from backend.config.firebase_config import firebase_config
from datetime import datetime
from functools import wraps

# Blueprint
servicios_bp = Blueprint('servicios', __name__)

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

@servicios_bp.route("/servicios")
@requiere_administrador
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
            
            # Obtener código de especialidad
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

@servicios_bp.route("/servicios/nuevo", methods=['GET', 'POST'])
@requiere_administrador
def nuevo_servicio():
    """Crear nuevo servicio"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        nombre = request.form['nombre'].strip()
        especialidad_id = request.form.get('especialidad_id', '').strip()
        duracion = request.form['duracion'].strip()
        precio = request.form['precio'].strip()
        descripcion = request.form['descripcion'].strip()
        
        if not all([nombre, especialidad_id, duracion, precio]):
            flash('Campos marcados con * son obligatorios', 'error')
            especialidades = cargar_especialidades()
            return render_template('servicio_form.html', especialidades=especialidades)
        
        try:
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
            return redirect(url_for('servicios.servicios'))
            
        except Exception as e:
            flash(f'Error: {str(e)}', 'error')
    
    especialidades = cargar_especialidades()
    return render_template('servicio_form.html', especialidades=especialidades)

@servicios_bp.route("/servicios/<servicio_id>/editar", methods=['GET', 'POST'])
@requiere_administrador
def editar_servicio(servicio_id):
    """Editar servicio"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    db = firebase_config.get_db()
    
    try:
        doc_ref = db.collection('servicios').document(servicio_id)
        doc = doc_ref.get()
        
        if not doc.exists:
            flash('Servicio no encontrado', 'error')
            return redirect(url_for('servicios.servicios'))
        
        servicio = doc.to_dict()
        servicio['id'] = servicio_id
        
        if request.method == 'POST':
            nombre = request.form['nombre'].strip()
            especialidad_id = request.form.get('especialidad_id', '').strip()
            duracion = request.form['duracion'].strip()
            precio = request.form['precio'].strip()
            descripcion = request.form['descripcion'].strip()
            estado = request.form['estado'].strip()
            
            if not all([nombre, especialidad_id, duracion, precio]):
                flash('Campos marcados con * son obligatorios', 'error')
                especialidades = cargar_especialidades()
                return render_template('servicio_edit_form.html', servicio=servicio, especialidades=especialidades)
            
            update_data = {
                'nombre': nombre,
                'especialidad_id': especialidad_id,
                'duracion': int(duracion),
                'precio': int(precio),
                'descripcion': descripcion if descripcion else '',
                'estado': estado,
                'fecha_modificacion': datetime.now().isoformat()
            }
            
            doc_ref.update(update_data)
            flash('Servicio actualizado correctamente', 'success')
            return redirect(url_for('servicios.servicios'))
        
        especialidades = cargar_especialidades()
        return render_template('servicio_edit_form.html', servicio=servicio, especialidades=especialidades)
        
    except Exception as e:
        flash(f'Error: {str(e)}', 'error')
        return redirect(url_for('servicios.servicios'))

@servicios_bp.route("/servicios/<servicio_id>/eliminar", methods=['POST'])
@requiere_administrador
def eliminar_servicio(servicio_id):
    """Eliminar servicio"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    try:
        db = firebase_config.get_db()
        doc_ref = db.collection('servicios').document(servicio_id)
        
        doc = doc_ref.get()
        if not doc.exists:
            flash('Servicio no encontrado', 'error')
        else:
            doc_ref.delete()
            flash('Servicio eliminado correctamente', 'success')
    
    except Exception as e:
        flash(f'Error al eliminar: {str(e)}', 'error')
    
    return redirect(url_for('servicios.servicios'))

def cargar_especialidades():
    """Función para cargar especialidades"""
    try:
        db = firebase_config.get_db()
        especialidades = []
        for doc in db.collection('especialidades').stream():
            esp_data = doc.to_dict()
            esp_data['id'] = doc.id
            especialidades.append(esp_data)
        return especialidades
    except Exception as e:
        print(f"Error cargando especialidades: {e}")
        return []