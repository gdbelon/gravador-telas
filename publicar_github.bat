@echo off
chcp 65001 > nul
echo ==============================================
echo Publicando Gravador de Telas no GitHub...
echo Repositorio: https://github.com/gdbelon/gravador-telas.git
echo ==============================================

cd /d "%~dp0"

echo.
echo [1/4] Inicializando git local...
git init

echo.
echo [2/4] Adicionando arquivos e gerando commit...
git add .
git commit -m "feat: gravador de telas web com fotos antes e depois"

echo.
echo [3/4] Configurando branch main e remote origin...
git branch -M main
git remote remove origin 2>nul
git remote add origin https://github.com/gdbelon/gravador-telas.git

echo.
echo [4/4] Enviando arquivos para o GitHub...
git push -u origin main

echo.
echo ==============================================
echo Concluido! Pressione qualquer tecla para sair.
echo ==============================================
pause
