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

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/test', methods=['GET'])
def test():
    return jsonify({"message": "hola mundo"})

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)