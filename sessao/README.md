# Módulo Sessão 📱

## 📖 Visão Geral

O módulo `sessao` gerencia conexões WhatsApp usando a biblioteca Neonize. Cada sessão representa uma conta WhatsApp conectada que pode ter múltiplos agentes.

## 🎯 Objetivo

- Conectar/desconectar contas WhatsApp
- Gerenciar QR Code e pareamento
- Receber e enviar mensagens
- Alternar entre agentes
- Auto-responder mensagens
- Manter histórico de conversas

## 📂 Principais Componentes

### Model (sessao_model.py)

**Tabela: `sessoes`**

| Campo | Descrição |
|-------|-----------|
| `nome` | Nome único da sessão |
| `telefone` | Telefone conectado |
| `status` | desconectado, conectando, conectado, erro |
| `ativa` | Se está ativa |
| `auto_responder` | Responde automaticamente |
| `agente_ativo_id` | Agente atual respondendo |
| `qr_code` | QR Code para conexão |

### Service (sessao_service.py)

**Funções Principais:**
- `conectar()` - Conecta sessão via QR Code ou Pair Code
- `desconectar()` - Desconecta sessão
- `reconectar_sessao()` - Reconecta automaticamente
- `enviar_mensagem()` - Envia mensagem via WhatsApp
- `processar_mensagem_webhook()` - Processa mensagem recebida

**GerenciadorSessoes:**
- Gerencia clientes Neonize ativos
- Mantém threads de conexão
- Cache de QR Codes

## 🔄 Fluxo

```
1. Criar Sessão → status: "desconectado"
2. Conectar → Gera QR Code → status: "conectando"
3. Escanear QR → status: "conectado"
4. Mensagem recebida → Auto-responder (se ativo)
5. Processa com agente_ativo → Responde
```

## 💡 Exemplo

```python
# Conectar sessão
SessaoService.conectar(db, sessao_id)
# → Gera QR Code

# Enviar mensagem
await SessaoService.enviar_mensagem(
    db, sessao_id,
    telefone="+5511999999999",
    texto="Olá!",
    tipo="texto"
)
```

---

**Módulo:** sessao  
**Biblioteca:** Neonize (WhatsApp Web)

