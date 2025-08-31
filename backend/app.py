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

# --- Configuração Inicial e Constantes ---

# Carrega as variáveis de ambiente do arquivo .env
load_dotenv()

# PONTO CRÍTICO: Configuração do Banco de Dados para o Render
# O Render apaga arquivos locais. Use um "Persistent Disk".
# 1. Crie um disco no Render com o "Mount Path" de, por exemplo, /data
# 2. Defina uma variável de ambiente DATABASE_PATH no Render para /data/automail.db
DATABASE_PATH = os.getenv('DATABASE_PATH', 'automail.db') # Usa 'automail.db' como padrão para dev local

# --- Criação da Instância da Aplicação Flask ---
# MOVIDO PARA CÁ: 'app' precisa ser definido antes de ser usado por decoradores ou funções.
app = Flask(__name__)
CORS(app, supports_credentials=True)

# A secret_key DEVE ser um valor fixo e secreto, carregado de variáveis de ambiente.
# Para o Render, adicione FLASK_SECRET_KEY às suas variáveis de ambiente.
# Você pode gerar um valor forte em um terminal Python com: import secrets; secrets.token_hex(16)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "uma-chave-secreta-padrao-para-desenvolvimento")


# --- Configuração do Banco de Dados ---
def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE_PATH)
        db.row_factory = sqlite3.Row
    return db

# AGORA FUNCIONA: @app.teardown_appcontext pode encontrar a variável 'app'
@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

def init_db():
    # AGORA FUNCIONA: app.app_context pode encontrar a variável 'app'
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


# --- Configuração da Autenticação ---
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


# --- Configuração da API do Gemini ---
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
    try:
        db.execute("INSERT INTO users (email, name, password_hash) VALUES (?, ?, ?)",
                   (email, name, generate_password_hash(password)))
        db.commit()
        return jsonify(message='Cadastro realizado com sucesso!'), 201
    except sqlite3.IntegrityError:
        return jsonify(error='Este e-mail já está cadastrado.'), 409

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


# --- Rotas da API Principal ---
@app.route('/api/history')
@login_required
def history():
    db = get_db()
    history_data = db.execute('SELECT text, category, suggestion FROM email_history WHERE user_email = ? ORDER BY id DESC', (current_user.id,)).fetchall()
    user_history = [dict(row) for row in history_data]
    return jsonify(user_history)

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

    db = get_db()
    db.execute('INSERT INTO email_history (user_email, text, category, suggestion) VALUES (?, ?, ?, ?)',
               (current_user.id, raw_text, category, suggestion))
    db.commit()

    return jsonify({
        'category': category,
        'suggestion': suggestion
    })


# Define o caminho para a pasta 'frontend'
FRONTEND_FOLDER = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'frontend'))
# Configura o Flask para usar a pasta 'frontend' para servir todos os arquivos estáticos.
# O static_url_path='' faz com que a rota seja a raiz ('/') em vez do padrão ('/static').
app.static_folder = FRONTEND_FOLDER
app.static_url_path = ''
# --- Rotas para servir o Frontend (Apenas para Desenvolvimento Local) ---
# Em produção, é melhor usar um serviço de "Static Site" do Render para o frontend.
@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')

@app.route('/')
def serve_index():
    # Esta rota garante que a página principal seja servida na raiz
    return app.send_static_file('index.html')

@app.route('/app.html')
def serve_app_page():
    # Rota específica para a página principal do app, caso o usuário acesse diretamente
    return app.send_static_file('app.html')

@app.errorhandler(404)
def not_found(e):
    # Se nenhuma rota da API ou arquivo estático for encontrado,
    # serve o index.html. Isso é útil para Single Page Applications (SPAs).
    return app.send_static_file('index.html')
# --- Ponto de Entrada da Aplicação ---
if __name__ == '__main__':
    # Garante que o banco de dados seja criado ao iniciar a aplicação em modo de desenvolvimento.
    init_db()
    app.run(debug=True, port=5000)
else:
    # Quando o Gunicorn importa o app, ele pode inicializar o banco de dados se necessário.
    # Esta chamada garante que a tabela exista antes que o primeiro request chegue.
    init_db()
