"""Erros explícitos da camada de conhecimento."""


class KnowledgeError(Exception):
    """Erro-base da camada de conhecimento."""


class DocumentLoadError(KnowledgeError):
    """Não foi possível ler ou extrair um documento."""


class UnsupportedDocumentError(DocumentLoadError):
    """Formato de documento não suportado."""


class MissingOptionalDependencyError(DocumentLoadError):
    """Uma dependência opcional necessária não está instalada."""


class EmptyDocumentError(DocumentLoadError):
    """O documento não contém texto selecionável."""


class KnowledgeIndexError(KnowledgeError):
    """Falha no armazenamento ou na pesquisa do índice."""


class EmbeddingError(KnowledgeError):
    """Falha na geração, validação ou leitura de embeddings."""
