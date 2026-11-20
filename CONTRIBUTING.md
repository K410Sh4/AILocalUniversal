# Contribuindo

O projeto está em fundação. Prefira mudanças pequenas, testáveis e documentadas.

## Fluxo

1. Discuta mudanças arquiteturais relevantes em uma issue.
2. Crie uma branch de trabalho.
3. Mantenha cada alteração focada.
4. Inclua testes para comportamento novo ou corrigido.
5. Atualize contratos e documentação quando necessário.
6. Abra Pull Request com motivação, escopo, testes e limitações.

Não envie alterações diretamente para \`main\` sem revisão.

## Padrões

- Python 3.11 ou superior.
- Tipagem em interfaces públicas.
- Erros explícitos; não ocultar falhas de backend/rede.
- Não registrar credenciais ou tokens.
- Não declarar capacidade como implementada antes de existir código e teste.
- Justificar dependências novas.

## Verificações

\`\`\`bash
python -m pytest
ruff check .
\`\`\`

Mudanças de rede exigem revisão de segurança. Descoberta de peers nunca concede autorização implícita.
