"""
Configuração da conexão com o Redis.
"""
import os
import redis
import json

# URL do Redis
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
REDIS_DB = int(os.getenv("REDIS_DB", 0))

# Pool de conexões Redis
redis_pool = redis.ConnectionPool(
    host=REDIS_HOST,
    port=REDIS_PORT,
    db=REDIS_DB,
    decode_responses=True  # Decodificar respostas para string
)

def get_cache():
    """
    Dependency para obter cliente Redis.
    Retorna None se não conseguir conectar.
    """
    try:
        r = redis.Redis(connection_pool=redis_pool)
        r.ping()  # Verificar conexão
        return r
    except redis.exceptions.ConnectionError:
        print("⚠️  Não foi possível conectar ao Redis.")
        return None

def set_cache(key: str, value: any, ttl: int = 300):
    """
    Adiciona um valor ao cache com um TTL (Time To Live).
    Serializa o valor para JSON se for um dict ou list.
    """
    r = get_cache()
    if r:
        try:
            if isinstance(value, (dict, list)):
                value = json.dumps(value)
            r.set(key, value, ex=ttl)
        except Exception as e:
            print(f"⚠️  Erro ao salvar no cache: {e}")

def get_from_cache(key: str) -> any:
    """
    Obtém um valor do cache.
    Desserializa o valor de JSON se for um dict ou list.
    """
    r = get_cache()
    if r:
        try:
            cached_value = r.get(key)
            if cached_value:
                try:
                    # Tenta desserializar como JSON
                    return json.loads(cached_value)
                except json.JSONDecodeError:
                    # Se não for JSON, retorna o valor original
                    return cached_value
            return None
        except Exception as e:
            print(f"⚠️  Erro ao obter do cache: {e}")
            return None
    return None

def invalidate_cache(key: str):
    """
    Invalida (deleta) uma chave do cache.
    """
    r = get_cache()
    if r:
        try:
            r.delete(key)
        except Exception as e:
            print(f"⚠️  Erro ao invalidar cache: {e}")
