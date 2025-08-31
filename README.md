# Automail

Automail é uma aplicação web que utiliza inteligência artificial para classificar e-mails e sugerir respostas. O sistema permite que os usuários enviem e-mails (em formato de texto ou PDF) e recebam uma classificação de "Produtivo" ou "Improdutivo", juntamente com uma sugestão de resposta gerada por IA.

## Funcionalidades

-   **Cadastro e Login de Usuários:** Sistema de autenticação para proteger o acesso dos usuários.
-   **Upload de E-mails:** Envie o conteúdo do e-mail como texto ou em um arquivo PDF.
-   **Classificação com IA:** Utiliza o Gemini para classificar os e-mails em:
    -   **Produtivo:** E-mails que exigem uma ação ou resposta.
    -   **Improdutivo:** E-mails que não necessitam de uma ação imediata.
-   **Sugestão de Resposta:** A IA gera uma sugestão de resposta com base no conteúdo e na categoria do e-mail.
-   **Histórico de E-mails:** Os usuários podem ver um histórico de todos os e-mails que processaram.

## Estrutura do Projeto

```
/
├── backend/
│   ├── app.py              # Aplicação principal Flask (API e servidor web)
│   └── requirements.txt    # Dependências Python do backend
├── frontend/
│   ├── index.html          # Página inicial/login
│   ├── signup.html         # Página de cadastro
│   ├── app.html            # Página principal da aplicação
│   ├── history.html        # Página de histórico
│   └── style.css           # Estilos
├── test_emails/
│   ├── ...                 # Arquivos de texto e PDF para teste
├── .env.example            # Exemplo de arquivo de variáveis de ambiente
├── generate_pdfs.py        # Script para gerar os PDFs de teste
└── README.md               # Este arquivo
```

## Pré-requisitos

-   Python 3.7+
-   Uma chave de API do [Google AI Studio](https://aistudio.google.com/app/apikey)

## Instalação e Configuração

Siga os passos abaixo para configurar e rodar o projeto localmente.

1.  **Clone o Repositório**

    ```bash
    git clone <URL_DO_REPOSITORIO>
    cd Automail
    ```

2.  **Crie e Ative um Ambiente Virtual**

    É uma boa prática usar um ambiente virtual para isolar as dependências do projeto.

    ```bash
    # Windows
    python -m venv venv
    .\venv\Scripts\activate

    # macOS / Linux
    python3 -m venv venv
    source venv/bin/activate
    ```

3.  **Instale as Dependências**

    As dependências do backend estão listadas no arquivo `requirements.txt`.

    ```bash
    pip install -r backend/requirements.txt
    ```

4.  **Configure as Variáveis de Ambiente**

    Crie um arquivo chamado `.env` na raiz do projeto, copiando o `.env.example`. Em seguida, adicione sua chave da API do Google.

    ```
    # .env
    GOOGLE_API_KEY="SUA_CHAVE_DE_API_AQUI"
    FLASK_SECRET_KEY="UMA_CHAVE_SECRETA_FORTE_PODE_SER_GERADA_COM_OS.URANDOM(24)"
    ```

    -   `GOOGLE_API_KEY`: Essencial para a integração com o Gemini.
    -   `FLASK_SECRET_KEY`: Necessária para a segurança das sessões do Flask.

## Rodando a Aplicação

Com o ambiente virtual ativado e as variáveis de ambiente configuradas, inicie o servidor Flask:

```bash
python backend/app.py
```

O servidor iniciará na porta 5000. Abra seu navegador e acesse [http://localhost:5000](http://localhost:5000).

A aplicação inicializa o banco de dados SQLite (`automail.db`) automaticamente na primeira vez que é executada.

## Scripts Auxiliares

### `generate_pdfs.py`

Este script converte os arquivos `.txt` da pasta `test_emails` em arquivos `.pdf`. É útil para gerar os arquivos de teste necessários para testar o upload de PDFs.

Para executá-lo, primeiro instale a dependência `fpdf`:

```bash
pip install fpdf
```

Em seguida, rode o script a partir da raiz do projeto:

```bash
python generate_pdfs.py
```
