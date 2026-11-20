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
