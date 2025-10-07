"""
Serviço de métricas e estatísticas.
"""
from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from mensagem.mensagem_model import Mensagem
from sessao.sessao_model import Sessao


class MetricaService:
    """Serviço para calcular métricas e estatísticas."""

    @staticmethod
    def obter_metricas_gerais(db: Session) -> Dict[str, Any]:
        """Obtém métricas gerais do sistema."""
        # Total de sessões
        total_sessoes = db.query(Sessao).count()
        sessoes_ativas = db.query(Sessao).filter(Sessao.ativa == True).count()
        sessoes_conectadas = db.query(Sessao).filter(Sessao.status == "conectado").count()
        
        # Total de mensagens
        total_mensagens = db.query(Mensagem).count()
        mensagens_recebidas = db.query(Mensagem).filter(Mensagem.direcao == "recebida").count()
        mensagens_enviadas = db.query(Mensagem).filter(Mensagem.direcao == "enviada").count()
        
        # Mensagens processadas
        mensagens_processadas = db.query(Mensagem).filter(Mensagem.processada == True).count()
        mensagens_respondidas = db.query(Mensagem).filter(Mensagem.respondida == True).count()
        
        # Taxa de sucesso
        taxa_sucesso = (mensagens_respondidas / mensagens_recebidas * 100) if mensagens_recebidas > 0 else 0
        
        # Clientes únicos
        clientes_unicos = db.query(Mensagem.telefone_cliente).distinct().count()
        
        return {
            "sessoes": {
                "total": total_sessoes,
                "ativas": sessoes_ativas,
                "conectadas": sessoes_conectadas
            },
            "mensagens": {
                "total": total_mensagens,
                "recebidas": mensagens_recebidas,
                "enviadas": mensagens_enviadas,
                "processadas": mensagens_processadas,
                "respondidas": mensagens_respondidas
            },
            "performance": {
                "taxa_sucesso": round(taxa_sucesso, 2),
                "clientes_unicos": clientes_unicos
            }
        }

    @staticmethod
    def obter_metricas_sessao(db: Session, sessao_id: int) -> Dict[str, Any]:
        """Obtém métricas de uma sessão específica."""
        # Mensagens da sessão
        total_mensagens = db.query(Mensagem)\
            .filter(Mensagem.sessao_id == sessao_id)\
            .count()
        
        mensagens_recebidas = db.query(Mensagem)\
            .filter(
                Mensagem.sessao_id == sessao_id,
                Mensagem.direcao == "recebida"
            )\
            .count()
        
        mensagens_respondidas = db.query(Mensagem)\
            .filter(
                Mensagem.sessao_id == sessao_id,
                Mensagem.respondida == True
            )\
            .count()
        
        # Taxa de resposta
        taxa_resposta = (mensagens_respondidas / mensagens_recebidas * 100) if mensagens_recebidas > 0 else 0
        
        # Tempo médio de resposta
        tempo_medio = db.query(func.avg(Mensagem.resposta_tempo_ms))\
            .filter(
                Mensagem.sessao_id == sessao_id,
                Mensagem.resposta_tempo_ms.isnot(None)
            )\
            .scalar() or 0
        
        # Tokens utilizados
        tokens_input_total = db.query(func.sum(Mensagem.resposta_tokens_input))\
            .filter(Mensagem.sessao_id == sessao_id)\
            .scalar() or 0
        
        tokens_output_total = db.query(func.sum(Mensagem.resposta_tokens_output))\
            .filter(Mensagem.sessao_id == sessao_id)\
            .scalar() or 0
        
        # Clientes únicos
        clientes_unicos = db.query(Mensagem.telefone_cliente)\
            .filter(Mensagem.sessao_id == sessao_id)\
            .distinct()\
            .count()
        
        # Mensagens com imagem
        mensagens_com_imagem = db.query(Mensagem)\
            .filter(
                Mensagem.sessao_id == sessao_id,
                Mensagem.tipo == "imagem"
            )\
            .count()
        
        # Mensagens com ferramentas
        mensagens_com_ferramentas = db.query(Mensagem)\
            .filter(
                Mensagem.sessao_id == sessao_id,
                Mensagem.ferramentas_usadas.isnot(None)
            )\
            .count()
        
        return {
            "mensagens": {
                "total": total_mensagens,
                "recebidas": mensagens_recebidas,
                "respondidas": mensagens_respondidas,
                "com_imagem": mensagens_com_imagem,
                "com_ferramentas": mensagens_com_ferramentas
            },
            "performance": {
                "taxa_resposta": round(taxa_resposta, 2),
                "tempo_medio_ms": round(tempo_medio, 2),
                "clientes_unicos": clientes_unicos
            },
            "tokens": {
                "input_total": int(tokens_input_total),
                "output_total": int(tokens_output_total),
                "total": int(tokens_input_total + tokens_output_total)
            }
        }

    @staticmethod
    def obter_metricas_periodo(
        db: Session,
        sessao_id: Optional[int] = None,
        dias: int = 7
    ) -> Dict[str, Any]:
        """Obtém métricas de um período específico."""
        data_inicio = datetime.now() - timedelta(days=dias)
        
        query = db.query(Mensagem).filter(Mensagem.criado_em >= data_inicio)
        if sessao_id:
            query = query.filter(Mensagem.sessao_id == sessao_id)
        
        mensagens = query.all()
        
        # Agrupar por dia
        mensagens_por_dia = {}
        for msg in mensagens:
            dia = msg.criado_em.strftime("%Y-%m-%d")
            if dia not in mensagens_por_dia:
                mensagens_por_dia[dia] = {
                    "total": 0,
                    "recebidas": 0,
                    "respondidas": 0
                }
            
            mensagens_por_dia[dia]["total"] += 1
            if msg.direcao == "recebida":
                mensagens_por_dia[dia]["recebidas"] += 1
            if msg.respondida:
                mensagens_por_dia[dia]["respondidas"] += 1
        
        return {
            "periodo_dias": dias,
            "data_inicio": data_inicio.strftime("%Y-%m-%d"),
            "data_fim": datetime.now().strftime("%Y-%m-%d"),
            "mensagens_por_dia": mensagens_por_dia,
            "total_periodo": len(mensagens)
        }

    @staticmethod
    def obter_top_clientes(
        db: Session,
        sessao_id: int,
        limite: int = 10
    ) -> List[Dict[str, Any]]:
        """Obtém os clientes que mais enviaram mensagens."""
        result = db.query(
            Mensagem.telefone_cliente,
            func.count(Mensagem.id).label("total_mensagens")
        )\
        .filter(
            Mensagem.sessao_id == sessao_id,
            Mensagem.direcao == "recebida"
        )\
        .group_by(Mensagem.telefone_cliente)\
        .order_by(func.count(Mensagem.id).desc())\
        .limit(limite)\
        .all()
        
        return [
            {
                "telefone": r[0],
                "total_mensagens": r[1]
            }
            for r in result
        ]

    @staticmethod
    def obter_uso_ferramentas(db: Session, sessao_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """Obtém estatísticas de uso de ferramentas."""
        query = db.query(Mensagem)\
            .filter(Mensagem.ferramentas_usadas.isnot(None))
        
        if sessao_id:
            query = query.filter(Mensagem.sessao_id == sessao_id)
        
        mensagens = query.all()
        
        # Contar uso de cada ferramenta
        uso_ferramentas = {}
        for msg in mensagens:
            if msg.ferramentas_usadas:
                for ferramenta in msg.ferramentas_usadas:
                    nome = ferramenta.get("nome", "desconhecida")
                    if nome not in uso_ferramentas:
                        uso_ferramentas[nome] = 0
                    uso_ferramentas[nome] += 1
        
        # Converter para lista ordenada
        resultado = [
            {"nome": nome, "total_usos": total}
            for nome, total in sorted(uso_ferramentas.items(), key=lambda x: x[1], reverse=True)
        ]
        
        return resultado
