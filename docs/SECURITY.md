# Segurança e privacidade

## Padrões

- Processamento local por padrão e menor privilégio.
- Nenhum segredo hardcoded ou versionado.
- Logs sem tokens, senhas ou conteúdo privado desnecessário.
- Dados do usuário permanecem sob controle local.
- Dependências novas exigem justificativa.

## Rede e Swarm (quando implementados)

1. Descoberta de peer não equivale a autorização.
2. Pareamento explícito de cada nó.
3. Autenticação antes de aceitar tarefas.
4. Transporte criptografado (TLS ou túnel seguro equivalente).
5. Limites de tempo, memória, CPU e tamanho de entrada.
6. Tarefas remotas canceláveis e auditáveis.
7. Integridade de arquivos verificada por SHA-256.
8. Shell/comandos arbitrários desabilitados por padrão.
9. Capacidades e permissões declaradas por nó.
10. Falha de autenticação nega acesso.

## Conteúdo não confiável

Documentos, páginas e dados recebidos de peers são dados não confiáveis. Não devem ser tratados como instruções privilegiadas para o agente ou sistema operacional.

## Modelo de ameaça inicial

Considerar peers desconhecidos, dispositivos comprometidos, prompt injection, arquivos adulterados, sobrecarga e exposição acidental de dados. A política deverá ser revisada antes de habilitar execução remota.


## Ingestão documental local (Fase 3)

- A ingestão é explícita: o usuário fornece um caminho; não há varredura automática do disco nem busca remota de arquivos.
- O loader aplica limites configuráveis de bytes, caracteres e páginas antes/depois da extração.
- TXT/Markdown são decodificados como UTF-8; arquivos com codificação inválida são rejeitados em vez de interpretados silenciosamente.
- PDFs são analisados localmente pelo pypdf opcional. PDFs criptografados são rejeitados; PDFs sem texto selecionável são informados. OCR não está habilitado.
- Conteúdo de documentos é dado não confiável, nunca uma instrução de sistema ou de ferramenta. O conteúdo recuperado deve ser delimitado como evidência não confiável no prompt.
- A indexação armazena texto extraído, metadados, hashes e localizadores no SQLite local. O usuário deve proteger e fazer backup do diretório de dados da aplicação.
- SHA-256 detecta alteração de conteúdo, mas não autentica autoria nem prova integridade antes da ingestão.
- A validação atual confere vínculos e offsets de citações; não é verificação semântica de alegações.
