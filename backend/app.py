# backend/app.py
import os
import pdfplumber
from flask import Flask, request, jsonify, redirect
from flask_cors import CORS
from dotenv import load_dotenv
import google.generativeai as genai
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user

# Carrega as variáveis de ambiente
load_dotenv()

# --- Configuração da API e Autenticação ---
app = Flask(__name__)
CORS(app, supports_credentials=True)
app.secret_key = os.urandom(24)

login_manager = LoginManager()
login_manager.init_app(app)

# --- Modelos e "Banco de Dados" em Memória ---
users = {
    "admin@admin.com": {
        "password_hash": generate_password_hash("password"),
        "name": "Admin"
    }
}
email_history = {}

class User(UserMixin):
    def __init__(self, id, name):
        self.id = id
        self.name = name

@login_manager.user_loader
def load_user(user_id):
    if user_id in users:
        return User(id=user_id, name=users[user_id]["name"])
    return None

@login_manager.unauthorized_handler
def unauthorized():
    if request.path.startswith('/api/'):
        return jsonify(error="Login Required"), 401
    return redirect("http://127.0.0.1:5500/frontend/index.html")

# --- Rotas de Autenticação ---
@app.route('/signup', methods=['POST'])
def signup():
    email = request.form.get('email')
    name = request.form.get('name')
    password = request.form.get('password')
    if not email or not name or not password:
        return 'Todos os campos são obrigatórios!', 400
    if email in users:
        return 'Este e-mail já está cadastrado.', 409
    users[email] = {
        'password_hash': generate_password_hash(password),
        'name': name
    }
    return redirect("http://127.0.0.1:5500/frontend/index.html")

@app.route('/login', methods=['POST'])
def login():
    email = request.form.get('email')
    password = request.form.get('password')
    user_data = users.get(email)
    if user_data and check_password_hash(user_data['password_hash'], password):
        user = User(id=email, name=user_data["name"])
        login_user(user)
        return redirect("http://127.0.0.1:5500/frontend/app.html")
    return 'Email ou senha inválidos', 401

@app.route('/logout', methods=['POST'])
@login_required
def logout():
    logout_user()
    return redirect("http://127.0.0.1:5500/frontend/index.html")

@app.route('/api/user')
@login_required
def get_current_user():
    return jsonify({'name': current_user.name, 'email': current_user.id})

# --- Rotas da Aplicação ---
@app.route('/api/history')
@login_required
def history():
    user_history = email_history.get(current_user.id, [])
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

    # Salva no histórico
    if current_user.id not in email_history:
        email_history[current_user.id] = []
    
    email_history[current_user.id].insert(0, {
        'text': raw_text[:300],
        'category': category,
        'suggestion': suggestion
    })

    return jsonify({
        'category': category,
        'suggestion': suggestion
    })

if __name__ == '__main__':
    app.run(debug=True, port=5000)