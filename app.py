from flask import Flask, jsonify, render_template, request
import psycopg2
from psycopg2 import pool
import bcrypt
from datetime import datetime
import os
from dotenv import load_dotenv
app = Flask(__name__)


# Cargar variables de entorno
load_dotenv()

DB_CONFIG = {
    'host': os.getenv('DB_HOST'),
    'port': int(os.getenv('DB_PORT', 5432)),  # valor por defecto si no existe
    'database': os.getenv('DB_NAME'),
    'user': os.getenv('DB_USER'),
    'password': os.getenv('DB_PASSWORD')
}

# Pool de conexiones para mejor rendimiento
connection_pool = None

def init_db_pool():
    """Inicializar el pool de conexiones"""
    global connection_pool
    try:
        print("[DEBUG] Iniciando pool de conexiones...")
        connection_pool = psycopg2.pool.SimpleConnectionPool(
            1,  # Mínimo de conexiones
            10,  # Máximo de conexiones
            **DB_CONFIG
        )
        print("[DEBUG] ✅ Pool de conexiones creado exitosamente")
        return True
    except Exception as e:
        print(f"[ERROR] ❌ Error al crear pool de conexiones: {e}")
        return False

# 🔥 ESTO ES LO IMPORTANTE: Inicializar el pool al cargar el módulo
if connection_pool is None:
    init_db_pool()
    
def get_db_connection():
    """Obtener una conexión del pool"""
    try:
        print("[DEBUG] Obteniendo conexión del pool...")
        conn = connection_pool.getconn()
        print("[DEBUG] ✅ Conexión obtenida")
        return conn
    except Exception as e:
        print(f"[ERROR] ❌ Error al obtener conexión: {e}")
        return None


def release_db_connection(conn):
    """Liberar conexión al pool"""
    try:
        print("[DEBUG] Liberando conexión al pool...")
        connection_pool.putconn(conn)
        print("[DEBUG] ✅ Conexión liberada")
    except Exception as e:
        print(f"[ERROR] ❌ Error al liberar conexión: {e}")


@app.route('/register_user', methods=['POST'])
def register_user():
    """Endpoint para registrar un nuevo usuario"""
    print("\n" + "="*50)
    print("[DEBUG] 📝 Iniciando registro de usuario")
    print(f"[DEBUG] Timestamp: {datetime.now()}")
    
    try:
        # Obtener datos del request
        data = request.get_json()
        print(f"[DEBUG] Datos recibidos: {data}")
        
        usr_name = data.get('name')
        usr_email = data.get('email')
        usr_password = data.get('password')
        
        # Validar campos
        if not usr_name or not usr_email or not usr_password:
            print("[ERROR] ❌ Campos incompletos")
            return jsonify({
                'success': False,
                'message': 'Todos los campos son requeridos'
            }), 400
        
        print(f"[DEBUG] Nombre: {usr_name}")
        print(f"[DEBUG] Email: {usr_email}")
        print(f"[DEBUG] Password length: {len(usr_password)}")
        
        # Hash de la contraseña
        print("[DEBUG] Hasheando contraseña...")
        hashed_password = bcrypt.hashpw(
            usr_password.encode('utf-8'), 
            bcrypt.gensalt()
        ).decode('utf-8')
        print("[DEBUG] ✅ Contraseña hasheada")
        
        # Obtener conexión
        conn = get_db_connection()
        if not conn:
            return jsonify({
                'success': False,
                'message': 'Error de conexión a la base de datos'
            }), 500
        
        cursor = conn.cursor()
        
        # Verificar si el email ya existe
        print("[DEBUG] Verificando si el email existe...")
        cursor.execute(
            "SELECT usr_email FROM usr_mstr WHERE usr_email = %s",
            (usr_email,)
        )
        existing_user = cursor.fetchone()
        
        if existing_user:
            print("[ERROR] ❌ Email ya registrado")
            cursor.close()
            release_db_connection(conn)
            return jsonify({
                'success': False,
                'message': 'El email ya está registrado'
            }), 409
        
        print("[DEBUG] ✅ Email disponible")
        
        # Insertar nuevo usuario
        print("[DEBUG] Insertando usuario en la base de datos...")
        cursor.execute(
            """
            INSERT INTO usr_mstr (usr_name, usr_email, usr_password)
            VALUES (%s, %s, %s)
            RETURNING usr_index
            """,
            (usr_name, usr_email, hashed_password)
        )
        
        usr_index = cursor.fetchone()[0]
        conn.commit()
        print(f"[DEBUG] ✅ Usuario insertado con ID: {usr_index}")
        
        # Cerrar cursor y liberar conexión
        cursor.close()
        release_db_connection(conn)
        
        print("[DEBUG] 🎉 Registro completado exitosamente")
        print("="*50 + "\n")
        
        return jsonify({
            'success': True,
            'message': 'Usuario registrado exitosamente',
            'data': {
                'usr_index': usr_index,
                'usr_name': usr_name,
                'usr_email': usr_email
            }
        }), 201
        
    except psycopg2.IntegrityError as e:
        print(f"[ERROR] ❌ Error de integridad: {e}")
        if conn:
            conn.rollback()
            release_db_connection(conn)
        return jsonify({
            'success': False,
            'message': 'Error: El email ya está registrado'
        }), 409
        
    except Exception as e:
        print(f"[ERROR] ❌ Error inesperado: {e}")
        if conn:
            conn.rollback()
            release_db_connection(conn)
        return jsonify({
            'success': False,
            'message': f'Error interno del servidor: {str(e)}'
        }), 500


@app.route('/login_user', methods=['POST'])
def login_user():
    """Endpoint para iniciar sesión"""
    print("\n" + "="*50)
    print("[DEBUG] 🔐 Iniciando proceso de login")
    print(f"[DEBUG] Timestamp: {datetime.now()}")
    
    try:
        # Obtener datos del request
        data = request.get_json()
        print(f"[DEBUG] Datos recibidos (sin password): {{'email': '{data.get('email')}'}}")
        
        usr_email = data.get('email')
        usr_password = data.get('password')
        
        # Validar campos
        if not usr_email or not usr_password:
            print("[ERROR] ❌ Campos incompletos")
            return jsonify({
                'success': False,
                'message': 'Email y contraseña son requeridos'
            }), 400
        
        print(f"[DEBUG] Email: {usr_email}")
        print(f"[DEBUG] Password length: {len(usr_password)}")
        
        # Obtener conexión
        conn = get_db_connection()
        if not conn:
            return jsonify({
                'success': False,
                'message': 'Error de conexión a la base de datos'
            }), 500
        
        cursor = conn.cursor()
        
        # Buscar usuario por email
        print("[DEBUG] Buscando usuario en la base de datos...")
        cursor.execute(
            """
            SELECT usr_index, usr_name, usr_email, usr_password 
            FROM usr_mstr 
            WHERE usr_email = %s
            """,
            (usr_email,)
        )
        
        user = cursor.fetchone()
        
        # Cerrar cursor y liberar conexión
        cursor.close()
        release_db_connection(conn)
        
        # Verificar si el usuario existe
        if not user:
            print("[ERROR] ❌ Usuario no encontrado")
            return jsonify({
                'success': False,
                'message': 'Credenciales incorrectas'
            }), 401
        
        print("[DEBUG] ✅ Usuario encontrado")
        
        usr_index, usr_name, usr_email_db, hashed_password = user
        
        # Verificar contraseña
        print("[DEBUG] Verificando contraseña...")
        password_match = bcrypt.checkpw(
            usr_password.encode('utf-8'),
            hashed_password.encode('utf-8')
        )
        
        if not password_match:
            print("[ERROR] ❌ Contraseña incorrecta")
            return jsonify({
                'success': False,
                'message': 'Credenciales incorrectas'
            }), 401
        
        print("[DEBUG] ✅ Contraseña correcta")
        print(f"[DEBUG] 🎉 Login exitoso para usuario ID: {usr_index}")
        print("="*50 + "\n")
        
        return jsonify({
            'success': True,
            'message': f'¡Bienvenido, {usr_name}!',
            'data': {
                'usr_index': usr_index,
                'usr_name': usr_name,
                'usr_email': usr_email_db
            }
        }), 200
        
    except Exception as e:
        print(f"[ERROR] ❌ Error inesperado: {e}")
        if 'conn' in locals() and conn:
            release_db_connection(conn)
        return jsonify({
            'success': False,
            'message': f'Error interno del servidor: {str(e)}'
        }), 500


# ============================================================================
# ENDPOINTS PARA GESTIÓN DE SESIONES DE TERAPIA
# ============================================================================

@app.route('/therapy/session/start', methods=['POST'])
def start_therapy_session():
    """
    Inicia una nueva sesión de terapia
    
    Body esperado:
    {
        "usr_index": 1,
        "therapy_type": "palabras",  // o "números"
        "therapy_category": "adjetivos"  // opcional
    }
    """
    print("\n" + "="*50)
    print("[DEBUG] 🎯 Iniciando nueva sesión de terapia")
    print(f"[DEBUG] Timestamp: {datetime.now()}")
    
    try:
        data = request.get_json()
        print(f"[DEBUG] Datos recibidos: {data}")
        
        usr_index = data.get('usr_index')
        therapy_type = data.get('therapy_type')
        therapy_category = data.get('therapy_category')
        
        # Validaciones
        if not usr_index or not therapy_type:
            print("[ERROR] ❌ Campos requeridos faltantes")
            return jsonify({
                'success': False,
                'message': 'usr_index y therapy_type son requeridos'
            }), 400
        
        if therapy_type not in ['palabras', 'números']:
            print("[ERROR] ❌ Tipo de terapia inválido")
            return jsonify({
                'success': False,
                'message': 'therapy_type debe ser "palabras" o "números"'
            }), 400
        
        # Verificar si hay sesiones activas del mismo tipo
        conn = get_db_connection()
        if not conn:
            return jsonify({
                'success': False,
                'message': 'Error de conexión a la base de datos'
            }), 500
        
        cursor = conn.cursor()
        
        # Buscar sesiones activas
        cursor.execute(
            """
            SELECT session_id FROM therapy_sessions 
            WHERE usr_index = %s 
            AND therapy_type = %s 
            AND session_status = 'active'
            """,
            (usr_index, therapy_type)
        )
        
        active_session = cursor.fetchone()
        
        if active_session:
            print(f"[DEBUG] ⚠️ Sesión activa encontrada: {active_session[0]}")
            cursor.close()
            release_db_connection(conn)
            return jsonify({
                'success': False,
                'message': 'Ya existe una sesión activa de este tipo',
                'active_session_id': active_session[0]
            }), 409
        
        # Crear nueva sesión
        cursor.execute(
            """
            INSERT INTO therapy_sessions 
            (usr_index, therapy_type, therapy_category, started_at, session_status)
            VALUES (%s, %s, %s, %s, 'active')
            RETURNING session_id, started_at
            """,
            (usr_index, therapy_type, therapy_category, datetime.now())
        )
        
        session_id, started_at = cursor.fetchone()
        conn.commit()
        
        cursor.close()
        release_db_connection(conn)
        
        print(f"[DEBUG] ✅ Sesión creada exitosamente: {session_id}")
        print("="*50 + "\n")
        
        return jsonify({
            'success': True,
            'message': 'Sesión de terapia iniciada',
            'data': {
                'session_id': session_id,
                'therapy_type': therapy_type,
                'therapy_category': therapy_category,
                'started_at': started_at.isoformat()
            }
        }), 201
        
    except Exception as e:
        print(f"[ERROR] ❌ Error: {e}")
        if 'conn' in locals() and conn:
            conn.rollback()
            release_db_connection(conn)
        return jsonify({
            'success': False,
            'message': f'Error al crear sesión: {str(e)}'
        }), 500


from flask import Flask, request, jsonify
from datetime import datetime
import json

# ============================================================================
# ENDPOINTS PARA GESTIÓN DE SESIONES DE TERAPIA
# ============================================================================

@app.route('/therapy/session/start', methods=['POST'])
def start_therapy_session():
    """
    Inicia una nueva sesión de terapia
    
    Body esperado:
    {
        "usr_index": 1,
        "therapy_type": "palabras",  // o "números"
        "therapy_category": "adjetivos"  // opcional
    }
    """
    print("\n" + "="*50)
    print("[DEBUG] 🎯 Iniciando nueva sesión de terapia")
    print(f"[DEBUG] Timestamp: {datetime.now()}")
    
    try:
        data = request.get_json()
        print(f"[DEBUG] Datos recibidos: {data}")
        
        usr_index = data.get('usr_index')
        therapy_type = data.get('therapy_type')
        therapy_category = data.get('therapy_category')
        
        # Validaciones
        if not usr_index or not therapy_type:
            print("[ERROR] ❌ Campos requeridos faltantes")
            return jsonify({
                'success': False,
                'message': 'usr_index y therapy_type son requeridos'
            }), 400
        
        if therapy_type not in ['palabras', 'números']:
            print("[ERROR] ❌ Tipo de terapia inválido")
            return jsonify({
                'success': False,
                'message': 'therapy_type debe ser "palabras" o "números"'
            }), 400
        
        # Verificar si hay sesiones activas del mismo tipo
        conn = get_db_connection()
        if not conn:
            return jsonify({
                'success': False,
                'message': 'Error de conexión a la base de datos'
            }), 500
        
        cursor = conn.cursor()
        
        # Buscar sesiones activas
        cursor.execute(
            """
            SELECT session_id FROM therapy_sessions 
            WHERE usr_index = %s 
            AND therapy_type = %s 
            AND session_status = 'active'
            """,
            (usr_index, therapy_type)
        )
        
        active_session = cursor.fetchone()
        
        if active_session:
            print(f"[DEBUG] ⚠️ Sesión activa encontrada: {active_session[0]}")
            cursor.close()
            release_db_connection(conn)
            return jsonify({
                'success': False,
                'message': 'Ya existe una sesión activa de este tipo',
                'active_session_id': active_session[0]
            }), 409
        
        # Crear nueva sesión
        cursor.execute(
            """
            INSERT INTO therapy_sessions 
            (usr_index, therapy_type, therapy_category, started_at, session_status)
            VALUES (%s, %s, %s, %s, 'active')
            RETURNING session_id, started_at
            """,
            (usr_index, therapy_type, therapy_category, datetime.now())
        )
        
        session_id, started_at = cursor.fetchone()
        conn.commit()
        
        cursor.close()
        release_db_connection(conn)
        
        print(f"[DEBUG] ✅ Sesión creada exitosamente: {session_id}")
        print("="*50 + "\n")
        
        return jsonify({
            'success': True,
            'message': 'Sesión de terapia iniciada',
            'data': {
                'session_id': session_id,
                'therapy_type': therapy_type,
                'therapy_category': therapy_category,
                'started_at': started_at.isoformat()
            }
        }), 201
        
    except Exception as e:
        print(f"[ERROR] ❌ Error: {e}")
        if 'conn' in locals() and conn:
            conn.rollback()
            release_db_connection(conn)
        return jsonify({
            'success': False,
            'message': f'Error al crear sesión: {str(e)}'
        }), 500


@app.route('/therapy/session/<int:session_id>/answer', methods=['POST'])
def record_therapy_answer(session_id):
    """
    Registra una respuesta individual durante la sesión
    
    Body esperado:
    {
        "question_text": "perro",
        "expected_answer": "perro",
        "user_answer": "pero",
        "pronunciation_score": 75,
        "is_correct": false,
        "error_type": "substitution_r_to_",
        "error_details": {
            "baseSimilarity": 80,
            "phoneticIssue": "omission",
            "positionIssue": "none",
            "lengthDifference": 1
        }
    }
    """
    print("\n" + "="*50)
    print(f"[DEBUG] 📝 Registrando respuesta para sesión {session_id}")
    print(f"[DEBUG] Timestamp: {datetime.now()}")
    
    try:
        data = request.get_json()
        print(f"[DEBUG] Datos de respuesta: {data}")
        
        # Validaciones
        required_fields = ['question_text', 'expected_answer', 'user_answer', 
                          'pronunciation_score', 'is_correct']
        
        for field in required_fields:
            if field not in data:
                return jsonify({
                    'success': False,
                    'message': f'Campo requerido faltante: {field}'
                }), 400
        
        conn = get_db_connection()
        if not conn:
            return jsonify({
                'success': False,
                'message': 'Error de conexión a la base de datos'
            }), 500
        
        cursor = conn.cursor()
        
        # Verificar que la sesión existe y está activa
        cursor.execute(
            """
            SELECT session_status FROM therapy_sessions 
            WHERE session_id = %s
            """,
            (session_id,)
        )
        
        session = cursor.fetchone()
        
        if not session:
            cursor.close()
            release_db_connection(conn)
            return jsonify({
                'success': False,
                'message': 'Sesión no encontrada'
            }), 404
        
        if session[0] != 'active':
            cursor.close()
            release_db_connection(conn)
            return jsonify({
                'success': False,
                'message': f'La sesión está {session[0]}, no se pueden agregar respuestas'
            }), 400
        
        # Insertar respuesta
        cursor.execute(
            """
            INSERT INTO therapy_answers 
            (session_id, question_text, expected_answer, user_answer, 
             pronunciation_score, is_correct, error_type, error_details, answered_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING answer_id, answered_at
            """,
            (
                session_id,
                data['question_text'],
                data['expected_answer'],
                data['user_answer'],
                data['pronunciation_score'],
                data['is_correct'],
                data.get('error_type'),
                json.dumps(data.get('error_details', {})),
                datetime.now()
            )
        )
        
        answer_id, answered_at = cursor.fetchone()
        
        # Actualizar contadores de la sesión
        cursor.execute(
            """
            UPDATE therapy_sessions 
            SET total_questions = total_questions + 1,
                correct_answers = correct_answers + CASE WHEN %s THEN 1 ELSE 0 END
            WHERE session_id = %s
            """,
            (data['is_correct'], session_id)
        )
        
        conn.commit()
        cursor.close()
        release_db_connection(conn)
        
        print(f"[DEBUG] ✅ Respuesta registrada: {answer_id}")
        print("="*50 + "\n")
        
        return jsonify({
            'success': True,
            'message': 'Respuesta registrada exitosamente',
            'data': {
                'answer_id': answer_id,
                'session_id': session_id,
                'answered_at': answered_at.isoformat()
            }
        }), 201
        
    except Exception as e:
        print(f"[ERROR] ❌ Error: {e}")
        if 'conn' in locals() and conn:
            conn.rollback()
            release_db_connection(conn)
        return jsonify({
            'success': False,
            'message': f'Error al registrar respuesta: {str(e)}'
        }), 500


@app.route('/therapy/session/<int:session_id>/end', methods=['PUT'])
def end_therapy_session(session_id):
    """
    Finaliza una sesión de terapia
    
    Body opcional:
    {
        "status": "completed"  // o "abandoned"
    }
    """
    print("\n" + "="*50)
    print(f"[DEBUG] 🏁 Finalizando sesión {session_id}")
    print(f"[DEBUG] Timestamp: {datetime.now()}")
    
    try:
        data = request.get_json() or {}
        status = data.get('status', 'completed')
        
        if status not in ['completed', 'abandoned']:
            return jsonify({
                'success': False,
                'message': 'status debe ser "completed" o "abandoned"'
            }), 400
        
        conn = get_db_connection()
        if not conn:
            return jsonify({
                'success': False,
                'message': 'Error de conexión a la base de datos'
            }), 500
        
        cursor = conn.cursor()
        
        # Actualizar sesión
        cursor.execute(
            """
            UPDATE therapy_sessions 
            SET ended_at = %s, session_status = %s
            WHERE session_id = %s AND session_status = 'active'
            RETURNING session_id, total_questions, correct_answers
            """,
            (datetime.now(), status, session_id)
        )
        
        result = cursor.fetchone()
        
        if not result:
            cursor.close()
            release_db_connection(conn)
            return jsonify({
                'success': False,
                'message': 'Sesión no encontrada o ya finalizada'
            }), 404
        
        session_id, total_questions, correct_answers = result
        
        conn.commit()
        cursor.close()
        release_db_connection(conn)
        
        accuracy = (correct_answers / total_questions * 100) if total_questions > 0 else 0
        
        print(f"[DEBUG] ✅ Sesión finalizada: {session_id}")
        print(f"[DEBUG] Precisión: {accuracy:.2f}%")
        print("="*50 + "\n")
        
        return jsonify({
            'success': True,
            'message': 'Sesión finalizada exitosamente',
            'data': {
                'session_id': session_id,
                'status': status,
                'total_questions': total_questions,
                'correct_answers': correct_answers,
                'accuracy': round(accuracy, 2)
            }
        }), 200
        
    except Exception as e:
        print(f"[ERROR] ❌ Error: {e}")
        if 'conn' in locals() and conn:
            conn.rollback()
            release_db_connection(conn)
        return jsonify({
            'success': False,
            'message': f'Error al finalizar sesión: {str(e)}'
        }), 500


@app.route('/therapy/user/<int:usr_index>/resume', methods=['GET'])
def get_user_therapy_resume(usr_index):
    """
    Obtiene el estado actual de las terapias del usuario para reanudar
    
    Retorna:
    - Sesión activa si existe
    - Última palabra/pregunta que estaba practicando
    - Progreso general del usuario
    - Siguiente ejercicio recomendado
    
    Este endpoint se llama cuando el usuario inicia la skill
    """
    print("\n" + "="*50)
    print(f"[DEBUG] 🔄 Consultando estado de terapias para usuario {usr_index}")
    print(f"[DEBUG] Timestamp: {datetime.now()}")
    
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({
                'success': False,
                'message': 'Error de conexión a la base de datos'
            }), 500
        
        cursor = conn.cursor()
        
        # 1. Buscar sesión activa
        cursor.execute(
            """
            SELECT 
                s.session_id,
                s.therapy_type,
                s.therapy_category,
                s.started_at,
                s.total_questions,
                s.correct_answers,
                ta.question_text as last_question,
                ta.answered_at as last_activity
            FROM therapy_sessions s
            LEFT JOIN LATERAL (
                SELECT question_text, answered_at
                FROM therapy_answers
                WHERE session_id = s.session_id
                ORDER BY answered_at DESC
                LIMIT 1
            ) ta ON true
            WHERE s.usr_index = %s 
            AND s.session_status = 'active'
            ORDER BY s.started_at DESC
            LIMIT 1
            """,
            (usr_index,)
        )
        
        active_session = cursor.fetchone()
        
        # 2. Obtener estadísticas generales del usuario
        cursor.execute(
            """
            SELECT 
                therapy_type,
                COUNT(*) as completed_sessions,
                SUM(total_questions) as total_questions,
                SUM(correct_answers) as total_correct,
                ROUND(AVG(CASE 
                    WHEN total_questions > 0 
                    THEN (correct_answers::DECIMAL / total_questions) * 100 
                    ELSE 0 
                END), 2) as avg_accuracy
            FROM therapy_sessions
            WHERE usr_index = %s 
            AND session_status = 'completed'
            GROUP BY therapy_type
            """,
            (usr_index,)
        )
        
        user_stats = cursor.fetchall()
        
        # 3. Obtener categorías disponibles para cada tipo
        cursor.execute(
            """
            SELECT DISTINCT therapy_type, therapy_category
            FROM therapy_sessions
            WHERE usr_index = %s
            AND therapy_category IS NOT NULL
            ORDER BY therapy_type, therapy_category
            """,
            (usr_index,)
        )
        
        practiced_categories = cursor.fetchall()
        
        cursor.close()
        release_db_connection(conn)
        
        # Formatear respuesta
        response_data = {
            'has_active_session': False,
            'user_statistics': {},
            'practiced_categories': {},
            'recommendation': None
        }
        
        # Si hay sesión activa
        if active_session:
            session_id, therapy_type, therapy_category, started_at, total_questions, correct_answers, last_question, last_activity = active_session
            
            accuracy = (correct_answers / total_questions * 100) if total_questions > 0 else 0
            
            response_data['has_active_session'] = True
            response_data['active_session'] = {
                'session_id': session_id,
                'therapy_type': therapy_type,
                'therapy_category': therapy_category,
                'started_at': started_at.isoformat(),
                'last_question': last_question,
                'last_activity': last_activity.isoformat() if last_activity else None,
                'total_questions': total_questions,
                'correct_answers': correct_answers,
                'accuracy': round(accuracy, 2)
            }
            
            print(f"[DEBUG] ✅ Sesión activa encontrada: {session_id}")
            print(f"[DEBUG] Última actividad: {last_activity}")
        
        # Estadísticas por tipo de terapia
        stats_dict = {}
        for stat in user_stats:
            stats_dict[stat[0]] = {
                'completed_sessions': stat[1],
                'total_questions': stat[2],
                'total_correct': stat[3],
                'avg_accuracy': float(stat[4])
            }
        
        response_data['user_statistics'] = stats_dict
        
        # Categorías practicadas
        categories_dict = {'palabras': [], 'números': []}
        for category in practiced_categories:
            if category[0] in categories_dict:
                categories_dict[category[0]].append(category[1])
        
        response_data['practiced_categories'] = categories_dict
        
        # Generar recomendación si no hay sesión activa
        if not active_session:
            if not stats_dict:
                response_data['recommendation'] = {
                    'therapy_type': 'palabras',
                    'therapy_category': 'adjetivos',
                    'reason': 'first_time'
                }
            else:
                # Recomendar el tipo con menor precisión
                lowest_type = min(stats_dict.items(), key=lambda x: x[1]['avg_accuracy'])
                response_data['recommendation'] = {
                    'therapy_type': lowest_type[0],
                    'reason': 'needs_practice',
                    'current_accuracy': lowest_type[1]['avg_accuracy']
                }
        
        print(f"[DEBUG] ✅ Estado consultado exitosamente")
        print("="*50 + "\n")
        
        return jsonify({
            'success': True,
            'data': response_data
        }), 200
        
    except Exception as e:
        print(f"[ERROR] ❌ Error: {e}")
        if 'conn' in locals() and conn:
            release_db_connection(conn)
        return jsonify({
            'success': False,
            'message': f'Error al consultar estado: {str(e)}'
        }), 500

@app.route('/therapy/session/start', methods=['POST'])
def start_therapy_session():
    """
    Inicia una nueva sesión de terapia
    
    Body esperado:
    {
        "usr_index": 1,
        "therapy_type": "palabras",  // o "números"
        "therapy_category": "adjetivos"  // opcional
    }
    
    LLAMAR desde Alexa cuando:
    - Usuario dice "empezar terapia de palabras/números"
    - Usuario selecciona una categoría específica
    """
    print("\n" + "="*50)
    print("[DEBUG] 🎯 Iniciando nueva sesión de terapia")
    print(f"[DEBUG] Timestamp: {datetime.now()}")
    
    try:
        data = request.get_json()
        print(f"[DEBUG] Datos recibidos: {data}")
        
        usr_index = data.get('usr_index')
        therapy_type = data.get('therapy_type')
        therapy_category = data.get('therapy_category')
        
        # Validaciones
        if not usr_index or not therapy_type:
            print("[ERROR] ❌ Campos requeridos faltantes")
            return jsonify({
                'success': False,
                'message': 'usr_index y therapy_type son requeridos'
            }), 400
        
        if therapy_type not in ['palabras', 'números']:
            print("[ERROR] ❌ Tipo de terapia inválido")
            return jsonify({
                'success': False,
                'message': 'therapy_type debe ser "palabras" o "números"'
            }), 400
        
        conn = get_db_connection()
        if not conn:
            return jsonify({
                'success': False,
                'message': 'Error de conexión a la base de datos'
            }), 500
        
        cursor = conn.cursor()
        
        # Verificar si hay sesiones activas del MISMO tipo
        cursor.execute(
            """
            SELECT session_id FROM therapy_sessions 
            WHERE usr_index = %s 
            AND therapy_type = %s 
            AND session_status = 'active'
            """,
            (usr_index, therapy_type)
        )
        
        active_session = cursor.fetchone()
        
        if active_session:
            print(f"[DEBUG] ⚠️ Ya existe sesión activa: {active_session[0]}")
            cursor.close()
            release_db_connection(conn)
            return jsonify({
                'success': False,
                'message': 'Ya tienes una sesión activa de este tipo',
                'active_session_id': active_session[0],
                'should_resume': True
            }), 409
        
        # Crear nueva sesión
        cursor.execute(
            """
            INSERT INTO therapy_sessions 
            (usr_index, therapy_type, therapy_category, started_at, session_status)
            VALUES (%s, %s, %s, %s, 'active')
            RETURNING session_id, started_at
            """,
            (usr_index, therapy_type, therapy_category, datetime.now())
        )
        
        session_id, started_at = cursor.fetchone()
        conn.commit()
        
        cursor.close()
        release_db_connection(conn)
        
        print(f"[DEBUG] ✅ Sesión creada exitosamente: {session_id}")
        print("="*50 + "\n")
        
        return jsonify({
            'success': True,
            'message': 'Sesión de terapia iniciada',
            'data': {
                'session_id': session_id,
                'therapy_type': therapy_type,
                'therapy_category': therapy_category,
                'started_at': started_at.isoformat()
            }
        }), 201
        
    except Exception as e:
        print(f"[ERROR] ❌ Error: {e}")
        if 'conn' in locals() and conn:
            conn.rollback()
            release_db_connection(conn)
        return jsonify({
            'success': False,
            'message': f'Error al crear sesión: {str(e)}'
        }), 500

@app.route('/therapy/session/<int:session_id>/answer', methods=['POST'])
def record_therapy_answer(session_id):
    """
    Registra una respuesta individual durante la sesión
    
    Body esperado:
    {
        "question_text": "perro",
        "expected_answer": "perro",
        "user_answer": "pero",
        "pronunciation_score": 75,
        "is_correct": false,
        "error_type": "substitution_r_to_",
        "error_details": {
            "baseSimilarity": 80,
            "phoneticIssue": "omission",
            "positionIssue": "none",
            "lengthDifference": 1
        }
    }
    
    LLAMAR desde Alexa:
    - Después de cada respuesta del usuario en validateWordAnswer
    - Después de cada respuesta en validateNumberAnswer
    - Usar los resultados de validateWord() para llenar los campos
    """
    print("\n" + "="*50)
    print(f"[DEBUG] 📝 Registrando respuesta para sesión {session_id}")
    print(f"[DEBUG] Timestamp: {datetime.now()}")
    
    try:
        data = request.get_json()
        print(f"[DEBUG] Respuesta: {data.get('user_answer')} (esperado: {data.get('expected_answer')})")
        print(f"[DEBUG] Score: {data.get('pronunciation_score')}")
        
        # Validaciones
        required_fields = ['question_text', 'expected_answer', 'user_answer', 
                          'pronunciation_score', 'is_correct']
        
        for field in required_fields:
            if field not in data:
                return jsonify({
                    'success': False,
                    'message': f'Campo requerido faltante: {field}'
                }), 400
        
        conn = get_db_connection()
        if not conn:
            return jsonify({
                'success': False,
                'message': 'Error de conexión a la base de datos'
            }), 500
        
        cursor = conn.cursor()
        
        # Verificar que la sesión existe y está activa
        cursor.execute(
            """
            SELECT session_status FROM therapy_sessions 
            WHERE session_id = %s
            """,
            (session_id,)
        )
        
        session = cursor.fetchone()
        
        if not session:
            cursor.close()
            release_db_connection(conn)
            return jsonify({
                'success': False,
                'message': 'Sesión no encontrada'
            }), 404
        
        if session[0] != 'active':
            cursor.close()
            release_db_connection(conn)
            return jsonify({
                'success': False,
                'message': f'La sesión está {session[0]}, no se pueden agregar respuestas'
            }), 400
        
        # Insertar respuesta
        cursor.execute(
            """
            INSERT INTO therapy_answers 
            (session_id, question_text, expected_answer, user_answer, 
             pronunciation_score, is_correct, error_type, error_details, answered_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING answer_id, answered_at
            """,
            (
                session_id,
                data['question_text'],
                data['expected_answer'],
                data['user_answer'],
                data['pronunciation_score'],
                data['is_correct'],
                data.get('error_type'),
                json.dumps(data.get('error_details', {})),
                datetime.now()
            )
        )
        
        answer_id, answered_at = cursor.fetchone()
        
        # Actualizar contadores de la sesión
        cursor.execute(
            """
            UPDATE therapy_sessions 
            SET total_questions = total_questions + 1,
                correct_answers = correct_answers + CASE WHEN %s THEN 1 ELSE 0 END
            WHERE session_id = %s
            RETURNING total_questions, correct_answers
            """,
            (data['is_correct'], session_id)
        )
        
        total_questions, correct_answers = cursor.fetchone()
        
        conn.commit()
        cursor.close()
        release_db_connection(conn)
        
        accuracy = (correct_answers / total_questions * 100) if total_questions > 0 else 0
        
        print(f"[DEBUG] ✅ Respuesta registrada: {answer_id}")
        print(f"[DEBUG] Progreso: {correct_answers}/{total_questions} ({accuracy:.1f}%)")
        print("="*50 + "\n")
        
        return jsonify({
            'success': True,
            'message': 'Respuesta registrada exitosamente',
            'data': {
                'answer_id': answer_id,
                'session_id': session_id,
                'answered_at': answered_at.isoformat(),
                'session_progress': {
                    'total_questions': total_questions,
                    'correct_answers': correct_answers,
                    'accuracy': round(accuracy, 2)
                }
            }
        }), 201
        
    except Exception as e:
        print(f"[ERROR] ❌ Error: {e}")
        if 'conn' in locals() and conn:
            conn.rollback()
            release_db_connection(conn)
        return jsonify({
            'success': False,
            'message': f'Error al registrar respuesta: {str(e)}'
        }), 500

@app.route('/therapy/session/<int:session_id>/end', methods=['PUT'])
def end_therapy_session(session_id):
    """
    Finaliza una sesión de terapia
    
    Body opcional:
    {
        "status": "completed"  // o "abandoned"
    }
    
    LLAMAR desde Alexa cuando:
    - Usuario dice "terminar", "salir", "cancelar"
    - Usuario completa todas las preguntas
    - Usuario cambia a otro tipo de terapia
    - Sesión de timeout (usar "abandoned")
    """
    print("\n" + "="*50)
    print(f"[DEBUG] 🏁 Finalizando sesión {session_id}")
    print(f"[DEBUG] Timestamp: {datetime.now()}")
    
    try:
        data = request.get_json() or {}
        status = data.get('status', 'completed')
        
        if status not in ['completed', 'abandoned']:
            return jsonify({
                'success': False,
                'message': 'status debe ser "completed" o "abandoned"'
            }), 400
        
        conn = get_db_connection()
        if not conn:
            return jsonify({
                'success': False,
                'message': 'Error de conexión a la base de datos'
            }), 500
        
        cursor = conn.cursor()
        
        # Actualizar sesión
        cursor.execute(
            """
            UPDATE therapy_sessions 
            SET ended_at = %s, session_status = %s
            WHERE session_id = %s AND session_status = 'active'
            RETURNING session_id, therapy_type, total_questions, correct_answers, started_at
            """,
            (datetime.now(), status, session_id)
        )
        
        result = cursor.fetchone()
        
        if not result:
            cursor.close()
            release_db_connection(conn)
            return jsonify({
                'success': False,
                'message': 'Sesión no encontrada o ya finalizada'
            }), 404
        
        session_id, therapy_type, total_questions, correct_answers, started_at = result
        
        conn.commit()
        cursor.close()
        release_db_connection(conn)
        
        accuracy = (correct_answers / total_questions * 100) if total_questions > 0 else 0
        duration_minutes = (datetime.now() - started_at).total_seconds() / 60
        
        print(f"[DEBUG] ✅ Sesión finalizada: {session_id}")
        print(f"[DEBUG] Resultado: {correct_answers}/{total_questions} ({accuracy:.1f}%)")
        print(f"[DEBUG] Duración: {duration_minutes:.1f} minutos")
        print("="*50 + "\n")
        
        return jsonify({
            'success': True,
            'message': 'Sesión finalizada exitosamente',
            'data': {
                'session_id': session_id,
                'therapy_type': therapy_type,
                'status': status,
                'total_questions': total_questions,
                'correct_answers': correct_answers,
                'accuracy': round(accuracy, 2),
                'duration_minutes': round(duration_minutes, 2)
            }
        }), 200
        
    except Exception as e:
        print(f"[ERROR] ❌ Error: {e}")
        if 'conn' in locals() and conn:
            conn.rollback()
            release_db_connection(conn)
        return jsonify({
            'success': False,
            'message': f'Error al finalizar sesión: {str(e)}'
        }), 500

# ============================================================================
# ENDPOINT DE ESTADÍSTICAS RÁPIDAS (PARA ALEXA)
# ============================================================================

@app.route('/therapy/user/<int:usr_index>/quick-stats', methods=['GET'])
def get_quick_stats(usr_index):
    """
    Retorna estadísticas rápidas para que Alexa las mencione
    
    Ejemplo de uso en Alexa:
    "Llevas 15 sesiones completadas con un 85% de precisión"
    """
    print("\n" + "="*50)
    print(f"[DEBUG] ⚡ Estadísticas rápidas para usuario {usr_index}")
    
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({
                'success': False,
                'message': 'Error de conexión a la base de datos'
            }), 500
        
        cursor = conn.cursor()
        
        cursor.execute(
            """
            SELECT 
                COUNT(*) as total_sessions,
                SUM(total_questions) as total_questions,
                SUM(correct_answers) as total_correct,
                ROUND(AVG(CASE 
                    WHEN total_questions > 0 
                    THEN (correct_answers::DECIMAL / total_questions) * 100 
                    ELSE 0 
                END), 0) as avg_accuracy
            FROM therapy_sessions
            WHERE usr_index = %s 
            AND session_status = 'completed'
            """,
            (usr_index,)
        )
        
        stats = cursor.fetchone()
        
        cursor.close()
        release_db_connection(conn)
        
        if not stats or stats[0] == 0:
            return jsonify({
                'success': True,
                'data': {
                    'is_new_user': True,
                    'total_sessions': 0,
                    'total_questions': 0,
                    'total_correct': 0,
                    'avg_accuracy': 0
                }
            }), 200
        
        return jsonify({
            'success': True,
            'data': {
                'is_new_user': False,
                'total_sessions': stats[0],
                'total_questions': stats[1],
                'total_correct': stats[2],
                'avg_accuracy': int(stats[3])
            }
        }), 200
        
    except Exception as e:
        print(f"[ERROR] ❌ Error: {e}")
        if 'conn' in locals() and conn:
            release_db_connection(conn)
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/test', methods=['GET'])
def test():
    return jsonify({"message": "hola mundo"})

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)