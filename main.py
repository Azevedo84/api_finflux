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

    return {
        "mensagem": "Login sucesso",
        "usuario": usuario["DESCRICAO"],
        "id": usuario["ID"]
    }

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
def salvar_nf(nota: NotaQR):

    conn = get_connection()
    cursor = conn.cursor()

    try:

        cursor.execute("""
            INSERT INTO mercado_qr_nf (CHAVE_NF, PARAMETRO_QR, PROCESSADA)
            VALUES (%s, %s, 'N')
        """, (nota.chave_nf, nota.parametro_qr))

        conn.commit()

        return {
            "status": "salvo"
        }

    except mysql.connector.errors.IntegrityError:

        return {
            "status": "duplicado"
        }

    finally:
        cursor.close()
        conn.close()

@app.get("/contas-correntes/{id_usuario}")
def contas_correntes(id_usuario: int):

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT bc.DESCRICAO, sb.SALDO
        FROM saldo_banco sb
        JOIN cadastro_banco bc 
            ON sb.ID_BANCO = bc.ID
        WHERE sb.ID_USUARIO = %s
        AND sb.ID_TIPOCONTA in (2, 4)
        AND sb.SALDO <> 0
        ORDER BY bc.DESCRICAO
    """, (id_usuario,))

    contas = cursor.fetchall()

    cursor.close()
    conn.close()

    return contas

@app.get("/resumo-mes/{id_usuario}")
def resumo_mes(id_usuario: int):

    conn = get_connection()
    cursor = conn.cursor()

    # RECEITAS
    cursor.execute("""
        SELECT SUM(mov.qtde_ent)
        FROM movimentacao mov
        JOIN saldo_banco sb ON mov.id_saldo = sb.id
        WHERE YEAR(mov.data) = YEAR(CURDATE())
        AND MONTH(mov.data) = MONTH(CURDATE())
        AND sb.id_usuario = %s
        AND mov.id_categoria IN (1, 2, 3, 4, 5, 151)
    """, (id_usuario,))

    entradas = cursor.fetchone()[0] or 0

    # DESPESAS
    cursor.execute("""
        SELECT SUM(mov.qtde_sai)
        FROM movimentacao mov
        JOIN saldo_banco sb ON mov.id_saldo = sb.id
        JOIN cadastro_categoria cat ON mov.id_categoria = cat.id
        JOIN cadastro_grupo gr ON cat.id_grupo = gr.id
        WHERE YEAR(mov.data) = YEAR(CURDATE())
        AND MONTH(mov.data) = MONTH(CURDATE())
        AND sb.id_usuario = %s
        AND gr.id NOT IN (1, 2, 14)
        AND cat.id NOT IN (103, 110, 158, 181, 109)
    """, (id_usuario,))

    saidas = cursor.fetchone()[0] or 0

    resultado = entradas - saidas

    cursor.close()
    conn.close()

    return {
        "entradas": entradas,
        "saidas": saidas,
        "resultado": resultado
    }

@app.get("/faturas-abertas/{id_usuario}")
def faturas_abertas(id_usuario: int):

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT f.id, 
            bc.descricao AS banco,
            DATE_FORMAT(f.vencimento, '%d/%m/%Y') AS vencimento,
            COALESCE(SUM(mov.qtde_sai),0) AS valor
        FROM cadastro_fatura f
        JOIN saldo_banco sb ON f.id_saldo = sb.id
        JOIN cadastro_banco bc ON sb.id_banco = bc.id
        LEFT JOIN movimentacao mov ON mov.id_fatura = f.id
        WHERE f.status = 'A'
        AND (f.ano < YEAR(CURDATE()) OR (f.ano <= YEAR(CURDATE()) AND f.mes <= MONTH(CURDATE())))
          AND sb.id_usuario = %s
        GROUP BY f.id, bc.descricao, f.vencimento
        ORDER BY f.vencimento
    """, (id_usuario,))

    dados = cursor.fetchall()

    cursor.close()
    conn.close()

    return dados

@app.get("/bancos-entrada/{id_usuario}")
def bancos_entrada(id_usuario: int):

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT DISTINCT bc.ID, bc.DESCRICAO
        FROM saldo_banco sb
        JOIN cadastro_banco bc ON sb.ID_BANCO = bc.ID
        WHERE sb.ID_USUARIO = %s
        AND sb.ID_TIPOCONTA IN (2,4)
        ORDER BY bc.DESCRICAO
    """, (id_usuario,))

    dados = cursor.fetchall()

    cursor.close()
    conn.close()

    return dados