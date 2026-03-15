from fastapi import FastAPI
import mysql.connector
import os
from dotenv import load_dotenv
import bcrypt
from fastapi.middleware.cors import CORSMiddleware

from fastapi import HTTPException
from pydantic import BaseModel


class LoginRequest(BaseModel):
    email: str
    senha: str


class NotaQR(BaseModel):
    chave_nf: str
    parametro_qr: str

load_dotenv()

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # permite qualquer origem (modo desenvolvimento)
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_connection():
    return mysql.connector.connect(
        host=os.getenv("DB_HOST"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        database=os.getenv("DB_NAME")
    )

@app.get("/")
def home():
    return {"status": "API funcionando"}

@app.get("/teste-banco")
def teste_banco():
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        result = cursor.fetchone()
        cursor.close()
        conn.close()
        return {"banco": "conectado", "resultado": result}
    except Exception as e:
        return {"erro": str(e)}

@app.get("/usuarios")
def listar_usuarios():
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("""
            SELECT ID, DESCRICAO, EMAIL
            FROM cadastro_usuario
            LIMIT 10
        """)
        dados = cursor.fetchall()

        cursor.close()
        conn.close()

        return dados

    except Exception as e:
        return {"erro": str(e)}


@app.post("/login")
def login(dados: LoginRequest):
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute(
        "SELECT * FROM cadastro_usuario WHERE EMAIL = %s",
        (dados.email,)
    )

    usuario = cursor.fetchone()

    cursor.close()
    conn.close()

    if not usuario:
        raise HTTPException(status_code=401, detail="Usuário não encontrado")

    senha_hash = usuario["senha"]

    if not bcrypt.checkpw(
        dados.senha.encode(),
        senha_hash.encode()
    ):
        raise HTTPException(status_code=401, detail="Senha inválida")

    return {"mensagem": "Login sucesso", "usuario": usuario["DESCRICAO"]}

@app.get("/nf-existe/{chave_nf}")
def verificar_nf(chave_nf: str):
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute(
            "SELECT ID FROM mercado_qr_nf WHERE CHAVE_NF = %s",
            (chave_nf,)
        )

        nota = cursor.fetchone()

        cursor.close()
        conn.close()

        if nota:
            return {"existe": True}
        else:
            return {"existe": False}

    except Exception as e:
        return {"erro": str(e)}

@app.post("/nf-salvar")
def salvar_nf(dados: NotaQR):

    try:
        conn = get_connection()
        cursor = conn.cursor()

        # verifica duplicidade
        cursor.execute(
            "SELECT ID FROM mercado_qr_nf WHERE CHAVE_NF = %s",
            (dados.chave_nf,)
        )

        existe = cursor.fetchone()

        if existe:
            cursor.close()
            conn.close()
            return {"status": "nota já existe"}

        cursor.execute(
            """
            INSERT INTO mercado_qr_nf
            (CHAVE_NF, PARAMETRO_QR, PROCESSADA)
            VALUES (%s, %s, 'N')
            """,
            (dados.chave_nf, dados.parametro_qr)
        )

        conn.commit()

        cursor.close()
        conn.close()

        return {"status": "nota salva"}

    except Exception as e:
        return {"erro": str(e)}