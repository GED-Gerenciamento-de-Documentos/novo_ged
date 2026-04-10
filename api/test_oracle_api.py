import asyncio
from fastapi import FastAPI, HTTPException
import uvicorn
import oracledb
from contextlib import asynccontextmanager

import os
from contextlib import contextmanager

# Carregar arquivo manualmente
env_file = ".env" if os.path.exists(".env") else ".env.legacy"
if os.path.exists(env_file):
    with open(env_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and "=" in line and not line.startswith("#"):
                key, val = line.split("=", 1)
                os.environ.setdefault(key.strip(), val.strip())

# ========================================================
# Configurações do Oracle vindas do .env
# ========================================================
ORACLE_USER = os.getenv("ORACLE_USER", "dbamv")
ORACLE_PASSWORD = os.getenv("ORACLE_PASSWORD", "")
ORACLE_DSN = os.getenv("ORACLE_DSN", "192.168.4.90:1521/prd")

# Habilitar o modo Thick (necessário para Oracle 11.1 e mais antigos)
# Apontando para o diretório do Oracle Client instalado no seu computador:
oracledb.init_oracle_client(lib_dir=r"C:\app\product\19.0.0\client_1\bin")

pool = None

@contextmanager
def get_sync_pool():
    global pool
    if not pool:
        print(f"\n🔄 Conectando ao banco Oracle no servidor {ORACLE_DSN}...")
        try:
            pool = oracledb.create_pool(
                user=ORACLE_USER,
                password=ORACLE_PASSWORD,
                dsn=ORACLE_DSN,
                min=1,
                max=5
            )
            print("✅ Conectado ao Oracle com sucesso!\n")
        except Exception as e:
            print(f"❌ Erro ao conectar no Oracle: {e}\n")
    yield pool

app = FastAPI(title="Teste de Conexão Oracle")

# Pre-aquecer o pool no evento de startup usando decorator legado só para o teste
@app.on_event("startup")
def startup_event():
    with get_sync_pool():
        pass

@app.on_event("shutdown")
def shutdown_event():
    global pool
    if pool:
        print("🔄 Encerrando conexão com o Oracle...")
        pool.close()

# Note que não tem 'async def' aqui. O FastAPI joga isso num threadpool automaticamente!
@app.get("/testar-oracle/{patient_id}")
def buscar_documentos_paciente(patient_id: int):
    """
    Busca documentos do paciente informando o patient_id.
    """
    if not pool:
        raise HTTPException(status_code=500, detail="Pool não inicializado.")
    
    sql = """
        SELECT * FROM (
            SELECT 
                t.patientid,
                t.patientname,
                g.gedid,
                g.filename     AS nome_arquivo,
                g.creationdate AS dt_inclusao_log,
                t.ROWID        AS row_id
            FROM 
                GEMMIUS.GEDLEGACY t
            JOIN 
                GEMMIUS.GED g ON t.gedid = g.gedid
            WHERE 
                t.patientid = :patient_id
            ORDER BY t.ROWID DESC
        )
    """
    
    try:
        with pool.acquire() as conn:
            with conn.cursor() as cursor:
                cursor.execute(sql, patient_id=patient_id)
                columns = [col[0].lower() for col in cursor.description]
                rows = cursor.fetchall()
                data = [dict(zip(columns, row)) for row in rows]
                
                return {
                    "mensagem": "Busca realizada com sucesso no Oracle usando JOIN entre GEDLEGACY e GED!",
                    "patient_id": patient_id,
                    "documentos_encontrados": len(data),
                    "dados": data
                }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao executar a consulta: {str(e)}")

@app.get("/testar-arquivo/{filename}")
def testar_arquivo_fisico(filename: str):
    """
    Testa se o arquivo físico existe no servidor 192.168.8.53 / Unidades H: e J:
    """
    possiveis_caminhos = [
        f"H:\\GED\\{filename}",
        f"J:\\GED\\{filename}",
        f"\\\\192.168.8.53\\GED\\{filename}",
        f"\\\\192.168.8.53\\H$\\GED\\{filename}",
        f"\\\\192.168.8.53\\J$\\GED\\{filename}"
    ]
    
    resultados = []
    encontrado = False
    caminho_correto = None
    tamanho_bytes = 0
    
    for caminho in possiveis_caminhos:
        existe = os.path.exists(caminho)
        info = {"caminho_tentado": caminho, "existe": existe}
        
        if existe:
            encontrado = True
            caminho_correto = caminho
            tamanho_bytes = os.path.getsize(caminho)
            info["tamanho_bytes"] = tamanho_bytes
            
        resultados.append(info)
        
    if encontrado:
        return {
            "status": "SUCESSO",
            "mensagem": f"Arquivo encontrado na rede!",
            "caminho_funcional": caminho_correto,
            "tamanho_mb": round(tamanho_bytes / (1024 * 1024), 2),
            "tentativas": resultados
        }
    else:
        return {
            "status": "FALHA",
            "mensagem": "O arquivo não foi encontrado em nenhum local mapeado. Verifique se as unidades H: ou J: estão mapeadas no seu Windows ou se você precisa de permissão de rede.",
            "tentativas": resultados
        }

@app.get("/testar-arquivos-paciente/{patient_id}")
def testar_todos_arquivos_paciente(patient_id: int):
    """
    Busca todos os arquivos do paciente no banco e verifica se eles REALMENTE existem nas pastas da rede.
    """
    if not pool:
        raise HTTPException(status_code=500, detail="Pool não inicializado.")
        
    sql = """
        SELECT g.filename
        FROM GEMMIUS.GEDLEGACY t
        JOIN GEMMIUS.GED g ON t.gedid = g.gedid
        WHERE t.patientid = :patient_id
    """
    
    arquivos_no_banco = []
    try:
        with pool.acquire() as conn:
            with conn.cursor() as cursor:
                cursor.execute(sql, patient_id=patient_id)
                rows = cursor.fetchall()
                arquivos_no_banco = [row[0] for row in rows if row[0]]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao buscar arquivos no banco: {str(e)}")
        
    relatorio = {
        "resumo": {
            "total_no_banco": len(arquivos_no_banco),
            "total_fisicamente_encontrados": 0,
            "total_faltando": 0
        },
        "arquivos_encontrados": [],
        "arquivos_faltando": []
    }
    
    for filename in arquivos_no_banco:
        possiveis_caminhos = [
            f"H:\\GED\\{filename}",
            f"J:\\GED\\{filename}",
            f"\\\\192.168.8.53\\GED\\{filename}",
            f"\\\\192.168.8.53\\H$\\GED\\{filename}",
            f"\\\\192.168.8.53\\J$\\GED\\{filename}"
        ]
        
        encontrado = False
        caminho_final = None
        
        for caminho in possiveis_caminhos:
            if os.path.exists(caminho):
                encontrado = True
                caminho_final = caminho
                break
                
        if encontrado:
            relatorio["resumo"]["total_fisicamente_encontrados"] += 1
            tamanho = os.path.getsize(caminho_final)
            relatorio["arquivos_encontrados"].append({
                "filename": filename,
                "caminho": caminho_final,
                "tamanho_mb": round(tamanho / (1024 * 1024), 2)
            })
        else:
            relatorio["resumo"]["total_faltando"] += 1
            relatorio["arquivos_faltando"].append({
                "filename": filename,
                "mensagem": "Não encontrado em H:, J: ou no UNC \\\\192.168.8.53"
            })
            
    return relatorio

if __name__ == "__main__":
    uvicorn.run("test_oracle_api:app", host="0.0.0.0", port=8001, reload=True)
