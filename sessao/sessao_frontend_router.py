"""
Rotas do frontend para sessões.
"""
from fastapi import APIRouter, Depends, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from database import get_db
from sessao.sessao_service import SessaoService
from sessao.sessao_schema import SessaoCriar, SessaoAtualizar
from config.config_service import ConfiguracaoService

router = APIRouter(prefix="/sessoes", tags=["Frontend - Sessões"])
templates = Jinja2Templates(directory="templates")


@router.get("/", response_class=HTMLResponse)
def pagina_sessoes(request: Request, db: Session = Depends(get_db)):
    """Página de listagem de sessões."""
    sessoes = SessaoService.listar_todas(db)
    
    return templates.TemplateResponse("sessao/lista.html", {
        "request": request,
        "sessoes": sessoes,
        "titulo": "Sessões WhatsApp"
    })


@router.get("/nova", response_class=HTMLResponse)
def pagina_nova_sessao(request: Request, db: Session = Depends(get_db)):
    """Página para criar nova sessão."""
    # Buscar configurações padrão do agente
    config_agente = {
        "papel": ConfiguracaoService.obter_valor(db, "agente_papel_padrao", "assistente pessoal"),
        "objetivo": ConfiguracaoService.obter_valor(db, "agente_objetivo_padrao", "ajudar o usuário"),
        "politicas": ConfiguracaoService.obter_valor(db, "agente_politicas_padrao", "ser educado e respeitoso"),
        "tarefa": ConfiguracaoService.obter_valor(db, "agente_tarefa_padrao", "responder perguntas"),
        "objetivo_explicito": ConfiguracaoService.obter_valor(db, "agente_objetivo_explicito_padrao", "fornecer informações úteis"),
        "publico": ConfiguracaoService.obter_valor(db, "agente_publico_padrao", "usuários em geral"),
        "restricoes": ConfiguracaoService.obter_valor(db, "agente_restricoes_padrao", "responder em português")
    }
    
    # Buscar configurações LLM
    modelo_padrao = ConfiguracaoService.obter_valor(db, "openrouter_modelo_padrao", "google/gemini-2.0-flash-001")
    temperatura_padrao = ConfiguracaoService.obter_valor(db, "openrouter_temperatura", "0.7")
    max_tokens_padrao = ConfiguracaoService.obter_valor(db, "openrouter_max_tokens", "2000")
    top_p_padrao = ConfiguracaoService.obter_valor(db, "openrouter_top_p", "1.0")
    
    return templates.TemplateResponse("sessao/form.html", {
        "request": request,
        "config_agente": config_agente,
        "modelo_padrao": modelo_padrao,
        "temperatura_padrao": temperatura_padrao,
        "max_tokens_padrao": max_tokens_padrao,
        "top_p_padrao": top_p_padrao,
        "titulo": "Nova Sessão",
        "acao": "criar"
    })


@router.get("/{sessao_id}/editar", response_class=HTMLResponse)
def pagina_editar_sessao(sessao_id: int, request: Request, db: Session = Depends(get_db)):
    """Página para editar sessão."""
    sessao = SessaoService.obter_por_id(db, sessao_id)
    if not sessao:
        return templates.TemplateResponse("shared/erro.html", {
            "request": request,
            "mensagem": "Sessão não encontrada",
            "titulo": "Erro"
        })
    
    return templates.TemplateResponse("sessao/form.html", {
        "request": request,
        "sessao": sessao,
        "titulo": f"Editar Sessão - {sessao.nome}",
        "acao": "editar"
    })


@router.get("/{sessao_id}/detalhes", response_class=HTMLResponse)
def pagina_detalhes_sessao(sessao_id: int, request: Request, db: Session = Depends(get_db)):
    """Página de detalhes da sessão."""
    sessao = SessaoService.obter_por_id(db, sessao_id)
    if not sessao:
        return templates.TemplateResponse("shared/erro.html", {
            "request": request,
            "mensagem": "Sessão não encontrada",
            "titulo": "Erro"
        })
    
    return templates.TemplateResponse("sessao/detalhes.html", {
        "request": request,
        "sessao": sessao,
        "titulo": f"Detalhes - {sessao.nome}"
    })


@router.get("/{sessao_id}/conectar", response_class=HTMLResponse)
def pagina_conectar_sessao(sessao_id: int, request: Request, db: Session = Depends(get_db)):
    """Página para conectar sessão via QR Code."""
    from datetime import datetime, timedelta
    
    sessao = SessaoService.obter_por_id(db, sessao_id)
    if not sessao:
        return templates.TemplateResponse("shared/erro.html", {
            "request": request,
            "mensagem": "Sessão não encontrada",
            "titulo": "Erro"
        })
    
    # Verificar se QR Code expirou (60 segundos)
    qr_code_expirado = False
    if sessao.qr_code and sessao.qr_code_gerado_em:
        tempo_decorrido = datetime.now() - sessao.qr_code_gerado_em
        if tempo_decorrido > timedelta(seconds=60):
            qr_code_expirado = True
            print(f"⏰ QR Code expirado para sessão {sessao_id} ({tempo_decorrido.seconds}s)")
            # Limpar QR Code expirado
            sessao.qr_code = None
            sessao.status = "desconectado"
    
    # Verificar se há QR Code no gerenciador (sempre prioritário)
    from sessao.sessao_service import gerenciador_sessoes
    qr_code_gerenciador = gerenciador_sessoes.qr_codes.get(sessao_id)
    if qr_code_gerenciador and not qr_code_expirado:
        # Sempre usar QR Code do gerenciador (mais recente)
        sessao.qr_code = qr_code_gerenciador
        print(f"🔄 QR Code do gerenciador aplicado à sessão {sessao_id} ({len(qr_code_gerenciador)} chars)")
    
    return templates.TemplateResponse("sessao/paircode.html", {
        "request": request,
        "sessao": sessao,
        "qr_code_expirado": qr_code_expirado,
        "titulo": f"Conectar - {sessao.nome}"
    })


@router.post("/{sessao_id}/conectar")
def conectar_sessao_post(
    sessao_id: int,
    db: Session = Depends(get_db)
):
    """Conecta uma sessão WhatsApp via QR Code."""
    try:
        # Limpar QR Code antigo antes de gerar novo
        sessao = SessaoService.obter_por_id(db, sessao_id)
        if sessao:
            sessao.qr_code = None
            sessao.qr_code_gerado_em = None
            db.commit()
            print(f"🧹 QR Code antigo limpo para sessão {sessao_id}")
        
        SessaoService.conectar(db, sessao_id, usar_paircode=False)
    except Exception as e:
        print(f"Erro ao conectar: {e}")
    return RedirectResponse(url=f"/sessoes/{sessao_id}/conectar", status_code=303)


@router.post("/{sessao_id}/desconectar")
def desconectar_sessao_post(sessao_id: int, db: Session = Depends(get_db)):
    """Desconecta uma sessão WhatsApp."""
    try:
        SessaoService.desconectar(db, sessao_id)
    except Exception as e:
        print(f"Erro ao desconectar: {e}")
    return RedirectResponse(url="/sessoes", status_code=303)


@router.post("/{sessao_id}/deletar")
def deletar_sessao_post(sessao_id: int, db: Session = Depends(get_db)):
    """Deleta uma sessão WhatsApp."""
    try:
        SessaoService.deletar(db, sessao_id)
        print(f"✅ Sessão {sessao_id} deletada com sucesso")
    except Exception as e:
        print(f"Erro ao deletar: {e}")
    return RedirectResponse(url="/sessoes", status_code=303)


@router.post("/criar")
def criar_sessao_post(
    nome: str = Form(...),
    agente_papel: str = Form(...),
    agente_objetivo: str = Form(...),
    agente_politicas: str = Form(...),
    agente_tarefa: str = Form(...),
    agente_objetivo_explicito: str = Form(...),
    agente_publico: str = Form(...),
    agente_restricoes: str = Form(...),
    modelo_llm: str = Form(None),
    temperatura: str = Form(None),
    max_tokens: str = Form(None),
    top_p: str = Form(None),
    auto_responder: str = Form(None),
    salvar_historico: str = Form(None),
    db: Session = Depends(get_db)
):
    """Cria uma nova sessão via formulário."""
    try:
        # Converter checkboxes
        auto_responder_bool = auto_responder == "true"
        salvar_historico_bool = salvar_historico == "true"
        
        # Criar sessão
        sessao_data = SessaoCriar(
            nome=nome,
            agente_papel=agente_papel,
            agente_objetivo=agente_objetivo,
            agente_politicas=agente_politicas,
            agente_tarefa=agente_tarefa,
            agente_objetivo_explicito=agente_objetivo_explicito,
            agente_publico=agente_publico,
            agente_restricoes=agente_restricoes,
            modelo_llm=modelo_llm if modelo_llm else None,
            temperatura=temperatura if temperatura else None,
            max_tokens=max_tokens if max_tokens else None,
            top_p=top_p if top_p else None,
            auto_responder=auto_responder_bool,
            salvar_historico=salvar_historico_bool
        )
        
        SessaoService.criar(db, sessao_data)
        return RedirectResponse(url="/sessoes", status_code=303)
    except ValueError as e:
        return RedirectResponse(url=f"/sessoes/nova?erro={str(e)}", status_code=303)


@router.post("/{sessao_id}/atualizar")
def atualizar_sessao_post(
    sessao_id: int,
    nome: str = Form(None),
    agente_papel: str = Form(None),
    agente_objetivo: str = Form(None),
    agente_politicas: str = Form(None),
    agente_tarefa: str = Form(None),
    agente_objetivo_explicito: str = Form(None),
    agente_publico: str = Form(None),
    agente_restricoes: str = Form(None),
    modelo_llm: str = Form(None),
    temperatura: str = Form(None),
    max_tokens: str = Form(None),
    top_p: str = Form(None),
    auto_responder: str = Form(None),
    salvar_historico: str = Form(None),
    ativa: str = Form(None),
    db: Session = Depends(get_db)
):
    """Atualiza uma sessão via formulário."""
    try:
        # Preparar dados de atualização
        update_data = {}
        
        if nome:
            update_data["nome"] = nome
        if agente_papel:
            update_data["agente_papel"] = agente_papel
        if agente_objetivo:
            update_data["agente_objetivo"] = agente_objetivo
        if agente_politicas:
            update_data["agente_politicas"] = agente_politicas
        if agente_tarefa:
            update_data["agente_tarefa"] = agente_tarefa
        if agente_objetivo_explicito:
            update_data["agente_objetivo_explicito"] = agente_objetivo_explicito
        if agente_publico:
            update_data["agente_publico"] = agente_publico
        if agente_restricoes:
            update_data["agente_restricoes"] = agente_restricoes
        if modelo_llm:
            update_data["modelo_llm"] = modelo_llm
        if temperatura:
            update_data["temperatura"] = temperatura
        if max_tokens:
            update_data["max_tokens"] = max_tokens
        if top_p:
            update_data["top_p"] = top_p
        if auto_responder is not None:
            update_data["auto_responder"] = auto_responder == "true"
        if salvar_historico is not None:
            update_data["salvar_historico"] = salvar_historico == "true"
        if ativa is not None:
            update_data["ativa"] = ativa == "true"
        
        sessao_atualizar = SessaoAtualizar(**update_data)
        SessaoService.atualizar(db, sessao_id, sessao_atualizar)
        
        return RedirectResponse(url=f"/sessoes/{sessao_id}/detalhes", status_code=303)
    except Exception as e:
        return RedirectResponse(url=f"/sessoes/{sessao_id}/editar?erro={str(e)}", status_code=303)
