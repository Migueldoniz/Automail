# backend/app.py
import os
import pdfplumber
import sqlite3 
from flask import Flask, request, jsonify, redirect, send_from_directory, g
from flask_cors import CORS
from dotenv import load_dotenv
import google.generativeai as genai
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user

DATABASE = 'automail.db'

# Carrega as variáveis de ambiente
load_dotenv()

# --- Configuração do Banco de Dados ---
def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
    return db

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

def init_db():
    with app.app_context():
        db = get_db()
        cursor = db.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                email TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                password_hash TEXT NOT NULL
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS email_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_email TEXT,
                text TEXT,
                category TEXT,
                suggestion TEXT,
                FOREIGN KEY (user_email) REFERENCES users (email)
            )
        ''')
        # Adiciona um usuário admin padrão se não existir
        cursor.execute("SELECT * FROM users WHERE email = ?", ("admin@admin.com",))
        if cursor.fetchone() is None:
            cursor.execute("INSERT INTO users (email, name, password_hash) VALUES (?, ?, ?)",
                           ("admin@admin.com", "Admin", generate_password_hash("password")))
        db.commit()

# --- Configuração da API e Autenticação ---
app = Flask(__name__)
CORS(app, supports_credentials=True)
# A secret_key DEVE ser um valor fixo e secreto, carregado de variáveis de ambiente.
# Usar os.urandom(24) gera uma nova chave a cada reinício, invalidando todas as sessões de login.
# Para o Render, adicione FLASK_SECRET_KEY às suas variáveis de ambiente.
# Você pode gerar um valor forte em um terminal Python com: import secrets; secrets.token_hex(16)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "uma-chave-secreta-padrao-para-desenvolvimento")

# Garante que o banco de dados seja criado ao iniciar a aplicação
init_db()

login_manager = LoginManager()
login_manager.init_app(app)


class User(UserMixin):
    def __init__(self, id, name):
        self.id = id
        self.name = name

@login_manager.user_loader
def load_user(user_id):
    db = get_db()
    user_data = db.execute('SELECT * FROM users WHERE email = ?', (user_id,)).fetchone()
    if user_data:
        return User(id=user_data['email'], name=user_data['name'])
    return None

@login_manager.unauthorized_handler
def unauthorized():
    if request.path.startswith('/api/'):
        return jsonify(error="Login Required"), 401
    return redirect("/")

# --- Rotas de Autenticação ---
@app.route('/signup', methods=['POST'])
def signup():
    data = request.get_json()
    email = data.get('email')
    name = data.get('name')
    password = data.get('password')

    if not email or not name or not password:
        return jsonify(error='Todos os campos são obrigatórios!'), 400

    db = get_db()
    cursor = db.cursor()
    try:
        cursor.execute("INSERT INTO users (email, name, password_hash) VALUES (?, ?, ?)",
                       (email, name, generate_password_hash(password)))
        db.commit()
        return jsonify(message='Cadastro realizado com sucesso!'), 201
    except sqlite3.IntegrityError:
        return jsonify(error='Este e-mail já está cadastrado.'), 409
    finally:
        pass # A conexão será fechada pelo teardown_appcontext

@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')

    db = get_db()
    user_data = db.execute('SELECT * FROM users WHERE email = ?', (email,)).fetchone()

    if user_data and check_password_hash(user_data['password_hash'], password):
        user = User(id=user_data['email'], name=user_data['name'])
        login_user(user)
        return jsonify(message='Login bem-sucedido!'), 200

    return jsonify(error='Email ou senha inválidos'), 401

@app.route('/logout', methods=['POST'])
@login_required
def logout():
    logout_user()
    return jsonify(message="Logout bem-sucedido"), 200

@app.route('/api/user')
@login_required
def get_current_user():
    return jsonify({'name': current_user.name, 'email': current_user.id})

# --- Rotas da Aplicação ---
@app.route('/api/history')
@login_required
def history():
    db = get_db()
    history_data = db.execute('SELECT text, category, suggestion FROM email_history WHERE user_email = ? ORDER BY id DESC', (current_user.id,)).fetchall()
    user_history = [dict(row) for row in history_data]
    return jsonify(user_history)

# Configura a API do Gemini
try:
    genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
    model = genai.GenerativeModel('gemini-1.5-flash-latest')
except Exception as e:
    print(f"Erro ao configurar a API do Gemini: {e}")
    model = None

# --- Funções Auxiliares ---
def extract_text_from_pdf(file_stream):
    text = ""
    try:
        with pdfplumber.open(file_stream) as pdf:
            for page in pdf.pages:
                text += page.extract_text() or ""
        return text
    except Exception as e:
        print(f"Erro ao ler PDF com pdfplumber: {e}")
        return ""

def classify_email_with_ai(text):
    if not model: return "Improdutivo"
    prompt = f"""Analise o e-mail a seguir e classifique-o como 'Produtivo' ou 'Improdutivo'. Retorne APENAS a palavra 'Produtivo' ou 'Improdutivo'. E-mail: \"{text}\""""
    try:
        response = model.generate_content(prompt)
        category = response.text.strip()
        return category if category in ['Produtivo', 'Improdutivo'] else 'Improdutivo'
    except Exception as e:
        print(f"Erro na classificação com Gemini: {e}")
        return "Improdutivo"

def generate_response_with_ai(email_text, category):
    if not model: return "Não foi possível gerar uma sugestão."
    prompt = f"O seguinte e-mail foi classificado como '{category}'. Com base em seu conteúdo, sugira uma resposta curta, profissional e em português. E-mail: \"{email_text}\""
    try:
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        print(f"Erro na geração de resposta com Gemini: {e}")
        return "Não foi possível gerar uma sugestão."

# --- Rota Principal da API (Agora Protegida) ---
@app.route('/api/process', methods=['POST'])
@login_required
def process_email():
    if not model:
        return jsonify({'error': 'A API do Gemini não foi inicializada corretamente.'}), 500
    
    raw_text = ""
    if 'file' in request.files:
        file = request.files['file']
        if file.filename.endswith('.txt'):
            raw_text = file.read().decode('utf-8')
        elif file.filename.endswith('.pdf'):
            raw_text = extract_text_from_pdf(file)
        else:
            return jsonify({'error': 'Formato de arquivo inválido. Use .txt ou .pdf'}), 400
    elif 'email_text' in request.form:
        raw_text = request.form['email_text']

    if not raw_text:
        return jsonify({'error': 'Nenhum conteúdo de e-mail fornecido'}), 400

    category = classify_email_with_ai(raw_text)
    suggestion = generate_response_with_ai(raw_text, category)

    # Salva no histórico do banco de dados
    db = get_db()
    db.execute('INSERT INTO email_history (user_email, text, category, suggestion) VALUES (?, ?, ?, ?)',
               (current_user.id, raw_text, category, suggestion))
    db.commit()

    return jsonify({
        'category': category,
        'suggestion': suggestion
    })

if __name__ == '__main__':
    app.run(debug=True, port=5000)

# --- Rotas para servir o Frontend ---
@app.route('/')
def serve_index():
    return send_from_directory('../frontend', 'index.html')

@app.route('/<path:path>')
def serve_static_files(path):
    # Garante que rotas como /app.html ou /static/logo.png sejam servidas
    return send_from_directory('../frontend', path)