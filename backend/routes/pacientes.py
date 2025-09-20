from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from backend.config.firebase_config import firebase_config
from datetime import datetime, date
from functools import wraps


# Crear Blueprint
pacientes_bp = Blueprint('pacientes', __name__)


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

def calcular_edad(fecha_nacimiento):
    """Calcular edad en años"""
    hoy = date.today()
    nacimiento = datetime.strptime(fecha_nacimiento, '%Y-%m-%d').date()
    edad = hoy.year - nacimiento.year
    if hoy.month < nacimiento.month or (hoy.month == nacimiento.month and hoy.day < nacimiento.day):
        edad -= 1
    return edad

@pacientes_bp.route("/pacientes")
@requiere_administrador

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

@pacientes_bp.route("/pacientes/nuevo", methods=['GET', 'POST'])
@requiere_administrador

def nuevo_paciente():
    """Crear nuevo paciente"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        nombre_paciente = request.form['nombre_paciente'].strip()
        fecha_nacimiento = request.form['fecha_nacimiento'].strip()
        nombre_apoderado = request.form['nombre_apoderado'].strip()
        telefono = request.form['telefono'].strip()
        email = request.form['email'].strip()
        
        if not all([nombre_paciente, fecha_nacimiento, nombre_apoderado]):
            flash('Campos marcados con * son obligatorios', 'error')
            return render_template('paciente_form.html')
        
        try:
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
            return redirect(url_for('pacientes.pacientes'))
            
        except Exception as e:
            flash(f'Error: {str(e)}', 'error')
    
    return render_template('paciente_form.html')

@pacientes_bp.route("/pacientes/<paciente_id>/editar", methods=['GET', 'POST'])
@requiere_administrador

def editar_paciente(paciente_id):
    """Editar paciente"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    db = firebase_config.get_db()
    
    try:
        doc_ref = db.collection('pacientes').document(paciente_id)
        doc = doc_ref.get()
        
        if not doc.exists:
            flash('Paciente no encontrado', 'error')
            return redirect(url_for('pacientes.pacientes'))
        
        paciente = doc.to_dict()
        paciente['id'] = paciente_id
        
        if request.method == 'POST':
            nombre_paciente = request.form['nombre_paciente'].strip()
            fecha_nacimiento = request.form['fecha_nacimiento'].strip()
            nombre_apoderado = request.form['nombre_apoderado'].strip()
            telefono = request.form['telefono'].strip()
            email = request.form['email'].strip()
            
            if not all([nombre_paciente, fecha_nacimiento, nombre_apoderado]):
                flash('Campos marcados con * son obligatorios', 'error')
                return render_template('paciente_edit_form.html', paciente=paciente)
            
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
            return redirect(url_for('pacientes.pacientes'))
        
        return render_template('paciente_edit_form.html', paciente=paciente)
        
    except Exception as e:
        flash(f'Error: {str(e)}', 'error')
        return redirect(url_for('pacientes.pacientes'))

@pacientes_bp.route("/pacientes/<paciente_id>/eliminar", methods=['POST'])
@requiere_administrador

def eliminar_paciente(paciente_id):
    """Eliminar paciente"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    try:
        db = firebase_config.get_db()
        doc_ref = db.collection('pacientes').document(paciente_id)
        
        doc = doc_ref.get()
        if not doc.exists:
            flash('Paciente no encontrado', 'error')
        else:
            doc_ref.delete()
            flash('Paciente eliminado correctamente', 'success')
    
    except Exception as e:
        flash(f'Error al eliminar: {str(e)}', 'error')
    
    return redirect(url_for('pacientes.pacientes'))