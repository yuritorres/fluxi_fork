"""
Serviço de Reconhecimento de Intenção do Usuário.
"""
from sqlalchemy.orm import Session
from typing import Literal
from llm_providers.llm_integration_service import LLMIntegrationService
from config.config_service import ConfiguracaoService

# Tipos de intenções possíveis
Intencao = Literal[
    "fazer_pedido",
    "consultar_cardapio",
    "rastrear_entrega",
    "falar_com_atendente",
    "outro"
]

class IntencaoService:
    """
    Serviço para reconhecer a intenção principal de uma mensagem do usuário
    usando um modelo de linguagem pequeno e rápido.
    """

    @staticmethod
    async def reconhecer_intencao(db: Session, texto_mensagem: str) -> Intencao:
        """
        Analisa o texto de uma mensagem e retorna a intenção do usuário.

        Args:
            db: A sessão do banco de dados.
            texto_mensagem: O conteúdo da mensagem do usuário.

        Returns:
            A intenção classificada.
        """
        # Modelo rápido e de baixo custo para classificação
        modelo_classificacao = ConfiguracaoService.obter_valor(
            db, "modelo_classificacao_intencao", "anthropic/claude-3-haiku-20240307"
        )

        intencoes_disponiveis = [
            "fazer_pedido",
            "consultar_cardapio",
            "rastrear_entrega",
            "falar_com_atendente",
            "outro"
        ]

        # Prompt otimizado para a tarefa de classificação
        system_prompt = (
            "Você é um assistente de IA focado em classificar a intenção do usuário. "
            "Sua única tarefa é analisar a mensagem do usuário e classificá-la em uma das "
            f"seguintes categorias: {', '.join(intencoes_disponiveis)}. "
            "Responda APENAS com o nome da categoria, em letras minúsculas. "
            "Se a intenção não se encaixar claramente em nenhuma das opções, "
            "use 'outro'."
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": texto_mensagem}
        ]

        try:
            print(f"🔎 [INTENCAO] Classificando mensagem: '{texto_mensagem[:50]}...'")
            resultado = await LLMIntegrationService.processar_mensagem_com_llm(
                db=db,
                messages=messages,
                modelo=modelo_classificacao,
                agente_id=None,  # Não está associado a um agente específico
                temperatura=0.0, # Baixa temperatura para respostas mais diretas
                max_tokens=20,     # Resposta curta (apenas o nome da intenção)
                top_p=1.0,
                tools=None,
                stream=False
            )

            # A resposta do LLM deve ser a própria intenção
            resposta_llm = resultado.get("conteudo", "").strip().lower()
            print(f"✅ [INTENCAO] Resposta do LLM: '{resposta_llm}'")

            # Validar se a resposta é uma das intenções válidas
            if resposta_llm in intencoes_disponiveis:
                return resposta_llm
            else:
                print(f"⚠️ [INTENCAO] Resposta inválida do LLM. Usando 'outro'.")
                return "outro"

        except Exception as e:
            print(f"❌ [INTENCAO] Erro ao classificar intenção: {e}")
            # Em caso de erro, assumir a intenção 'outro' para não quebrar o fluxo
            return "outro"
