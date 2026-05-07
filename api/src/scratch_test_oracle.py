import oracledb
import structlog
from src.settings import get_settings
from src.infrastructure.database.oracle.legacy_connection import OracleLegacyConnection

settings = get_settings()

def inspect_oracle():
    print(f"Connecting to Oracle at {settings.ORACLE_DSN} as {settings.ORACLE_USER}...")
    OracleLegacyConnection.connect()
    
    sql = """
        SELECT COLUMN_NAME, DATA_TYPE 
        FROM ALL_TAB_COLUMNS 
        WHERE TABLE_NAME = 'GED_CONTEUDO'
        ORDER BY COLUMN_ID
    """
    try:
        results = OracleLegacyConnection.execute_query(sql)
        print("--- Columns of GED_DOCUMENTO ---")
        for row in results:
            print(f"{row['column_name']}: {row['data_type']}")
        print("--------------------")
    except Exception as e:
        print(f"Error querying Oracle: {e}")

if __name__ == "__main__":
    inspect_oracle()
