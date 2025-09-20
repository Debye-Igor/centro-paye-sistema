from flask import Blueprint, jsonify, request
from backend.config.firebase_config import firebase_config
from datetime import datetime

api_bp = Blueprint('api', __name__)

@api_bp.route("/api/citas", methods=['GET'])
def api_get_citas():
    """API: Obtener citas"""
    try:
        db = firebase_config.get_db()
        citas = []
        
        for doc in db.collection('citas').where('estado', '==', 'programada').stream():
            cita_data = doc.to_dict()
            cita_data['id'] = doc.id
            citas.append(cita_data)
        
        return jsonify({"citas": citas, "status": "success"})
    except Exception as e:
        return jsonify({"error": str(e), "status": "error"}), 400

@api_bp.route("/api/pacientes", methods=['GET'])
def api_get_pacientes():
    """API: Obtener pacientes"""
    try:
        db = firebase_config.get_db()
        pacientes = []
        
        for doc in db.collection('pacientes').stream():
            paciente_data = doc.to_dict()
            paciente_data['id'] = doc.id
            pacientes.append(paciente_data)
        
        return jsonify({"pacientes": pacientes, "status": "success"})
    except Exception as e:
        return jsonify({"error": str(e), "status": "error"}), 400

@api_bp.route("/api/citas", methods=['POST'])
def api_create_cita():
    """API: Crear nueva cita"""
    try:
        data = request.get_json()
        
        # Validación básica
        required_fields = ['fecha', 'hora', 'paciente_id', 'servicio_id', 'profesional_id']
        if not all(field in data for field in required_fields):
            return jsonify({"error": "Campos requeridos faltantes", "status": "error"}), 400
        
        db = firebase_config.get_db()
        cita_data = {
            'fecha': data['fecha'],
            'hora': data['hora'],
            'paciente_id': data['paciente_id'],
            'servicio_id': data['servicio_id'],
            'profesional_id': data['profesional_id'],
            'observaciones': data.get('observaciones', ''),
            'estado': 'programada',
            'fecha_creacion': datetime.now().isoformat()
        }
        
        doc_ref = db.collection('citas').add(cita_data)
        cita_data['id'] = doc_ref[1].id
        
        return jsonify({"cita": cita_data, "status": "success"}), 201
    except Exception as e:
        return jsonify({"error": str(e), "status": "error"}), 400

@api_bp.route("/api/citas/<cita_id>/reprogramar", methods=['PUT'])
def api_reprogramar_cita(cita_id):
    """API: Funcionalidad innovadora - Reprogramar cita"""
    try:
        data = request.get_json()
        motivo = data.get('motivo', 'Sin motivo especificado')
        
        db = firebase_config.get_db()
        cita_ref = db.collection('citas').document(cita_id)
        
        if not cita_ref.get().exists:
            return jsonify({"error": "Cita no encontrada", "status": "error"}), 404
        
        # Cambiar estado 
        cita_ref.update({
            'estado': 'pendiente_reprogramacion',
            'motivo_reprogramacion': motivo,
            'fecha_reprogramacion': datetime.now().isoformat()
        })
        
        return jsonify({
            "message": "Cita marcada para reprogramar. Horario liberado.", 
            "status": "success"
        })
    except Exception as e:
        return jsonify({"error": str(e), "status": "error"}), 400