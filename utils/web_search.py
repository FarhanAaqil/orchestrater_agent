from duckduckgo_search import DDGS
import arxiv
import requests

def search_web(query: str, max_results: int = 5) -> list:
    results = []
    try:
        with DDGS() as ddgs:
            for r in ddgs.text(query, max_results=max_results):
                results.append({
                    "title": r.get("title", ""),
                    "snippet": r.get("body", ""),
                    "url": r.get("href", "")
                })
    except Exception as e:
        results = [{"error": str(e)}]
    return results

def search_news(query: str, max_results: int = 5) -> list:
    results = []
    try:
        with DDGS() as ddgs:
            for r in ddgs.news(query, max_results=max_results):
                results.append({
                    "title": r.get("title", ""),
                    "snippet": r.get("body", ""),
                    "url": r.get("url", ""),
                    "date": r.get("date", "")
                })
    except Exception as e:
        results = [{"error": str(e)}]
    return results

def search_arxiv(query: str, max_results: int = 10) -> list:
    results = []
    try:
        client = arxiv.Client()
        search = arxiv.Search(
            query=query,
            max_results=max_results,
            sort_by=arxiv.SortCriterion.Relevance
        )
        for paper in client.results(search):
            results.append({
                "title": paper.title,
                "authors": [a.name for a in paper.authors[:4]],
                "abstract": paper.summary[:400],
                "url": paper.pdf_url,
                "arxiv_id": paper.entry_id,
                "published": str(paper.published)[:10],
                "categories": paper.categories[:3]
            })
    except Exception as e:
        results = [{"error": str(e)}]
    return results

def fetch_page(url: str) -> str:
    try:
        resp = requests.get(url, timeout=10,
            headers={"User-Agent": "Mozilla/5.0"})
        return resp.text[:3000]
    except Exception as e:
        return f"Error: {str(e)}"