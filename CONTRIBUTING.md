# Contribuindo

O AILocal Universal é um projeto proprietário. Mudanças devem ser pequenas,
testáveis, documentadas e acompanhadas de proveniência clara.

## Fluxo

1. Discuta mudanças arquiteturais relevantes em uma issue.
2. Crie uma branch de trabalho.
3. Mantenha cada alteração focada.
4. Inclua testes para comportamento novo ou corrigido.
5. Atualize contratos e documentação quando necessário.
6. Abra Pull Request com motivação, escopo, testes, limitações e origem de todo o material incluído.

Não envie alterações diretamente para `main` sem revisão.

## Propriedade intelectual e contribuições externas

- A licença padrão do projeto é proprietária: consulte `LICENSE` e `docs/LICENSING.md`.
- Não envie código, documentação, modelos, imagens, fontes ou outros ativos sem comprovar que você tem direito de submetê-los.
- Toda contribuição externa precisa de aprovação prévia e de um acordo escrito separado, assinado, que atribua ao titular do projeto os direitos patrimoniais transferíveis necessários para manter, modificar, integrar, licenciar e explorar comercialmente a contribuição no projeto. Direitos que a lei não permite transferir permanecem protegidos.
- Abrir uma issue, fork ou Pull Request não transfere direitos nem significa que a contribuição foi aceita.
- Dependências, trechos de código e ativos de terceiros precisam ser identificados e acompanhados de suas licenças e avisos obrigatórios.
- Não inclua pesos de modelos, datasets, conteúdo de usuário ou plugins de terceiros como se fossem propriedade do projeto.
- A aceitação de contribuições sem o acordo formal acima está suspensa.

## Padrões técnicos

- Python 3.11 ou superior.
- Tipagem em interfaces públicas.
- Erros explícitos; não ocultar falhas de backend/rede.
- Não registrar credenciais ou tokens.
- Não declarar capacidade como implementada antes de existir código e teste.
- Justificar dependências novas e informar a respectiva licença.
- Manter o inventário de licenças e avisos de terceiros atualizado.

## Verificações

```bash
python -m pytest
ruff check .
```

Mudanças de rede exigem revisão de segurança. Descoberta de peers nunca concede autorização implícita.
