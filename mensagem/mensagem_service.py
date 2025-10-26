"""
Serviço de lógica de negócio para mensagens.
"""
from sqlalchemy.orm import Session
from typing import Optional, List
from datetime import datetime, timedelta
import os
import base64
from pathlib import Path
from PIL import Image
import io
from neonize.events import MessageEv
from mensagem.mensagem_model import Mensagem
from mensagem.mensagem_schema import MensagemCriar


class MensagemService:
    """Serviço para gerenciar mensagens."""

    @staticmethod
    def listar_por_sessao(
        db: Session,
        sessao_id: int,
        limite: int = 100,
        offset: int = 0
    ) -> List[Mensagem]:
        """Lista mensagens de uma sessão."""
        return db.query(Mensagem)\
            .filter(Mensagem.sessao_id == sessao_id)\
            .order_by(Mensagem.criado_em.desc())\
            .limit(limite)\
            .offset(offset)\
            .all()

    @staticmethod
    def listar_por_cliente(
        db: Session,
        sessao_id: int,
        telefone_cliente: str,
        limite: int = 50
    ) -> List[Mensagem]:
        """Lista mensagens de um cliente específico."""
        return db.query(Mensagem)\
            .filter(
                Mensagem.sessao_id == sessao_id,
                Mensagem.telefone_cliente == telefone_cliente
            )\
            .order_by(Mensagem.criado_em.desc())\
            .limit(limite)\
            .all()

    @staticmethod
    def obter_por_id(db: Session, mensagem_id: int) -> Optional[Mensagem]:
        """Obtém uma mensagem pelo ID."""
        return db.query(Mensagem).filter(Mensagem.id == mensagem_id).first()

    @staticmethod
    def criar(db: Session, mensagem: MensagemCriar) -> Mensagem:
        """Cria uma nova mensagem."""
        db_mensagem = Mensagem(**mensagem.model_dump())
        db.add(db_mensagem)
        db.commit()
        db.refresh(db_mensagem)
        return db_mensagem

    @staticmethod
    def salvar_imagem(imagem_bytes: bytes, telefone: str, sessao_id: int) -> tuple[str, str]:
        """
        Salva uma imagem localmente e retorna o caminho e base64.
        
        Returns:
            tuple: (caminho_arquivo, base64_string)
        """
        # Criar diretório se não existir
        upload_dir = Path("./uploads") / f"sessao_{sessao_id}" / telefone
        upload_dir.mkdir(parents=True, exist_ok=True)
        
        # Gerar nome único para arquivo
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"img_{timestamp}.jpg"
        filepath = upload_dir / filename
        
        # Salvar imagem
        try:
            # Abrir e converter para RGB (caso seja RGBA)
            img = Image.open(io.BytesIO(imagem_bytes))
            if img.mode in ('RGBA', 'LA', 'P'):
                img = img.convert('RGB')
            
            # Salvar
            img.save(filepath, 'JPEG', quality=85)
            
            # Converter para base64
            base64_string = base64.b64encode(imagem_bytes).decode('utf-8')
            
            return str(filepath), base64_string
        except Exception as e:
            print(f"Erro ao salvar imagem: {e}")
            return None, None

    @staticmethod
    async def processar_mensagem_recebida(
        db: Session,
        sessao_id: int,
        event: MessageEv
    ):
        """
        Processa uma mensagem recebida do WhatsApp.
        """
        from sessao.sessao_service import SessaoService
        from agente.agente_service import AgenteService
        from agente.intencao_service import IntencaoService
        
        # Obter informações da mensagem
        message = event.Message
        info = event.Info
        
        # Extrair dados do sender
        sender_jid = info.MessageSource.Sender
        # Converter JID protobuf para string
        if hasattr(sender_jid, 'User'):
            telefone_cliente = sender_jid.User
        else:
            telefone_cliente = str(sender_jid).split('@')[0] if '@' in str(sender_jid) else str(sender_jid)
        
        # Obter sessão
        sessao = SessaoService.obter_por_id(db, sessao_id)
        if not sessao or not sessao.ativa:
            return
        
        # Criar registro de mensagem
        db_mensagem = Mensagem(
            sessao_id=sessao_id,
            telefone_cliente=telefone_cliente,
            mensagem_id_whatsapp=info.ID,
            tipo="texto",
            direcao="recebida",
            processada=False,
            respondida=False
        )
        
        # Processar conteúdo
        if hasattr(message, 'conversation') and message.conversation:
            # Mensagem de texto
            db_mensagem.conteudo_texto = message.conversation
            db_mensagem.tipo = "texto"
            print(f"📝 Mensagem de texto: {message.conversation[:50]}...")
            
            # Verificar comandos especiais
            comando = message.conversation.strip().lower()
            if comando == "#limpar":
                print(f"🧹 Comando #limpar recebido de {telefone_cliente}")
                
                # Deletar histórico de mensagens deste cliente
                mensagens_deletadas = db.query(Mensagem)\
                    .filter(
                        Mensagem.sessao_id == sessao_id,
                        Mensagem.telefone_cliente == telefone_cliente
                    )\
                    .delete()
                
                db.commit()
                print(f"✅ {mensagens_deletadas} mensagem(ns) deletada(s)")
                
                # Enviar confirmação
                from sessao.sessao_service import gerenciador_sessoes
                cliente = gerenciador_sessoes.obter_cliente(sessao_id)
                
                if cliente:
                    from neonize.utils import build_jid
                    jid = build_jid(telefone_cliente)
                    cliente.send_message(
                        jid, 
                        message="🧹 *Histórico limpo!*\n\nSeu histórico de conversas foi apagado.\nVamos começar uma nova conversa! 🆕"
                    )
                    print(f"📤 Confirmação enviada ao usuário")
                
                return  # Não processar com agente

            elif comando == "#ajuda" or comando == "#help":
                print(f"ℹ️  Comando #ajuda recebido de {telefone_cliente}")
                
                from sessao.sessao_service import gerenciador_sessoes
                cliente = gerenciador_sessoes.obter_cliente(sessao_id)
                
                if cliente:
                    from neonize.utils import build_jid
                    jid = build_jid(telefone_cliente)
                    
                    ajuda_texto = """📚 *Comandos Disponíveis:*

🤖 *#listar* - Lista todos os agentes disponíveis
🔄 *#01, #02...* - Ativa um agente específico
🧹 *#limpar* - Apaga todo o histórico de conversas
ℹ️ *#ajuda* - Mostra esta mensagem
📊 *#status* - Mostra informações da sessão

💬 Para conversar normalmente, basta enviar sua mensagem!"""
                    
                    cliente.send_message(jid, message=ajuda_texto)
                    print(f"📤 Ajuda enviada ao usuário")
                
                return  # Não processar com agente
            
            elif comando == "#status":
                print(f"📊 Comando #status recebido de {telefone_cliente}")
                
                # Contar mensagens do usuário
                total_msgs = db.query(Mensagem)\
                    .filter(
                        Mensagem.sessao_id == sessao_id,
                        Mensagem.telefone_cliente == telefone_cliente
                    )\
                    .count()
                
                from sessao.sessao_service import gerenciador_sessoes
                cliente = gerenciador_sessoes.obter_cliente(sessao_id)
                
                if cliente:
                    from neonize.utils import build_jid
                    from agente.agente_service import AgenteService
                    jid = build_jid(telefone_cliente)
                    
                    # Obter agente ativo
                    agente_nome = "Nenhum"
                    if sessao.agente_ativo_id:
                        agente_ativo = AgenteService.obter_por_id(db, sessao.agente_ativo_id)
                        if agente_ativo:
                            agente_nome = f"#{agente_ativo.codigo} - {agente_ativo.nome}"
                    
                    status_texto = f"""📊 *Status da Sessão:*

💬 Total de mensagens: {total_msgs}
✅ Sessão ativa e conectada
🤖 Agente ativo: {agente_nome}

Digite *#ajuda* para ver comandos disponíveis."""
                    
                    cliente.send_message(jid, message=status_texto)
                    print(f"📤 Status enviado ao usuário")
                
                return  # Não processar com agente    
            # Comando para listar agentes
            elif comando == "#listar":
                print(f"📋 Comando #listar recebido de {telefone_cliente}")
                
                from agente.agente_service import AgenteService
                agentes = AgenteService.listar_por_sessao_ativos(db, sessao_id)
                
                from sessao.sessao_service import gerenciador_sessoes
                cliente = gerenciador_sessoes.obter_cliente(sessao_id)
                
                if cliente:
                    from neonize.utils import build_jid
                    jid = build_jid(telefone_cliente)
                    
                    if agentes:
                        lista_texto = "🤖 *Agentes Disponíveis:*\n\n"
                        for agente in agentes:
                            # Marcar agente ativo
                            marcador = "✅" if sessao.agente_ativo_id == agente.id else "⚪"
                            lista_texto += f"{marcador} *#{agente.codigo}* - {agente.nome}\n"
                            if agente.descricao:
                                lista_texto += f"   _{agente.descricao}_\n"
                            lista_texto += "\n"
                        
                        lista_texto += "\n💡 *Como usar:*\n"
                        lista_texto += "Digite *#XX* para ativar um agente\n"
                        lista_texto += "Exemplo: *#01* para ativar o agente 01"
                    else:
                        lista_texto = "⚠️ *Nenhum agente disponível*\n\n"
                        lista_texto += "Entre em contato com o administrador para configurar agentes."
                    
                    cliente.send_message(jid, message=lista_texto)
                    print(f"📤 Lista de agentes enviada ao usuário")
                
                return  # Não processar com agente
            
            # Comando para ativar agente (formato: #01, #02, etc.)
            elif comando.startswith("#") and len(comando) >= 2:
                codigo_agente = comando[1:]  # Remove o #
                print(f"🔄 Comando de troca de agente recebido: {codigo_agente}")
                
                from agente.agente_service import AgenteService
                agente = AgenteService.obter_por_codigo(db, sessao_id, codigo_agente)
                
                from sessao.sessao_service import gerenciador_sessoes
                cliente = gerenciador_sessoes.obter_cliente(sessao_id)
                
                if agente and agente.ativo:
                    # Ativar agente
                    sessao.agente_ativo_id = agente.id
                    db.commit()
                    
                    if cliente:
                        from neonize.utils import build_jid
                        jid = build_jid(telefone_cliente)
                        
                        confirmacao = f"✅ *Agente Ativado!*\n\n"
                        confirmacao += f"🤖 *{agente.nome}*\n"
                        if agente.descricao:
                            confirmacao += f"_{agente.descricao}_\n\n"
                        confirmacao += f"Agora estou pronto para ajudar como {agente.agente_papel}!"
                        
                        cliente.send_message(jid, message=confirmacao)
                        print(f"✅ Agente {agente.codigo} ativado para sessão {sessao_id}")
                    
                    return  # Não processar com agente
                elif cliente:
                    # Agente não encontrado
                    from neonize.utils import build_jid
                    jid = build_jid(telefone_cliente)
                    
                    erro_msg = f"❌ *Agente não encontrado*\n\n"
                    erro_msg += f"O código *#{codigo_agente}* não corresponde a nenhum agente ativo.\n\n"
                    erro_msg += "Digite *#listar* para ver os agentes disponíveis."
                    
                    cliente.send_message(jid, message=erro_msg)
                    print(f"⚠️ Agente {codigo_agente} não encontrado")
                    
                    return  # Não processar com agente
            

            
            
        
        elif hasattr(message, 'imageMessage') and message.imageMessage:
            # Mensagem com imagem
            db_mensagem.tipo = "imagem"
            db_mensagem.conteudo_texto = message.imageMessage.caption if hasattr(message.imageMessage, 'caption') else ""
            print(f"🖼️  Mensagem com imagem")
            
            # Baixar imagem
            try:
                from sessao.sessao_service import gerenciador_sessoes
                cliente = gerenciador_sessoes.obter_cliente(sessao_id)
                
                if cliente:
                    # Download da imagem usando download_any
                    imagem_bytes = cliente.download_any(message)
                    
                    if imagem_bytes:
                        # Salvar imagem
                        caminho, base64_str = MensagemService.salvar_imagem(
                            imagem_bytes,
                            telefone_cliente,
                            sessao_id
                        )
                        
                        if caminho:
                            db_mensagem.conteudo_imagem_path = caminho
                            db_mensagem.conteudo_imagem_base64 = base64_str
                            db_mensagem.conteudo_mime_type = message.image_message.mime_type
            except Exception as e:
                print(f"Erro ao baixar imagem: {e}")
        
        # Salvar mensagem
        db.add(db_mensagem)
        db.commit()
        db.refresh(db_mensagem)
        
        # --- Reconhecimento de Intenção ---
        if sessao.auto_responder and db_mensagem.conteudo_texto:
            intencao = await IntencaoService.reconhecer_intencao(db, db_mensagem.conteudo_texto)
            db_mensagem.intencao = intencao
            db.commit()
            print(f"👁️ Intenção reconhecida: {intencao}")

            # Se a intenção for falar com atendente, não processar com o agente
            if intencao == "falar_com_atendente":
                print("🗣️ Intenção 'falar_com_atendente'. Transferindo...")

                # Enviar mensagem de transferência
                from sessao.sessao_service import gerenciador_sessoes
                cliente = gerenciador_sessoes.obter_cliente(sessao_id)
                if cliente:
                    from neonize.utils import build_jid
                    jid = build_jid(telefone_cliente)

                    msg_transferencia = "Ok, estou te transferindo para um de nossos atendentes. Por favor, aguarde um momento. 🧑‍💻"
                    cliente.send_message(jid, message=msg_transferencia)

                    # Atualizar mensagem no banco
                    db_mensagem.resposta_texto = msg_transferencia
                    db_mensagem.respondida = True
                    db_mensagem.respondido_em = datetime.now()
                    db_mensagem.processada = True
                    db.commit()

                return # Interrompe o fluxo aqui

        # Se auto-responder está ativo, processar com agente
        if sessao.auto_responder:
            try:
                # Obter histórico de mensagens do cliente
                historico = MensagemService.listar_por_cliente(
                    db,
                    sessao_id,
                    telefone_cliente,
                    limite=10
                )
                
                # Processar com agente
                resposta = await AgenteService.processar_mensagem(
                    db,
                    sessao,
                    db_mensagem,
                    historico
                )
                
                # Atualizar mensagem com resposta
                db_mensagem.resposta_texto = resposta.get("texto")
                db_mensagem.resposta_tokens_input = resposta.get("tokens_input")
                db_mensagem.resposta_tokens_output = resposta.get("tokens_output")
                db_mensagem.resposta_tempo_ms = resposta.get("tempo_ms")
                db_mensagem.resposta_modelo = resposta.get("modelo")
                db_mensagem.ferramentas_usadas = resposta.get("ferramentas")
                db_mensagem.processada = True
                db_mensagem.processado_em = datetime.now()
                
                # Enviar resposta
                if resposta.get("texto"):
                    from sessao.sessao_service import gerenciador_sessoes
                    cliente = gerenciador_sessoes.obter_cliente(sessao_id)
                    
                    if cliente:
                        from neonize.utils import build_jid
                        jid = build_jid(telefone_cliente)
                        # Parâmetro correto: message (str ou Message object)
                        cliente.send_message(jid, message=resposta["texto"])
                        
                        db_mensagem.respondida = True
                        db_mensagem.respondido_em = datetime.now()
                
                db.commit()
                
            except Exception as e:
                print(f"Erro ao processar mensagem com agente: {e}")
                
                # Salvar erro no banco
                db_mensagem.resposta_erro = str(e)
                db_mensagem.processada = True
                db_mensagem.processado_em = datetime.now()
                
                # Enviar mensagem de erro amigável para o usuário
                try:
                    from sessao.sessao_service import gerenciador_sessoes
                    cliente = gerenciador_sessoes.obter_cliente(sessao_id)
                    
                    if cliente:
                        from neonize.utils import build_jid
                        jid = build_jid(telefone_cliente)
                        
                        # Mensagem de erro amigável
                        erro_msg = f"❌ *Erro ao processar sua mensagem*\n\n"
                        
                        # Identificar tipo de erro
                        erro_str = str(e).lower()
                        if "api key" in erro_str or "openrouter" in erro_str:
                            erro_msg += "⚙️ O sistema não está configurado corretamente.\n"
                            erro_msg += "Por favor, contate o administrador."
                        elif "timeout" in erro_str or "connection" in erro_str:
                            erro_msg += "🌐 Problema de conexão com o servidor.\n"
                            erro_msg += "Tente novamente em alguns instantes."
                        elif "rate limit" in erro_str:
                            erro_msg += "⏱️ Muitas requisições.\n"
                            erro_msg += "Aguarde um momento e tente novamente."
                        else:
                            erro_msg += f"🔧 Erro técnico: {str(e)[:100]}\n"
                            erro_msg += "Por favor, tente novamente ou contate o suporte."
                        
                        cliente.send_message(jid, message=erro_msg)
                        print(f"📤 Mensagem de erro enviada ao usuário")
                        
                        db_mensagem.respondida = True
                        db_mensagem.respondido_em = datetime.now()
                except Exception as send_error:
                    print(f"❌ Erro ao enviar mensagem de erro: {send_error}")
                
                db.commit()

    @staticmethod
    def contar_mensagens_por_sessao(db: Session, sessao_id: int) -> int:
        """Conta total de mensagens de uma sessão."""
        return db.query(Mensagem)\
            .filter(Mensagem.sessao_id == sessao_id)\
            .count()

    @staticmethod
    def contar_mensagens_por_periodo(
        db: Session,
        sessao_id: int,
        dias: int = 7
    ) -> int:
        """Conta mensagens dos últimos N dias."""
        data_inicio = datetime.now() - timedelta(days=dias)
        return db.query(Mensagem)\
            .filter(
                Mensagem.sessao_id == sessao_id,
                Mensagem.criado_em >= data_inicio
            )\
            .count()

    @staticmethod
    def obter_clientes_unicos(db: Session, sessao_id: int) -> List[str]:
        """Obtém lista de telefones únicos que enviaram mensagens."""
        result = db.query(Mensagem.telefone_cliente)\
            .filter(Mensagem.sessao_id == sessao_id)\
            .distinct()\
            .all()
        return [r[0] for r in result]
