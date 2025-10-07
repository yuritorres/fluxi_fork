#!/bin/bash

# Script para testar a configuração Docker do Fluxi
echo "🧪 Testando configuração Docker do Fluxi..."

# Verificar se os diretórios existem
echo "📁 Verificando diretórios..."
if [ -d "data" ]; then
    echo "✅ Diretório data existe"
    ls -la data/
else
    echo "❌ Diretório data não existe"
fi

if [ -d "uploads" ]; then
    echo "✅ Diretório uploads existe"
else
    echo "❌ Diretório uploads não existe"
fi

if [ -d "sessoes" ]; then
    echo "✅ Diretório sessoes existe"
else
    echo "❌ Diretório sessoes não existe"
fi

if [ -d "rags" ]; then
    echo "✅ Diretório rags existe"
else
    echo "❌ Diretório rags não existe"
fi

# Verificar permissões
echo ""
echo "🔐 Verificando permissões..."
ls -la | grep -E "(data|uploads|sessoes|rags)"

# Testar se o container consegue acessar os diretórios
echo ""
echo "🐳 Testando acesso do container..."
docker-compose exec fluxi ls -la /app/data 2>/dev/null || echo "❌ Container não consegue acessar /app/data"

echo ""
echo "✅ Teste concluído!"
