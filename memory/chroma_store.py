import chromadb
from config import CHROMA_PATH

client = chromadb.PersistentClient(path=CHROMA_PATH)

def get_collection(name: str):
    return client.get_or_create_collection(name)

def store_memory(collection_name: str, doc_id: str, content: str, metadata: dict = {}):
    col = get_collection(collection_name)
    col.upsert(documents=[content], ids=[doc_id], metadatas=[metadata])

def retrieve_memory(collection_name: str, query: str, n=3):
    col = get_collection(collection_name)
    results = col.query(query_texts=[query], n_results=n)
    return results["documents"][0] if results["documents"] else []