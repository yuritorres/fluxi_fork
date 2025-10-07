"""
Rotas do frontend para mensagens.
"""
from fastapi import APIRouter, Depends, Request, Query
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from database import get_db
from mensagem.mensagem_service import MensagemService
from sessao.sessao_service import SessaoService

router = APIRouter(prefix="/mensagens", tags=["Frontend - Mensagens"])
templates = Jinja2Templates(directory="templates")


@router.get("/sessao/{sessao_id}", response_class=HTMLResponse)
def pagina_mensagens_sessao(
    sessao_id: int,
    request: Request,
    limite: int = Query(default=100, le=500),
    db: Session = Depends(get_db)
):
    """Página de mensagens de uma sessão."""
    sessao = SessaoService.obter_por_id(db, sessao_id)
    if not sessao:
        return templates.TemplateResponse("shared/erro.html", {
            "request": request,
            "mensagem": "Sessão não encontrada",
            "titulo": "Erro"
        })
    
    mensagens = MensagemService.listar_por_sessao(db, sessao_id, limite)
    clientes = MensagemService.obter_clientes_unicos(db, sessao_id)
    
    return templates.TemplateResponse("mensagens.html", {
        "request": request,
        "sessao": sessao,
        "mensagens": mensagens,
        "clientes": clientes,
        "titulo": f"Mensagens - {sessao.nome}"
    })


@router.get("/sessao/{sessao_id}/cliente/{telefone}", response_class=HTMLResponse)
def pagina_conversa_cliente(
    sessao_id: int,
    telefone: str,
    request: Request,
    db: Session = Depends(get_db)
):
    """Página de conversa com um cliente específico."""
    sessao = SessaoService.obter_por_id(db, sessao_id)
    if not sessao:
        return templates.TemplateResponse("shared/erro.html", {
            "request": request,
            "mensagem": "Sessão não encontrada",
            "titulo": "Erro"
        })
    
    mensagens = MensagemService.listar_por_cliente(db, sessao_id, telefone, limite=100)
    
    return templates.TemplateResponse("conversa.html", {
        "request": request,
        "sessao": sessao,
        "telefone_cliente": telefone,
        "mensagens": mensagens,
        "titulo": f"Conversa com {telefone}"
    })
