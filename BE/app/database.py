"""Async PostgreSQL data-access facade used by the public API service."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Optional

import bcrypt
from sqlalchemy import DateTime, delete, func, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.db_models import (
    ChatMessage,
    Department,
    Document,
    DocumentChunk,
    Organization,
    Repository,
    RepositoryCategory,
    User,
)

logger = logging.getLogger(__name__)

engine = create_async_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


def _uuid(value: str | uuid.UUID | None) -> uuid.UUID | None:
    if value in (None, ""):
        return None
    return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))


def _dict(obj: Any) -> Optional[dict]:
    if obj is None:
        return None
    result: dict[str, Any] = {}
    for column in obj.__table__.columns:
        value = getattr(obj, column.name)
        result[column.name] = str(value) if isinstance(value, uuid.UUID) else value
    return result


def _coerce_datetime(value: Any) -> Any:
    if isinstance(value, str):
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    return value


def _json_safe(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    return value


async def get_db() -> AsyncSession:
    return SessionLocal()


async def _get(model, object_id: str) -> Optional[dict]:
    async with SessionLocal() as session:
        return _dict(await session.get(model, _uuid(object_id)))


async def _delete(model, object_id: str) -> None:
    async with SessionLocal.begin() as session:
        await session.execute(delete(model).where(model.id == _uuid(object_id)))


async def _update(model, object_id: str, values: dict) -> Optional[dict]:
    allowed = {column.name for column in model.__table__.columns}
    clean = {key: value for key, value in values.items() if key in allowed and value is not None}
    for key in ("org_id", "dept_id", "category_id", "user_id", "repository_id", "template_id", "repo_id"):
        if key in clean:
            clean[key] = _uuid(clean[key])
    for column in model.__table__.columns:
        if column.name in clean and isinstance(column.type, DateTime):
            clean[column.name] = _coerce_datetime(clean[column.name])
    if "updated_at" in allowed:
        clean["updated_at"] = datetime.now(timezone.utc)
    async with SessionLocal.begin() as session:
        obj = await session.get(model, _uuid(object_id))
        if not obj:
            return None
        for key, value in clean.items():
            setattr(obj, key, value)
        await session.flush()
        return _dict(obj)


async def init_db() -> None:
    """Verify connectivity and idempotently seed the initial system admin."""
    async with engine.connect() as connection:
        await connection.execute(text("SELECT 1"))
    if not settings.admin_username or not settings.admin_password:
        raise RuntimeError("ADMIN_USERNAME and ADMIN_PASSWORD are required")
    async with SessionLocal.begin() as session:
        existing = await session.scalar(select(User).where(User.username == settings.admin_username))
        if existing is None:
            password_hash = bcrypt.hashpw(
                settings.admin_password.encode("utf-8"), bcrypt.gensalt()
            ).decode("utf-8")
            session.add(
                User(
                    username=settings.admin_username,
                    password_hash=password_hash,
                    full_name=settings.admin_full_name,
                    role="system_admin",
                )
            )
            logger.info("Seeded initial system administrator '%s'", settings.admin_username)


# Users
async def create_user(
    username: str,
    password_hash: str,
    full_name: str = "",
    role: str = "user",
    org_id: str = None,
    dept_id: str = None,
    ai_engine: str = None,
) -> dict:
    async with SessionLocal.begin() as session:
        obj = User(
            username=username,
            password_hash=password_hash,
            full_name=full_name,
            role=role,
            org_id=_uuid(org_id),
            dept_id=_uuid(dept_id),
            ai_engine=ai_engine,
        )
        session.add(obj)
        await session.flush()
        return _dict(obj)


async def get_user_by_username(username: str) -> Optional[dict]:
    async with SessionLocal() as session:
        return _dict(await session.scalar(select(User).where(User.username == username)))


async def get_user_by_id(user_id: str) -> Optional[dict]:
    return await _get(User, user_id)


async def get_users_by_org(org_id: str) -> list[dict]:
    async with SessionLocal() as session:
        rows = (await session.scalars(
            select(User).where(User.org_id == _uuid(org_id)).order_by(User.created_at.desc())
        )).all()
        return [_dict(row) for row in rows]


async def get_all_users() -> list[dict]:
    async with SessionLocal() as session:
        return [_dict(row) for row in (await session.scalars(select(User).order_by(User.created_at.desc()))).all()]


async def update_user(user_id: str, **kwargs) -> Optional[dict]:
    return await _update(User, user_id, kwargs)


async def delete_user(user_id: str) -> None:
    await _delete(User, user_id)


# Repository categories
async def create_repository_category(
    user_id: str, name: str, description: str = "", is_public: bool = False
) -> dict:
    async with SessionLocal.begin() as session:
        obj = RepositoryCategory(
            user_id=_uuid(user_id), name=name, description=description, is_public=is_public
        )
        session.add(obj)
        await session.flush()
        return _dict(obj)


async def get_repository_categories_by_user(user_id: str) -> list[dict]:
    async with SessionLocal() as session:
        rows = (await session.scalars(
            select(RepositoryCategory)
            .where(RepositoryCategory.user_id == _uuid(user_id))
            .order_by(RepositoryCategory.updated_at.desc())
        )).all()
        return [_dict(row) for row in rows]


async def get_shared_repository_categories(org_id: str, exclude_user_id: str) -> list[dict]:
    async with SessionLocal() as session:
        rows = (await session.scalars(
            select(RepositoryCategory)
            .join(User, User.id == RepositoryCategory.user_id)
            .where(
                User.org_id == _uuid(org_id),
                RepositoryCategory.user_id != _uuid(exclude_user_id),
                RepositoryCategory.is_public.is_(True),
            )
            .order_by(RepositoryCategory.updated_at.desc())
        )).all()
        return [_dict(row) for row in rows]


async def get_repository_category_by_id(category_id: str) -> Optional[dict]:
    return await _get(RepositoryCategory, category_id)


async def update_repository_category(
    category_id: str, name: str = None, description: str = None, is_public: bool = None
) -> Optional[dict]:
    return await _update(
        RepositoryCategory,
        category_id,
        {"name": name, "description": description, "is_public": is_public},
    )


async def delete_repository_category(category_id: str) -> None:
    await _delete(RepositoryCategory, category_id)


# Repositories
async def create_repository(
    user_id: str,
    name: str,
    description: str = "",
    notebook_id: str = None,
    is_public: bool = False,
    notebooklm_session_fingerprint: str = None,
    category_id: str = None,
) -> dict:
    async with SessionLocal.begin() as session:
        obj = Repository(
            user_id=_uuid(user_id),
            name=name,
            description=description,
            notebook_id=notebook_id,
            is_public=is_public,
            notebooklm_session_fingerprint=notebooklm_session_fingerprint,
            category_id=_uuid(category_id),
        )
        session.add(obj)
        await session.flush()
        return _dict(obj)


async def get_repositories_by_user(user_id: str) -> list[dict]:
    async with SessionLocal() as session:
        rows = (await session.scalars(
            select(Repository)
            .where(Repository.user_id == _uuid(user_id))
            .order_by(Repository.last_used_at.desc())
        )).all()
        return [_dict(row) for row in rows]


async def get_repository_by_id(repo_id: str) -> Optional[dict]:
    return await _get(Repository, repo_id)


async def touch_repository(repo_id: str) -> None:
    await _update(Repository, repo_id, {"last_used_at": datetime.now(timezone.utc)})


async def count_active_notebooklm_repositories(session_fingerprint: str = "") -> int:
    async with SessionLocal() as session:
        conditions = [Repository.notebook_id.is_not(None)]
        if session_fingerprint:
            conditions.append(Repository.notebooklm_session_fingerprint == session_fingerprint)
        return int(await session.scalar(select(func.count()).select_from(Repository).where(*conditions)) or 0)


async def get_notebooklm_eviction_candidate(
    session_fingerprint: str = "", exclude_repo_id: str = ""
) -> Optional[dict]:
    async with SessionLocal() as session:
        conditions = [Repository.notebook_id.is_not(None)]
        if session_fingerprint:
            conditions.append(Repository.notebooklm_session_fingerprint == session_fingerprint)
        if exclude_repo_id:
            conditions.append(Repository.id != _uuid(exclude_repo_id))
        obj = await session.scalar(
            select(Repository).where(*conditions).order_by(Repository.last_used_at.asc()).limit(1)
        )
        return _dict(obj)


async def clear_repository_document_source_ids(repository_id: str) -> None:
    async with SessionLocal.begin() as session:
        await session.execute(
            update(Document)
            .where(Document.repository_id == _uuid(repository_id))
            .values(notebooklm_source_id=None)
        )


async def count_user_repositories(user_id: str) -> int:
    async with SessionLocal() as session:
        return int(await session.scalar(
            select(func.count()).select_from(Repository).where(Repository.user_id == _uuid(user_id))
        ) or 0)


async def update_repository(
    repo_id: str,
    name: str = None,
    description: str = None,
    is_public: bool = None,
    category_id: str = None,
    **kwargs,
) -> Optional[dict]:
    values = {"name": name, "description": description, "is_public": is_public, **kwargs}
    if category_id is not None:
        values["category_id"] = category_id
    return await _update(Repository, repo_id, values)


async def set_repository_notebooklm_state(
    repo_id: str, notebook_id: str | None, session_fingerprint: str | None
) -> Optional[dict]:
    async with SessionLocal.begin() as session:
        obj = await session.get(Repository, _uuid(repo_id))
        if not obj:
            return None
        obj.notebook_id = notebook_id
        obj.notebooklm_session_fingerprint = session_fingerprint
        obj.last_used_at = datetime.now(timezone.utc)
        await session.flush()
        return _dict(obj)


async def delete_repository(repo_id: str) -> None:
    await _delete(Repository, repo_id)


async def get_shared_repositories(org_id: str, exclude_user_id: str) -> list[dict]:
    async with SessionLocal() as session:
        rows = (await session.scalars(
            select(Repository)
            .join(User, User.id == Repository.user_id)
            .where(
                User.org_id == _uuid(org_id),
                Repository.user_id != _uuid(exclude_user_id),
                Repository.is_public.is_(True),
            )
            .order_by(Repository.last_used_at.desc())
        )).all()
        return [_dict(row) for row in rows]


# Documents
async def create_document(
    repository_id: str,
    filename: str,
    stored_path: str,
    file_size: int = 0,
    file_type: str = "",
    notebooklm_source_id: str = None,
    doc_id: str = None,
    **kwargs,
) -> dict:
    async with SessionLocal.begin() as session:
        obj = Document(
            id=_uuid(doc_id) or uuid.uuid4(),
            repository_id=_uuid(repository_id),
            filename=filename,
            stored_path=stored_path,
            folder_key=kwargs.pop("folder_key", "draft"),
            file_size=file_size,
            file_type=file_type,
            notebooklm_source_id=notebooklm_source_id,
            **{key: value for key, value in kwargs.items() if hasattr(Document, key)},
        )
        session.add(obj)
        await session.flush()
        return _dict(obj)


async def get_documents_by_repository(repository_id: str) -> list[dict]:
    async with SessionLocal() as session:
        rows = (await session.scalars(
            select(Document)
            .where(Document.repository_id == _uuid(repository_id))
            .order_by(Document.uploaded_at.desc())
        )).all()
        return [_dict(row) for row in rows]


async def get_user_total_document_bytes(user_id: str) -> int:
    async with SessionLocal() as session:
        value = await session.scalar(
            select(func.coalesce(func.sum(Document.file_size), 0))
            .join(Repository, Repository.id == Document.repository_id)
            .where(Repository.user_id == _uuid(user_id))
        )
        return int(value or 0)


async def get_document_by_id(doc_id: str) -> Optional[dict]:
    return await _get(Document, doc_id)


async def update_document_source_id(doc_id: str, source_id: str) -> None:
    await _update(Document, doc_id, {"notebooklm_source_id": source_id})


async def update_document_file(
    doc_id: str,
    filename: str,
    stored_path: str,
    file_size: int,
    file_type: str = "",
) -> Optional[dict]:
    async with SessionLocal.begin() as session:
        obj = await session.get(Document, _uuid(doc_id))
        if not obj:
            return None
        obj.filename = filename
        obj.stored_path = stored_path
        obj.file_size = file_size
        obj.file_type = file_type
        obj.notebooklm_source_id = None
        obj.markdown_content = ""
        obj.processing_status = "processing"
        obj.progress_message = "Đang chuyển đổi tài liệu đã cập nhật"
        obj.error_message = ""
        obj.chunk_count = 0
        obj.processed_at = None
        obj.uploaded_at = datetime.now(timezone.utc)
        await session.flush()
        return _dict(obj)


async def update_document_processing(
    doc_id: str,
    status: str = None,
    progress_message: str = None,
    error_message: str = None,
    chunk_count: int = None,
    processed_at: datetime = None,
    **kwargs,
) -> Optional[dict]:
    return await _update(
        Document,
        doc_id,
        {
            "processing_status": status,
            "progress_message": progress_message,
            "error_message": error_message,
            "chunk_count": chunk_count,
            "processed_at": processed_at,
            **kwargs,
        },
    )


async def delete_document(doc_id: str) -> None:
    await _delete(Document, doc_id)


async def update_document_markdown(doc_id: str, markdown_content: str) -> None:
    await _update(Document, doc_id, {"markdown_content": markdown_content})


async def replace_document_chunks(
    document_id: str,
    chunks: list[dict],
) -> None:
    async with SessionLocal.begin() as session:
        await session.execute(delete(DocumentChunk).where(DocumentChunk.document_id == _uuid(document_id)))
        for chunk in chunks:
            session.add(
                DocumentChunk(
                    document_id=_uuid(document_id),
                    chunk_index=int(chunk.get("chunk_index") or 0),
                    header_path=str(chunk.get("header_path") or ""),
                    section_label=str(chunk.get("section_label") or ""),
                    page_label=str(chunk.get("page_label") or ""),
                    citation_label=str(chunk.get("citation_label") or ""),
                    chunk_text=str(chunk.get("chunk_text") or ""),
                    embedding_model=str(chunk.get("embedding_model") or ""),
                    embedding=list(chunk.get("embedding") or []),
                    metadata_json=chunk.get("metadata") or {},
                )
            )


async def get_document_chunks(document_id: str) -> list[dict]:
    async with SessionLocal() as session:
        rows = (
            await session.scalars(
                select(DocumentChunk)
                .where(DocumentChunk.document_id == _uuid(document_id))
                .order_by(DocumentChunk.chunk_index.asc())
            )
        ).all()
        return [_dict(row) for row in rows]


async def count_document_chunks(document_id: str) -> int:
    async with SessionLocal() as session:
        return int(
            await session.scalar(
                select(func.count(DocumentChunk.id)).where(DocumentChunk.document_id == _uuid(document_id))
            )
            or 0
        )


async def get_documents_missing_chunks_by_repository(repository_id: str) -> list[dict]:
    async with SessionLocal() as session:
        query = (
            select(Document)
            .where(
                Document.repository_id == _uuid(repository_id),
                Document.markdown_content != "",
                ~select(DocumentChunk.id)
                .where(DocumentChunk.document_id == Document.id)
                .exists(),
            )
            .order_by(Document.uploaded_at.desc())
        )
        return [_dict(row) for row in (await session.scalars(query)).all()]


async def count_repository_chunks(repository_id: str) -> int:
    async with SessionLocal() as session:
        return int(
            await session.scalar(
                select(func.count(DocumentChunk.id))
                .join(Document, Document.id == DocumentChunk.document_id)
                .where(Document.repository_id == _uuid(repository_id))
            )
            or 0
        )


def _vector_literal(values: list[float]) -> str:
    return "[" + ",".join(f"{float(value):.8f}" for value in values) + "]"


async def search_document_chunks_hybrid(
    repository_id: str,
    query_text: str,
    query_embedding: list[float],
    *,
    limit: int = 8,
    vector_candidates: int = 30,
    text_candidates: int = 30,
) -> list[dict]:
    if not query_embedding:
        return []

    sql = text(
        """
        WITH vector_matches AS (
            SELECT
                dc.id,
                dc.document_id,
                d.filename,
                dc.chunk_index,
                dc.header_path,
                dc.section_label,
                dc.page_label,
                dc.citation_label,
                dc.chunk_text,
                dc.embedding_model,
                dc.metadata,
                dc.embedding <=> CAST(:query_embedding AS vector) AS vector_distance,
                row_number() OVER (ORDER BY dc.embedding <=> CAST(:query_embedding AS vector)) AS vector_rank
            FROM document_chunks dc
            JOIN documents d ON d.id = dc.document_id
            WHERE d.repository_id = CAST(:repository_id AS uuid)
            ORDER BY dc.embedding <=> CAST(:query_embedding AS vector)
            LIMIT :vector_candidates
        ),
        text_matches AS (
            SELECT
                dc.id,
                dc.document_id,
                d.filename,
                dc.chunk_index,
                dc.header_path,
                dc.section_label,
                dc.page_label,
                dc.citation_label,
                dc.chunk_text,
                dc.embedding_model,
                dc.metadata,
                ts_rank_cd(
                    to_tsvector('simple', coalesce(dc.header_path, '') || ' ' || coalesce(dc.chunk_text, '')),
                    plainto_tsquery('simple', :query_text)
                ) AS text_rank_score,
                row_number() OVER (
                    ORDER BY ts_rank_cd(
                        to_tsvector('simple', coalesce(dc.header_path, '') || ' ' || coalesce(dc.chunk_text, '')),
                        plainto_tsquery('simple', :query_text)
                    ) DESC
                ) AS text_rank
            FROM document_chunks dc
            JOIN documents d ON d.id = dc.document_id
            WHERE d.repository_id = CAST(:repository_id AS uuid)
              AND to_tsvector('simple', coalesce(dc.header_path, '') || ' ' || coalesce(dc.chunk_text, '')) @@
                  plainto_tsquery('simple', :query_text)
            ORDER BY text_rank_score DESC
            LIMIT :text_candidates
        ),
        fused AS (
            SELECT
                coalesce(v.id, t.id) AS id,
                coalesce(v.document_id, t.document_id) AS document_id,
                coalesce(v.filename, t.filename) AS filename,
                coalesce(v.chunk_index, t.chunk_index) AS chunk_index,
                coalesce(v.header_path, t.header_path) AS header_path,
                coalesce(v.section_label, t.section_label) AS section_label,
                coalesce(v.page_label, t.page_label) AS page_label,
                coalesce(v.citation_label, t.citation_label) AS citation_label,
                coalesce(v.chunk_text, t.chunk_text) AS chunk_text,
                coalesce(v.embedding_model, t.embedding_model) AS embedding_model,
                coalesce(v.metadata, t.metadata) AS metadata,
                v.vector_distance,
                t.text_rank_score,
                (coalesce(1.0 / (60 + v.vector_rank), 0.0) +
                 coalesce(1.0 / (60 + t.text_rank), 0.0)) AS hybrid_score
            FROM vector_matches v
            FULL OUTER JOIN text_matches t ON t.id = v.id
        )
        SELECT *
        FROM fused
        ORDER BY hybrid_score DESC, vector_distance ASC NULLS LAST
        LIMIT :limit
        """
    )
    params = {
        "repository_id": str(repository_id),
        "query_text": query_text,
        "query_embedding": _vector_literal(query_embedding),
        "limit": int(limit),
        "vector_candidates": int(vector_candidates),
        "text_candidates": int(text_candidates),
    }
    async with SessionLocal() as session:
        rows = (await session.execute(sql, params)).mappings().all()
        return [
            {
                key: _json_safe(value)
                for key, value in dict(row).items()
            }
            for row in rows
        ]


async def get_documents_markdown_by_repository(
    repository_id: str, document_ids: list[str] | None = None
) -> list[dict]:
    async with SessionLocal() as session:
        query = select(Document).where(
            Document.repository_id == _uuid(repository_id),
            Document.markdown_content != "",
        )
        if document_ids:
            query = query.where(Document.id.in_([_uuid(value) for value in document_ids]))
        rows = (await session.scalars(query.order_by(Document.uploaded_at.desc()))).all()
        return [_dict(row) for row in rows]


# Chat
async def add_chat_message(repository_id: str, user_id: str, role: str, content: str) -> dict:
    async with SessionLocal.begin() as session:
        obj = ChatMessage(
            repository_id=_uuid(repository_id), user_id=_uuid(user_id), role=role, content=content
        )
        session.add(obj)
        await session.flush()
        return _dict(obj)


async def get_chat_history(repository_id: str, user_id: str, limit: int = 50) -> list[dict]:
    async with SessionLocal() as session:
        rows = (await session.scalars(
            select(ChatMessage)
            .where(
                ChatMessage.repository_id == _uuid(repository_id),
                ChatMessage.user_id == _uuid(user_id),
            )
            .order_by(ChatMessage.created_at.desc())
            .limit(limit)
        )).all()
        return [_dict(row) for row in reversed(rows)]


async def delete_chat_history(repository_id: str, user_id: str) -> None:
    async with SessionLocal.begin() as session:
        await session.execute(
            delete(ChatMessage).where(
                ChatMessage.repository_id == _uuid(repository_id),
                ChatMessage.user_id == _uuid(user_id),
            )
        )


# Organizations and departments
async def create_organization(name: str, description: str = "", max_accounts: int = 0) -> dict:
    async with SessionLocal.begin() as session:
        obj = Organization(name=name, description=description, max_accounts=max_accounts)
        session.add(obj)
        await session.flush()
        return _dict(obj)


async def get_all_organizations() -> list[dict]:
    async with SessionLocal() as session:
        return [_dict(row) for row in (await session.scalars(
            select(Organization).order_by(Organization.created_at.desc())
        )).all()]


async def get_organization_by_id(org_id: str) -> Optional[dict]:
    return await _get(Organization, org_id)


async def update_organization(
    org_id: str, name: str = None, description: str = None, max_accounts: int = None
) -> Optional[dict]:
    return await _update(
        Organization,
        org_id,
        {"name": name, "description": description, "max_accounts": max_accounts},
    )


async def delete_organization(org_id: str) -> None:
    await _delete(Organization, org_id)


async def create_department(org_id: str, name: str, description: str = "") -> dict:
    async with SessionLocal.begin() as session:
        obj = Department(org_id=_uuid(org_id), name=name, description=description)
        session.add(obj)
        await session.flush()
        return _dict(obj)


async def get_departments_by_org(org_id: str) -> list[dict]:
    async with SessionLocal() as session:
        return [_dict(row) for row in (await session.scalars(
            select(Department)
            .where(Department.org_id == _uuid(org_id))
            .order_by(Department.created_at.desc())
        )).all()]


async def get_department_by_id(dept_id: str) -> Optional[dict]:
    return await _get(Department, dept_id)


async def update_department(
    dept_id: str, name: str = None, description: str = None
) -> Optional[dict]:
    return await _update(Department, dept_id, {"name": name, "description": description})


async def delete_department(dept_id: str) -> None:
    await _delete(Department, dept_id)
