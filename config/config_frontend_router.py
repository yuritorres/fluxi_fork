"""
Rotas do frontend para configurações.
"""
from fastapi import APIRouter, Depends, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from database import get_db
from config.config_service import ConfiguracaoService

router = APIRouter(prefix="/configuracoes", tags=["Frontend - Configurações"])
templates = Jinja2Templates(directory="templates")


@router.get("/", response_class=HTMLResponse)
def pagina_configuracoes(request: Request, db: Session = Depends(get_db)):
    """Página de configurações do sistema."""
    # Buscar configurações por categoria
    config_openrouter = ConfiguracaoService.listar_por_categoria(db, "openrouter")
    config_agente = ConfiguracaoService.listar_por_categoria(db, "agente")
    config_geral = ConfiguracaoService.listar_por_categoria(db, "geral")
    config_llm = ConfiguracaoService.listar_por_categoria(db, "llm")
    
    return templates.TemplateResponse("config/settings.html", {
        "request": request,
        "config_openrouter": config_openrouter,
        "config_agente": config_agente,
        "config_geral": config_geral,
        "config_llm": config_llm,
        "titulo": "Configurações do Sistema"
    })


@router.post("/salvar-openrouter")
async def salvar_openrouter(
    request: Request,
    api_key: str = Form(...),
    modelo_padrao: str = Form(...),
    acao: str = Form(...),
    db: Session = Depends(get_db)
):
    """Salva configurações do OpenRouter."""
    if acao == "testar":
        # Testar conexão
        resultado = await ConfiguracaoService.testar_conexao_openrouter(db, api_key)
        # Redirecionar com mensagem
        return RedirectResponse(url="/configuracoes", status_code=303)
    else:
        # Salvar configurações
        ConfiguracaoService.definir_valor(db, "openrouter_api_key", api_key)
        ConfiguracaoService.definir_valor(db, "openrouter_modelo_padrao", modelo_padrao)
        return RedirectResponse(url="/configuracoes", status_code=303)


@router.post("/salvar-parametros-llm")
def salvar_parametros_llm(
    temperatura: float = Form(...),
    max_tokens: int = Form(...),
    top_p: float = Form(...),
    db: Session = Depends(get_db)
):
    """Salva parâmetros LLM."""
    ConfiguracaoService.definir_valor(db, "openrouter_temperatura", str(temperatura))
    ConfiguracaoService.definir_valor(db, "openrouter_max_tokens", str(max_tokens))
    ConfiguracaoService.definir_valor(db, "openrouter_top_p", str(top_p))
    return RedirectResponse(url="/configuracoes", status_code=303)


@router.post("/salvar-agente")
def salvar_agente(
    papel: str = Form(...),
    objetivo: str = Form(...),
    politicas: str = Form(...),
    tarefa: str = Form(...),
    objetivo_explicito: str = Form(...),
    publico: str = Form(...),
    restricoes: str = Form(...),
    db: Session = Depends(get_db)
):
    """Salva configurações do agente."""
    ConfiguracaoService.definir_valor(db, "agente_papel_padrao", papel)
    ConfiguracaoService.definir_valor(db, "agente_objetivo_padrao", objetivo)
    ConfiguracaoService.definir_valor(db, "agente_politicas_padrao", politicas)
    ConfiguracaoService.definir_valor(db, "agente_tarefa_padrao", tarefa)
    ConfiguracaoService.definir_valor(db, "agente_objetivo_explicito_padrao", objetivo_explicito)
    ConfiguracaoService.definir_valor(db, "agente_publico_padrao", publico)
    ConfiguracaoService.definir_valor(db, "agente_restricoes_padrao", restricoes)
    return RedirectResponse(url="/configuracoes", status_code=303)


@router.post("/salvar-geral")
def salvar_geral(
    diretorio_uploads: str = Form(...),
    max_tamanho_imagem_mb: int = Form(...),
    db: Session = Depends(get_db)
):
    """Salva configurações gerais."""
    ConfiguracaoService.definir_valor(db, "sistema_diretorio_uploads", diretorio_uploads)
    ConfiguracaoService.definir_valor(db, "sistema_max_tamanho_imagem_mb", str(max_tamanho_imagem_mb))
    return RedirectResponse(url="/configuracoes", status_code=303)


@router.post("/salvar-provedores-llm")
def salvar_provedores_llm(
    provedor_padrao: str = Form(...),
    fallback_openrouter: bool = Form(False),
    db: Session = Depends(get_db)
):
    """Salva configurações de provedores LLM."""
    ConfiguracaoService.definir_valor(db, "llm_provedor_padrao", provedor_padrao)
    ConfiguracaoService.definir_valor(db, "llm_fallback_openrouter", str(fallback_openrouter).lower())
    return RedirectResponse(url="/configuracoes", status_code=303)
