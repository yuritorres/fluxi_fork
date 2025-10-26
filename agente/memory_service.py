"""
Serviço para gerenciar a memória do agente usando Mem0.
"""
import os
from mem0 import Memory
from sqlalchemy.orm import Session
from config.config_service import ConfiguracaoService

class MemoryService:
    """
    Serviço para interagir com a camada de memória Mem0.
    """
    def __init__(self, db: Session):
        """
        Inicializa o MemoryService.

        Args:
            db: A sessão do banco de dados.
        """
        api_key = ConfiguracaoService.obter_valor(db, "openai_api_key")
        if api_key:
            os.environ["OPENAI_API_KEY"] = api_key

        if not os.getenv("OPENAI_API_KEY"):
            print("AVISO: OPENAI_API_KEY não foi encontrada para o Mem0. O serviço pode não funcionar.")

        self.memory = Memory()

    def add_memory(self, messages: list, user_id: str):
        """
        Adiciona uma nova memória.

        Args:
            messages: Uma lista de mensagens para adicionar à memória.
            user_id: O ID do usuário associado à memória.
        """
        # A API do Mem0 espera a lista de mensagens diretamente
        self.memory.add(messages, user_id=user_id)

    def search_memory(self, query: str, user_id: str) -> list:
        """
        Busca na memória.

        Args:
            query: A consulta de busca.
            user_id: O ID do usuário para filtrar a busca.

        Returns:
            Uma lista de resultados da busca.
        """
        # A busca agora usa um filtro para o user_id
        results = self.memory.search(query=query, filters={"user_id": user_id})

        # A API pode retornar um dicionário ou uma lista. Normalizar para uma lista.
        if isinstance(results, dict) and "results" in results:
            return results["results"]
        if isinstance(results, list):
            return results
        return []
