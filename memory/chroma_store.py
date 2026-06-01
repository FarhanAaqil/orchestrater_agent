import chromadb
from config import CHROMA_PATH

client = chromadb.PersistentClient(path=CHROMA_PATH)

def get_collection(name: str):
    return client.get_or_create_collection(name)

def store_memory(collection_name: str, doc_id: str, content: str, metadata: dict = {}):
    col = get_collection(collection_name)
    
    # Semantic deduplication
    count = col.count()
    if count > 0:
        results = col.query(query_texts=[content], n_results=1)
        if results and results.get("distances") and results["distances"][0]:
            dist = results["distances"][0][0]
            if dist < 0.15:  # Threshold for similarity
                print(f"Duplicate ignored in {collection_name} (dist: {dist})")
                return

    col.upsert(documents=[content], ids=[doc_id], metadatas=[metadata])

def retrieve_memory(collection_name: str, query: str, n: int = 3) -> list:
    """Query semantic memory. Returns empty list if collection is empty or on any error."""
    try:
        col = get_collection(collection_name)
        count = col.count()
        if count == 0:
            return []
        # Don't request more results than documents in the collection
        n_results = min(n, count)
        results = col.query(query_texts=[query], n_results=n_results)
        return results["documents"][0] if results["documents"] else []
    except Exception:
        return []