"""
Services package for Knowledge module.
"""

from app.modules.knowledge.services.knowledge_service import (
    KNOWLEDGE_COLLECTION,
    KNOWLEDGE_SEED,
    KnowledgeService,
    get_knowledge_service,
)

__all__ = [
    "KNOWLEDGE_COLLECTION",
    "KNOWLEDGE_SEED",
    "KnowledgeService",
    "get_knowledge_service",
]