from fastapi import FastAPI
import mysql.connector
import os
from dotenv import load_dotenv

load_dotenv()

app = FastAPI()

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