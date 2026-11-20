# Exemplo de pacote NeuralInjector

Este diretório contém arquivos-fonte ilustrativos para demonstrar a estrutura prevista pela NIP 0.1.0.

**Este diretório não é, por si só, um arquivo .neuralinjector instalável.** O pacote final deve ser montado em ZIP64, incluir todos os caminhos referenciados no manifesto e gerar o arquivo `security/checksums.sha256` depois que os arquivos finais estiverem definidos.

## Conteúdo

- `manifest.example.json`: manifesto de referência.
- `plugins/pt-br/`: plugin de regras para português brasileiro.
- `plugins/programming/`: plugin de regras para programação.
- `hardware/profiles/balanced.json`: perfil declarativo e não vinculado a um hardware específico.
- `evaluations/smoke.jsonl`: exemplos mínimos de avaliação.

O exemplo não contém adaptadores de pesos, poda, deltas de restauração ou código executável. Esses componentes só devem ser incluídos quando houver artefatos reais, compatibilidade declarada e um backend capaz de aplicá-los.

## Licença deste exemplo

Os manifestos, regras, workflow declarativo, perfis, avaliações e demais materiais originais deste exemplo são disponibilizados sob `LicenseRef-AILocal-Universal-Proprietary`, conforme o arquivo `LICENSE` na raiz do repositório. O exemplo não concede uma licença aberta para os componentes originais. Modelos mencionados são apenas referências de compatibilidade e não estão incluídos nem licenciados por este exemplo.

Pacotes ou plugins criados por usuários/terceiros devem substituir autoria e licença pelos dados reais de seus próprios materiais, sem reutilizar a licença proprietária por padrão.
