# FinTrack Advanced — instalador Windows

## Criar instalador profissional

1. Instale Python 3.11 ou 3.12 para Windows (com Python Launcher `py`).
2. Instale **Inno Setup 6** em https://jrsoftware.org/isinfo.php.
3. Extraia o ZIP no Windows e execute **gerar_instalador.bat**.
4. O arquivo final estará em `instalador\FinTrackAdvanced_Setup.exe`. Envie **somente esse EXE** ao cliente.

O script instala as dependências de desenvolvimento, gera o executável com o ícone `FinTrackAdvanced.ico` e compila o instalador. O cliente não precisa de Python nem VS Code. O Windows do cliente precisa de Microsoft Edge WebView2 Runtime.

O instalador cria entrada no menu Iniciar e oferece atalho na área de trabalho. Não precisa de privilégios de administrador. O banco fica em `%LOCALAPPDATA%\FinTrackAdvanced\fintrack.db`, fora da pasta do aplicativo. Faça backup antes de atualizações.

## Importante

Este pacote contém o código e o processo de compilação, **não** um instalador EXE pronto: a compilação deve acontecer no Windows. Teste no computador de destino antes de vender. A assinatura digital do instalador não está incluída; o Windows pode exibir alertas de reputação. A integração Open Finance ainda não está ativa, e a IA remota requer configuração de chave e acesso à internet.
