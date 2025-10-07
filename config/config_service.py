"""
Serviço de lógica de negócio para configurações.
"""
from sqlalchemy.orm import Session
from typing import Optional, List, Dict, Any
import httpx
import json
from config.config_model import Configuracao
from config.config_schema import (
    ConfiguracaoCriar,
    ConfiguracaoAtualizar,
    ModeloLLM,
    TestarConexaoResposta
)


class ConfiguracaoService:
    """Serviço para gerenciar configurações do sistema."""

    @staticmethod
    def obter_por_chave(db: Session, chave: str) -> Optional[Configuracao]:
        """Obtém uma configuração pela chave."""
        return db.query(Configuracao).filter(Configuracao.chave == chave).first()

    @staticmethod
    def obter_valor(db: Session, chave: str, padrao: Any = None) -> Any:
        """
        Obtém o valor de uma configuração, convertendo para o tipo correto.
        Retorna o valor padrão se não encontrar.
        """
        config = ConfiguracaoService.obter_por_chave(db, chave)
        if not config or config.valor is None:
            return padrao

        # Converter para o tipo correto
        try:
            if config.tipo == "int":
                return int(config.valor)
            elif config.tipo == "float":
                return float(config.valor)
            elif config.tipo == "bool":
                return config.valor.lower() in ("true", "1", "sim", "yes")
            elif config.tipo == "json":
                return json.loads(config.valor)
            else:
                return config.valor
        except (ValueError, json.JSONDecodeError):
            return padrao

    @staticmethod
    def listar_por_categoria(db: Session, categoria: str) -> List[Configuracao]:
        """Lista todas as configurações de uma categoria."""
        return db.query(Configuracao).filter(Configuracao.categoria == categoria).all()

    @staticmethod
    def listar_todas(db: Session) -> List[Configuracao]:
        """Lista todas as configurações."""
        return db.query(Configuracao).all()

    @staticmethod
    def criar(db: Session, config: ConfiguracaoCriar) -> Configuracao:
        """Cria uma nova configuração."""
        db_config = Configuracao(**config.model_dump())
        db.add(db_config)
        db.commit()
        db.refresh(db_config)
        return db_config

    @staticmethod
    def atualizar(db: Session, chave: str, config: ConfiguracaoAtualizar) -> Optional[Configuracao]:
        """Atualiza uma configuração existente."""
        db_config = ConfiguracaoService.obter_por_chave(db, chave)
        if not db_config:
            return None

        if not db_config.editavel:
            raise ValueError("Esta configuração não pode ser editada")

        update_data = config.model_dump(exclude_unset=True)
        for campo, valor in update_data.items():
            setattr(db_config, campo, valor)

        db.commit()
        db.refresh(db_config)
        return db_config

    @staticmethod
    def definir_valor(db: Session, chave: str, valor: Any, criar_se_nao_existir: bool = True) -> Configuracao:
        """
        Define o valor de uma configuração.
        Cria a configuração se não existir e criar_se_nao_existir=True.
        """
        db_config = ConfiguracaoService.obter_por_chave(db, chave)

        if db_config:
            # Converter valor para string
            if isinstance(valor, (dict, list)):
                valor_str = json.dumps(valor, ensure_ascii=False)
            else:
                valor_str = str(valor)

            db_config.valor = valor_str
            db.commit()
            db.refresh(db_config)
            return db_config
        elif criar_se_nao_existir:
            # Criar nova configuração
            tipo = "string"
            if isinstance(valor, bool):
                tipo = "bool"
            elif isinstance(valor, int):
                tipo = "int"
            elif isinstance(valor, float):
                tipo = "float"
            elif isinstance(valor, (dict, list)):
                tipo = "json"

            nova_config = ConfiguracaoCriar(
                chave=chave,
                valor=str(valor) if not isinstance(valor, (dict, list)) else json.dumps(valor),
                tipo=tipo,
                categoria="geral"
            )
            return ConfiguracaoService.criar(db, nova_config)
        else:
            raise ValueError(f"Configuração '{chave}' não encontrada")

    @staticmethod
    def deletar(db: Session, chave: str) -> bool:
        """Deleta uma configuração."""
        db_config = ConfiguracaoService.obter_por_chave(db, chave)
        if not db_config:
            return False

        if not db_config.editavel:
            raise ValueError("Esta configuração não pode ser deletada")

        db.delete(db_config)
        db.commit()
        return True

    @staticmethod
    async def testar_conexao_openrouter(db: Session, api_key: Optional[str] = None) -> TestarConexaoResposta:
        """
        Testa a conexão com OpenRouter e busca modelos disponíveis.
        """
        # Usar API key fornecida ou buscar do banco
        if not api_key:
            api_key = ConfiguracaoService.obter_valor(db, "openrouter_api_key")

        if not api_key:
            return TestarConexaoResposta(
                sucesso=False,
                mensagem="API Key do OpenRouter não configurada",
                modelos=None
            )

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    "https://openrouter.ai/api/v1/models",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json"
                    },
                    timeout=10.0
                )

                if response.status_code == 200:
                    data = response.json()
                    modelos = []

                    for modelo_data in data.get("data", []):
                        modelo = ModeloLLM(
                            id=modelo_data.get("id", ""),
                            nome=modelo_data.get("name", modelo_data.get("id", "")),
                            contexto=modelo_data.get("context_length"),
                            preco_input=modelo_data.get("pricing", {}).get("prompt"),
                            preco_output=modelo_data.get("pricing", {}).get("completion"),
                            suporta_imagens="vision" in modelo_data.get("id", "").lower() or 
                                          "vision" in modelo_data.get("name", "").lower() or
                                          modelo_data.get("architecture", {}).get("modality") == "multimodal",
                            suporta_ferramentas="tools" in modelo_data.get("supported_parameters", [])
                        )
                        modelos.append(modelo)

                    # Salvar API key se a conexão foi bem-sucedida
                    ConfiguracaoService.definir_valor(db, "openrouter_api_key", api_key)

                    return TestarConexaoResposta(
                        sucesso=True,
                        mensagem=f"{len(modelos)} modelos disponíveis",
                        modelos=modelos
                    )
                elif response.status_code == 401:
                    return TestarConexaoResposta(
                        sucesso=False,
                        mensagem="API Key inválida",
                        modelos=None
                    )
                else:
                    return TestarConexaoResposta(
                        sucesso=False,
                        mensagem=f"Erro ao conectar: {response.status_code}",
                        modelos=None
                    )

        except httpx.TimeoutException:
            return TestarConexaoResposta(
                sucesso=False,
                mensagem="Timeout ao conectar com OpenRouter",
                modelos=None
            )
        except Exception as e:
            return TestarConexaoResposta(
                sucesso=False,
                mensagem=f"Erro: {str(e)}",
                modelos=None
            )

    @staticmethod
    def inicializar_configuracoes_padrao(db: Session):
        """Inicializa configurações padrão do sistema."""
        configuracoes_padrao = [
            # Provedores LLM
            {
                "chave": "llm_provedor_padrao",
                "valor": "openrouter",
                "tipo": "string",
                "descricao": "Provedor LLM padrão (openrouter, local, custom)",
                "categoria": "llm",
                "editavel": True
            },
            {
                "chave": "llm_provedor_local_id",
                "valor": None,
                "tipo": "int",
                "descricao": "ID do provedor local padrão",
                "categoria": "llm",
                "editavel": True
            },
            {
                "chave": "llm_fallback_openrouter",
                "valor": "true",
                "tipo": "bool",
                "descricao": "Usar OpenRouter como fallback quando provedor local falhar",
                "categoria": "llm",
                "editavel": True
            },
            # OpenRouter
            {
                "chave": "openrouter_api_key",
                "valor": None,
                "tipo": "string",
                "descricao": "API Key do OpenRouter",
                "categoria": "openrouter",
                "editavel": True
            },
            {
                "chave": "openrouter_modelo_padrao",
                "valor": "google/gemini-2.0-flash-001",
                "tipo": "string",
                "descricao": "Modelo LLM padrão",
                "categoria": "openrouter",
                "editavel": True
            },
            {
                "chave": "openrouter_temperatura",
                "valor": "0.7",
                "tipo": "float",
                "descricao": "Temperatura para geração de respostas (0.0 a 2.0)",
                "categoria": "openrouter",
                "editavel": True
            },
            {
                "chave": "openrouter_max_tokens",
                "valor": "2000",
                "tipo": "int",
                "descricao": "Máximo de tokens na resposta",
                "categoria": "openrouter",
                "editavel": True
            },
            {
                "chave": "openrouter_top_p",
                "valor": "1.0",
                "tipo": "float",
                "descricao": "Top P para amostragem (0.0 a 1.0)",
                "categoria": "openrouter",
                "editavel": True
            },
            # Agente
            {
                "chave": "agente_papel_padrao",
                "valor": "assistente pessoal",
                "tipo": "string",
                "descricao": "Papel padrão do agente",
                "categoria": "agente",
                "editavel": True
            },
            {
                "chave": "agente_objetivo_padrao",
                "valor": "ajudar o usuário com suas dúvidas e tarefas",
                "tipo": "string",
                "descricao": "Objetivo padrão do agente",
                "categoria": "agente",
                "editavel": True
            },
            {
                "chave": "agente_politicas_padrao",
                "valor": "ser educado, respeitoso e prestativo",
                "tipo": "string",
                "descricao": "Políticas padrão do agente",
                "categoria": "agente",
                "editavel": True
            },
            {
                "chave": "agente_tarefa_padrao",
                "valor": "responder perguntas de forma clara e objetiva",
                "tipo": "string",
                "descricao": "Tarefa padrão do agente",
                "categoria": "agente",
                "editavel": True
            },
            {
                "chave": "agente_objetivo_explicito_padrao",
                "valor": "fornecer informações úteis e precisas",
                "tipo": "string",
                "descricao": "Objetivo explícito padrão do agente",
                "categoria": "agente",
                "editavel": True
            },
            {
                "chave": "agente_publico_padrao",
                "valor": "usuários em geral",
                "tipo": "string",
                "descricao": "Público-alvo padrão do agente",
                "categoria": "agente",
                "editavel": True
            },
            {
                "chave": "agente_restricoes_padrao",
                "valor": "responder em português brasileiro, ser conciso",
                "tipo": "string",
                "descricao": "Restrições padrão do agente",
                "categoria": "agente",
                "editavel": True
            },
            # Sistema
            {
                "chave": "sistema_diretorio_uploads",
                "valor": "./uploads",
                "tipo": "string",
                "descricao": "Diretório para armazenar uploads",
                "categoria": "geral",
                "editavel": True
            },
            {
                "chave": "sistema_max_tamanho_imagem_mb",
                "valor": "10",
                "tipo": "int",
                "descricao": "Tamanho máximo de imagem em MB",
                "categoria": "geral",
                "editavel": True
            },
        ]

        for config_data in configuracoes_padrao:
            # Verificar se já existe
            existe = ConfiguracaoService.obter_por_chave(db, config_data["chave"])
            if not existe:
                config = ConfiguracaoCriar(**config_data)
                ConfiguracaoService.criar(db, config)
