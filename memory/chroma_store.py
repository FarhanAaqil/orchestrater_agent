import chromadb
from config import CHROMA_PATH
from datetime import datetime, timedelta
import json

client = chromadb.PersistentClient(path=CHROMA_PATH)


def get_collection(name: str):
    return client.get_or_create_collection(name)


def store_memory(collection_name: str, doc_id: str, content: str, metadata: dict = {}):
    """Store a document in the specified collection."""
    col = get_collection(collection_name)
    # Ensure all metadata values are strings/ints/floats (ChromaDB requirement)
    safe_meta = {k: str(v) if not isinstance(v, (str, int, float, bool)) else v
                 for k, v in metadata.items()}
    col.upsert(documents=[content], ids=[doc_id], metadatas=[safe_meta])


def retrieve_memory(collection_name: str, query: str, n: int = 3) -> list:
    """Retrieve the top-n most semantically similar documents."""
    col = get_collection(collection_name)
    try:
        count = col.count()
        if count == 0:
            return []
        n = min(n, count)
        results = col.query(query_texts=[query], n_results=n)
        return results["documents"][0] if results["documents"] else []
    except Exception:
        return []


def retrieve_with_metadata(collection_name: str, query: str, n: int = 3) -> list:
    """Retrieve documents with their metadata — returns list of {doc, metadata} dicts."""
    col = get_collection(collection_name)
    try:
        count = col.count()
        if count == 0:
            return []
        n = min(n, count)
        results = col.query(query_texts=[query], n_results=n)
        docs = results.get("documents", [[]])[0]
        metas = results.get("metadatas", [[]])[0]
        return [{"doc": d, "metadata": m} for d, m in zip(docs, metas)]
    except Exception:
        return []


def get_recent(collection_name: str, days: int = 7, limit: int = 10) -> list:
    """Retrieve documents created within the last N days."""
    col = get_collection(collection_name)
    try:
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        results = col.get(
            where={"timestamp": {"$gte": cutoff}},
            limit=limit
        )
        docs = results.get("documents", [])
        metas = results.get("metadatas", [])
        return [{"doc": d, "metadata": m} for d, m in zip(docs, metas)]
    except Exception:
        # Fallback: return without date filter if metadata key missing
        try:
            results = col.get(limit=limit)
            return [{"doc": d, "metadata": m}
                    for d, m in zip(results.get("documents", []),
                                    results.get("metadatas", []))]
        except Exception:
            return []


def delete_memory(collection_name: str, doc_id: str) -> bool:
    """Delete a specific document by ID."""
    try:
        col = get_collection(collection_name)
        col.delete(ids=[doc_id])
        return True
    except Exception:
        return False


def store_reasoning_trace(agent_name: str, task: str, reasoning: str,
                          result: str, quality_score: float = None):
    """Store a structured reasoning trace for an agent's output.
    This enables agents to learn from past reasoning patterns.
    """
    trace_id = f"{agent_name}_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
    trace_content = json.dumps({
        "task": task[:500],
        "reasoning": reasoning[:1000],
        "result_preview": result[:300],
        "quality_score": quality_score
    })
    metadata = {
        "agent": agent_name,
        "timestamp": datetime.now().isoformat(),
        "quality_score": quality_score if quality_score is not None else -1,
        "task_preview": task[:100]
    }
    store_memory(f"{agent_name}_traces", trace_id, trace_content, metadata)


def get_quality_history(agent_name: str, content_type: str, n: int = 10) -> list:
    """Retrieve past quality scores for a specific agent + content type."""
    results = retrieve_with_metadata(
        f"{agent_name}_traces",
        f"quality score for {content_type}",
        n=n
    )
    scores = []
    for r in results:
        meta = r.get("metadata", {})
        score = meta.get("quality_score", -1)
        if score != -1:
            try:
                scores.append(float(score))
            except (ValueError, TypeError):
                pass
    return scores