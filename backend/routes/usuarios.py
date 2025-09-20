from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from backend.config.firebase_config import firebase_config
from datetime import datetime
import requests
import json
import os

from functools import wraps


# Crear Blueprint
usuarios_bp = Blueprint('usuarios', __name__)

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


def requiere_login(f):
    """Decorador básico para login"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@usuarios_bp.route("/usuarios")
@requiere_administrador

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
            
            # Obtener nombre de especialidad si existe
            if 'especialidad_id' in usuario_data:
                try:
                    esp_doc = db.collection('especialidades').document(usuario_data['especialidad_id']).get()
                    if esp_doc.exists:
                        usuario_data['especialidad_nombre'] = esp_doc.to_dict()['codigo']
                except:
                    usuario_data['especialidad_nombre'] = 'Error'
            
            usuarios.append(usuario_data)
        
        return render_template('usuarios.html', usuarios=usuarios)
        
    except Exception as e:
        flash(f'Error: {str(e)}', 'error')
        return render_template('usuarios.html', usuarios=[])


@usuarios_bp.route("/usuarios/nuevo", methods=['GET', 'POST'])
@requiere_administrador
def nuevo_usuario():
    """Crear nuevo usuario del sistema"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    # Cargar especialidades SIEMPRE (para usar en errores también)
    try:
        db = firebase_config.get_db()
        especialidades = []
        for doc in db.collection('especialidades').where('estado', '==', 'activa').stream():
            esp_data = doc.to_dict()
            esp_data['id'] = doc.id
            especialidades.append(esp_data)
    except:
        especialidades = []
    
    if request.method == 'POST':
        nombre = request.form['nombre'].strip()
        email = request.form['email'].strip()
        password = request.form['password'].strip()
        rol = request.form['rol'].strip()
        especialidad_id = request.form.get('especialidad_id', '').strip()
        
        # Validación - AHORA CON especialidades
        if not all([nombre, email, password, rol]):
            flash('Todos los campos son obligatorios', 'error')
            return render_template('usuario_form.html', especialidades=especialidades)
        
        # Si es profesional, especialidad es obligatoria - AHORA CON especialidades
        if rol == 'profesional' and not especialidad_id:
            flash('Especialidad es obligatoria para profesionales', 'error')
            return render_template('usuario_form.html', especialidades=especialidades)
        
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
                
                # Agregar especialidad si es profesional
                if rol == 'profesional' and especialidad_id:
                    usuario_data['especialidad_id'] = especialidad_id
                
                db.collection('usuarios_sistema').add(usuario_data)
                flash('Usuario creado correctamente', 'success')
                return redirect(url_for('usuarios.usuarios'))
            else:
                flash('Error creando usuario en Firebase', 'error')
                return render_template('usuario_form.html', especialidades=especialidades)
                
        except Exception as e:
            flash(f'Error: {str(e)}', 'error')
            return render_template('usuario_form.html', especialidades=especialidades)
    
    # GET: Mostrar formulario
    return render_template('usuario_form.html', especialidades=especialidades)