from __future__ import annotations

from sqlalchemy import text




def search_similar_sections(
    session,
    query_embedding: list[float],
    limit: int = 5,
    exclude_section_numbers: list[str] | None = None,
) -> list:
    """Find sections most similar to a query embedding."""
    exclude = exclude_section_numbers or []

    results = session.execute(
        text(
            """
            SELECT
                id,
                section_number,
                title,
                full_text,
                version_date,
                1 - (embedding <=> CAST(:emb AS vector)) AS similarity
            FROM regulation_sections
            WHERE embedding IS NOT NULL
              AND level = 2
              AND NOT (section_number = ANY(:exclude))
            ORDER BY embedding <=> CAST(:emb AS vector)
            LIMIT :lim
            """
        ),
        {
            "emb": str(query_embedding),
            "exclude": exclude,
            "lim": limit,
        },
    )

    return results.fetchall()


def get_sibling_sections(session, section_number: str, part_id: int) -> list:
    """Get sections in the same subpart using parent_section_number."""
    section = session.execute(
        text(
            """
            SELECT parent_section_number
            FROM regulation_sections
            WHERE section_number = :sn
              AND part_id = :pid
              AND level = 2
            """
        ),
        {"sn": section_number, "pid": part_id},
    ).fetchone()

    if not section or not section.parent_section_number:
        return []

    siblings = session.execute(
        text(
            """
            SELECT section_number, title, full_text
            FROM regulation_sections
            WHERE parent_section_number = :parent_sn
              AND part_id = :pid
              AND level = 2
              AND section_number != :sn
            ORDER BY section_number
            """
        ),
        {
            "parent_sn": section.parent_section_number,
            "pid": part_id,
            "sn": section_number,
        },
    )

    return siblings.fetchall()

def search_similar_context_chunks(
    session,
    query_embedding: list[float],
    document_short_code: str,
    source_type: str = "federal_register_preamble",
    limit: int = 3,
) -> list:
    results = session.execute(
        text(
            """
            SELECT
                cc.id,
                cd.document_short_code,
                cc.chunk_index,
                cc.heading,
                cc.chunk_text,
                1 - (cc.embedding <=> CAST(:emb AS vector)) AS similarity
            FROM context_chunks cc
            JOIN context_documents cd
              ON cd.id = cc.document_id
            WHERE cc.embedding IS NOT NULL
              AND cd.document_short_code = :doc_code
              AND cd.source_type = :source_type
            ORDER BY cc.embedding <=> CAST(:emb AS vector)
            LIMIT :lim
            """
        ),
        {
            "emb": str(query_embedding),
            "doc_code": document_short_code,
            "source_type": source_type,
            "lim": limit,
        },
    )
    return results.fetchall()

from sqlalchemy import text


def search_similar_sections_latest_only(
    session,
    query_embedding: list[float],
    limit: int = 7,
    part_numbers: list[int] | None = None,
) -> list:
    """
    Retrieve semantically similar sections, keeping only the latest version
    of each section_number across the selected parts.
    """
    part_numbers = part_numbers or [11, 210, 211, 820]

    results = session.execute(
        text(
            """
            WITH latest_sections AS (
                SELECT rs.*
                FROM regulation_sections rs
                JOIN regulation_parts rp
                  ON rp.id = rs.part_id
                JOIN (
                    SELECT
                        rs2.section_number,
                        MAX(rp2.version_date) AS max_version_date
                    FROM regulation_sections rs2
                    JOIN regulation_parts rp2
                      ON rp2.id = rs2.part_id
                    WHERE rp2.title_number = 21
                      AND rp2.part_number = ANY(:part_numbers)
                      AND rs2.embedding IS NOT NULL
                      AND rs2.level = 2
                    GROUP BY rs2.section_number
                ) latest
                  ON latest.section_number = rs.section_number
                 AND latest.max_version_date = rs.version_date
                WHERE rp.title_number = 21
                  AND rp.part_number = ANY(:part_numbers)
                  AND rs.embedding IS NOT NULL
                  AND rs.level = 2
            )
            SELECT
                section_number,
                title,
                full_text,
                version_date,
                1 - (embedding <=> CAST(:emb AS vector)) AS similarity
            FROM latest_sections
            ORDER BY embedding <=> CAST(:emb AS vector)
            LIMIT :lim
            """
        ),
        {
            "emb": str(query_embedding),
            "lim": limit,
            "part_numbers": part_numbers,
        },
    )

    return results.fetchall()

def search_similar_sections_current_only(
    session,
    query_embedding: list[float],
    limit: int = 7,
    part_numbers: list[int] | None = None,
) -> list:
    """
    Retrieve semantically similar sections from the current snapshot only.

    For each selected part, use the most recent version_date in regulation_parts,
    then search only regulation_sections belonging to those latest part snapshots.
    """
    part_numbers = part_numbers or [11, 210, 211, 820]

    results = session.execute(
        text(
            """
            WITH latest_parts AS (
                SELECT rp.id, rp.part_number, rp.version_date
                FROM regulation_parts rp
                JOIN (
                    SELECT
                        part_number,
                        MAX(version_date) AS max_version_date
                    FROM regulation_parts
                    WHERE title_number = 21
                      AND part_number = ANY(:part_numbers)
                    GROUP BY part_number
                ) latest
                  ON latest.part_number = rp.part_number
                 AND latest.max_version_date = rp.version_date
                WHERE rp.title_number = 21
                  AND rp.part_number = ANY(:part_numbers)
            )
            SELECT
                rs.section_number,
                rs.title,
                rs.full_text,
                rs.version_date,
                1 - (rs.embedding <=> CAST(:emb AS vector)) AS similarity
            FROM regulation_sections rs
            JOIN latest_parts lp
              ON lp.id = rs.part_id
            WHERE rs.embedding IS NOT NULL
                AND rs.level = 2
                AND COALESCE(rs.title, '') NOT ILIKE '%[Reserved]%'
                AND COALESCE(rs.full_text, '') NOT ILIKE '%[Reserved]%'
            ORDER BY rs.embedding <=> CAST(:emb AS vector)
            LIMIT :lim
            """
        ),
        {
            "emb": str(query_embedding),
            "lim": limit,
            "part_numbers": part_numbers,
        },
    )

    return results.fetchall()

def search_similar_context_chunks_by_source_type(
    session,
    query_embedding: list[float],
    corpus: str,
    source_type: str,
    limit: int = 3,
) -> list:
    results = session.execute(
        text(
            """
            SELECT
                cc.id,
                cd.corpus,
                cd.document_short_code,
                cd.source_type,
                cc.chunk_index,
                cc.heading,
                cc.chunk_text,
                1 - (cc.embedding <=> CAST(:emb AS vector)) AS similarity
            FROM context_chunks cc
            JOIN context_documents cd
              ON cd.id = cc.document_id
            WHERE cc.embedding IS NOT NULL
              AND cd.corpus = :corpus
              AND cd.source_type = :source_type
            ORDER BY cc.embedding <=> CAST(:emb AS vector)
            LIMIT :lim
            """
        ),
        {
            "emb": str(query_embedding),
            "corpus": corpus,
            "source_type": source_type,
            "lim": limit,
        },
    )
    return results.fetchall()

def search_similar_context_chunks_by_document_codes(
    session,
    query_embedding: list[float],
    corpus: str,
    document_codes: list[str],
    limit: int = 3,
) -> list:
    results = session.execute(
        text(
            """
            SELECT
                cc.id,
                cd.corpus,
                cd.document_short_code,
                cd.source_type,
                cc.chunk_index,
                cc.heading,
                cc.chunk_text,
                1 - (cc.embedding <=> CAST(:emb AS vector)) AS similarity
            FROM context_chunks cc
            JOIN context_documents cd
              ON cd.id = cc.document_id
            WHERE cc.embedding IS NOT NULL
              AND cd.corpus = :corpus
              AND cd.document_short_code = ANY(:document_codes)
            ORDER BY cc.embedding <=> CAST(:emb AS vector)
            LIMIT :lim
            """
        ),
        {
            "emb": str(query_embedding),
            "corpus": corpus,
            "document_codes": document_codes,
            "lim": limit,
        },
    )
    return results.fetchall()


def search_similar_context_chunks_by_corpus(
    session,
    query_embedding: list[float],
    corpus: str,
    limit: int = 5,
) -> list:
    results = session.execute(
        text(
            """
            SELECT
                cc.id,
                cd.corpus,
                cd.document_short_code,
                cd.source_type,
                cc.chunk_index,
                cc.heading,
                cc.chunk_text,
                1 - (cc.embedding <=> CAST(:emb AS vector)) AS similarity
            FROM context_chunks cc
            JOIN context_documents cd
              ON cd.id = cc.document_id
            WHERE cc.embedding IS NOT NULL
              AND cd.corpus = :corpus
            ORDER BY cc.embedding <=> CAST(:emb AS vector)
            LIMIT :lim
            """
        ),
        {
            "emb": str(query_embedding),
            "corpus": corpus,
            "lim": limit,
        },
    )
    return results.fetchall()