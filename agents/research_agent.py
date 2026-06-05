from agents.base_agent import BaseAgent
from database.tracker import (
    add_paper, get_papers, update_paper_status,
    add_journal_target, get_journal_targets
)
import requests
import os
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from config import PERSONAL_NAME, PERSONAL_EMAIL, AFFILIATION, DEPARTMENT

AUTHOR_PROFILE = f"""
Author: {PERSONAL_NAME}
Affiliation: {AFFILIATION}
Department: {DEPARTMENT}
Email: {PERSONAL_EMAIL}
Previous Publication: ML-based Diabetes Prediction (2025)
"""

# Known predatory publishers to blacklist
PREDATORY_PUBLISHERS = [
    "omics", "scientific research publishing", "scirp",
    "academic journals", "scientific & academic publishing",
    "international journal of computer applications",
    "ijca", "wseas", "waset", "ijarai", "ijcsis"
]

# Trusted publishers
TRUSTED_PUBLISHERS = [
    "ieee", "acm", "springer", "elsevier", "wiley",
    "mdpi", "nature", "oxford", "cambridge", "hindawi",
    "frontiers", "plos", "arxiv"
]

class ResearchAgent(BaseAgent):

    TOOLS = [
        {
            "name": "write_paper",
            "description": "Write a full academic research paper. Use for 'write paper', 'generate paper'.",
            "args": {"project": "str", "description": "str", "results": "str (optional)", "methodology": "str (optional)", "format": "str (default 'ieee')"}
        },
        {
            "name": "improve_paper",
            "description": "Improve a generated paper based on feedback. Use for 'improve paper [ID]', 'fix paper'.",
            "args": {"paper_id": "int", "feedback": "str"}
        },
        {
            "name": "read_full_paper",
            "description": "Read the full text of an ArXiv paper from its PDF URL. Use for 'read paper', 'summarize full paper'.",
            "args": {"pdf_url": "str"}
        },
        {
            "name": "find_journals",
            "description": "Search DOAJ for free, reputable journals. Use for 'find journals', 'search journals'.",
            "args": {"topic": "str", "paper_id": "int (optional)"}
        },
        {
            "name": "recommend_journals",
            "description": "Recommend reputable, indexed journals via LLM. Use for 'recommend journals'.",
            "args": {"topic": "str", "paper_id": "int (optional)"}
        },
        {
            "name": "check_predatory",
            "description": "Check if a journal is predatory. Use for 'is [journal] predatory', 'check journal'.",
            "args": {"journal_name": "str"}
        },
        {
            "name": "draft_submission_email",
            "description": "Draft a formal journal submission email. Use for 'submission email'.",
            "args": {"paper_title": "str", "journal": "str", "editor": "str (optional)"}
        },
        {
            "name": "draft_cover_letter",
            "description": "Write a formal cover letter for journal submission. Use for 'research cover letter'.",
            "args": {"paper_title": "str", "journal": "str", "abstract": "str (optional)"}
        },
        {
            "name": "update_paper_status",
            "description": "Update the status of a tracked paper. Use for 'update paper [ID] to [status]'.",
            "args": {"paper_id": "int", "status": "str", "journal": "str (optional)", "decision": "str (optional)"}
        },
        {
            "name": "research_dashboard",
            "description": "Show the research papers dashboard with stats. Use for 'research dashboard', 'papers dashboard'.",
            "args": {}
        },
        {
            "name": "show_papers",
            "description": "Show a list of all tracked papers. Use for 'show papers', 'my papers'.",
            "args": {}
        }
    ]

    def __init__(self):
        super().__init__(
            name="research",
            system_prompt=f"""You are Aaqil's Research Agent.
You write professional research papers, find reputable journals, and manage submissions.
Author details:
{AUTHOR_PROFILE}
Always write in formal academic style. Follow IEEE/ACM standards.
Never suggest predatory journals. Only reputable, indexed publishers."""
        )

    # ─── Paper Writer ─────────────────────────────────────────────────

    def write_paper(self, project: str, description: str = "", results: str = "",
                methodology: str = "", format: str = "ieee",
                target_pages: int = 30) -> dict:

        from utils.web_search import search_arxiv, search_web, fetch_arxiv_full_text
    
        # Step 1: Live literature search
        arxiv_papers = search_arxiv(f"{project} machine learning AI", max_results=15)
        web_refs = search_web(f"{project} research survey state of the art", max_results=5)
    
        # Format citations
        citations = []
        for i, p in enumerate(arxiv_papers[:12], 1):
            if "error" in p:
                continue
            authors = ", ".join(p.get("authors", [])[:3])
            if len(p.get("authors", [])) > 3:
                authors += " et al."
            citations.append({
                "id": i,
                "authors": authors,
                "title": p.get("title", "Untitled"),
                "year": p.get("published", "2024")[:4],
                "url": p.get("url", ""),
                "abstract": p.get("abstract", "")
            })
    
        citation_text = "\n".join([
            f'[{c["id"]}] {c["authors"]}, "{c["title"]}", {c["year"]}. {c["url"]}'
            for c in citations
        ])
    
        # Pull full text for the top most relevant paper to make related work deeply technical
        top_paper_full_text = ""
        if citations:
            top_paper_url = citations[0]["url"]
            print(f"Fetching full text for {top_paper_url}")
            full_text = fetch_arxiv_full_text(top_paper_url)
            if not full_text.startswith("Error"):
                top_paper_full_text = full_text[:4000] # First 4000 chars of top paper for deep context

        related_work_context = "\n".join([
            f'Paper {c["id"]}: {c["title"]} — {c["abstract"][:200]}'
            for c in citations
        ])

        if top_paper_full_text:
            related_work_context += f"\n\nDEEP CONTEXT (Paper 1 Full Text Excerpt):\n{top_paper_full_text}"

        # Step 2: Write all sections in parallel using a thread pool
        # This reduces wall-clock time from ~7 serial calls to ~1 parallel batch.
        section_prompts = {
            "abstract": f"""Write a comprehensive abstract and keywords for:
Project: {project}
Description: {description}
Results: {results or 'Significant improvement over baseline methods'}
Format: IEEE

Abstract should be 250-300 words covering:
- Problem statement and motivation
- Proposed approach/methodology
- Key results with specific numbers
- Significance and contributions

Then list 8-10 IEEE-style keywords.""",

            "introduction": f"""Write a detailed Introduction section for an IEEE research paper:
Project: {project}
Description: {description}

Write 800-1000 words covering:
1. Background and problem motivation (cite [{', '.join([str(c['id']) for c in citations[:4]])}])
2. Limitations of existing approaches
3. Why this problem is important now
4. Overview of proposed solution
5. Key contributions (bullet list of 4-5 specific contributions)
6. Paper organization paragraph

Use IEEE citation style [1], [2] etc.
Available citations:
{citation_text[:2000]}""",

            "related_work": f"""Write a comprehensive Related Work section:
Project: {project}

Write 1000-1200 words organized into subsections:
2.1 Traditional Approaches
2.2 Machine Learning Based Methods
2.3 Deep Learning and Neural Approaches
2.4 Recent LLM and Agent-Based Systems
2.5 Research Gaps

For each subsection discuss 2-3 relevant papers with citations.
Be critical — explain why existing methods fall short.

Available papers to cite:
{related_work_context}

Use IEEE citation format [1], [2] etc.""",

            "background": f"""Write a Theoretical Background / Preliminaries section:
Project: {project}
Methodology: {methodology or 'Machine Learning, Neural Networks, LLM Agents'}

Write 600-800 words covering:
3.1 Mathematical foundations relevant to this work
3.2 Key algorithms and models used
3.3 Formal problem definition with mathematical notation
3.4 Evaluation metrics with formulas

Include LaTeX-style math equations where appropriate.""",

            "methodology": f"""Write an extremely detailed Methodology section:
Project: {project}
Description: {description}
Methodology: {methodology or 'AI/ML pipeline with LLM agents and vector memory'}

Write 1500-2000 words covering:
4.1 System Architecture Overview
4.2 Data Collection and Preprocessing
4.3 Model Design and Implementation
4.4 Training Strategy
4.5 Agent Architecture (if applicable)
4.6 Implementation Details

Be extremely technical and specific.""",

            "experiments": f"""Write a detailed Experimental Setup section:
Project: {project}

Write 600-800 words covering:
5.1 Datasets
5.2 Baseline Methods
5.3 Evaluation Metrics
5.4 Implementation Environment
5.5 Hyperparameter Configuration""",

            "results": f"""Write a comprehensive Results and Discussion section:
Project: {project}
Results context: {results or 'The proposed method demonstrates significant improvements'}

Write 1000-1200 words covering:
6.1 Main Results
6.2 Ablation Study
6.3 Qualitative Analysis
6.4 Error Analysis
6.5 Discussion""",

            "conclusion": f"""Write a Conclusion and Future Work section:
Project: {project}

Write 400-500 words covering:
7.1 Summary of contributions
7.2 Key findings
7.3 Limitations
7.4 Future work directions (at least 5 specific directions)
7.5 Broader impact and applications""",
        }

        sections: dict = {}
        # Use a thread pool to write all sections concurrently
        with ThreadPoolExecutor(max_workers=4) as executor:
            future_to_section = {
                executor.submit(self.run, prompt): name
                for name, prompt in section_prompts.items()
            }
            for future in as_completed(future_to_section):
                section_name = future_to_section[future]
                try:
                    sections[section_name] = future.result()
                except Exception as e:
                    sections[section_name] = f"*(Section generation failed: {e})*"
    
        # Assemble full paper
        full_paper = f"""# {project}: A Comprehensive Study
    
    **Author:** Farhan Aaqil
    **Affiliation:** Department of Artificial Intelligence and Machine Learning,
    Jayaprakash Narayan College of Engineering, Mahbubnagar, Telangana, India
    **Email:** fadurrani543@gmail.com
    
    ---
    
    ## Abstract
    
    {sections['abstract']}
    
    ---
    
    ## I. INTRODUCTION
    
    {sections['introduction']}
    
    ---
    
    ## II. RELATED WORK
    
    {sections['related_work']}
    
    ---
    
    ## III. THEORETICAL BACKGROUND
    
    {sections['background']}
    
    ---
    
    ## IV. PROPOSED METHODOLOGY
    
    {sections['methodology']}
    
    ---
    
    ## V. EXPERIMENTAL SETUP
    
    {sections['experiments']}
    
    ---
    
    ## VI. RESULTS AND DISCUSSION
    
    {sections['results']}
    
    ---
    
    ## VII. CONCLUSION AND FUTURE WORK
    
    {sections['conclusion']}
    
    ---
    
    ## REFERENCES
    
    {citation_text}
    
    ---
    
    *Paper generated with live ArXiv citations.*
    *Total citations: {len(citations)}*
    *Format: {format.upper()}*
    """
    
        paper_id = add_paper(
            f"{project} — Research Paper",
            sections["abstract"][:500],
            full_paper,
            project,
            format
        )

        return {
            "paper_id": paper_id,
            "title": f"{project}: A Comprehensive Study",
            "content": full_paper,
            "citations": len(citations),
            "format": format,
            "sections": list(sections.keys())
        }

    def read_full_paper(self, pdf_url: str) -> str:
        from utils.web_search import fetch_arxiv_full_text
        text = fetch_arxiv_full_text(pdf_url)
        if text.startswith("Error"):
            return f"❌ Failed to fetch paper: {text}"
        
        task = f"""Summarize this full research paper and extract key findings:
{text[:8000]}...

Provide:
1. Core Methodology
2. Key Results (with numbers if available)
3. Main Contributions
4. Limitations"""
        return self.run(task)

    # ─── Journal Finder ───────────────────────────────────────────────

    def find_journals(self, topic: str, paper_id: int = None) -> list:
        """Search DOAJ for free, reputable journals"""
        try:
            query = topic.replace(" ", "%20")
            url = f"https://doaj.org/api/v3/search/journals?q={query}&pageSize=20&sort=score"
            resp = requests.get(url, timeout=15)
            data = resp.json()

            journals = []
            for item in data.get("results", []):
                bibjson = item.get("bibjson", {})
                publisher = bibjson.get("publisher", {}).get("name", "").lower()
                journal_name = bibjson.get("title", "")
                apc_info = bibjson.get("apc", {})

                # Skip predatory
                if any(p in publisher for p in PREDATORY_PUBLISHERS):
                    continue

                # Check if free to publish
                has_apc = apc_info.get("has_apc", True)
                apc_max = 0
                if has_apc and apc_info.get("max"):
                    apc_max = apc_info["max"][0].get("price", 999) if apc_info["max"] else 999

                if apc_max > 500:  # Skip expensive journals
                    continue

                journal_info = {
                    "name": journal_name,
                    "publisher": bibjson.get("publisher", {}).get("name", ""),
                    "subject": ", ".join([s.get("term", "") for s in bibjson.get("subject", [])[:3]]),
                    "is_open_access": True,
                    "apc": apc_max,
                    "url": bibjson.get("ref", {}).get("journal_url", ""),
                    "eissn": bibjson.get("eissn", "")
                }
                journals.append(journal_info)

                if paper_id:
                    add_journal_target(
                        paper_id, journal_name,
                        bibjson.get("publisher", {}).get("name", ""),
                        0, 1,
                        bibjson.get("ref", {}).get("journal_url", "")
                    )

            return journals[:10]
        except Exception as e:
            return [{"error": str(e)}]

    def recommend_journals(self, topic: str, paper_id: int = None) -> str:
        """LLM-powered journal recommendations for reputable venues"""
        task = f"""Recommend the best journals and conferences for this research topic:
Topic: {topic}

Requirements:
- Must be indexed (IEEE Xplore, ACM DL, Scopus, Web of Science)
- Preferably open access or low APC
- Relevant to AI/ML/Computer Science
- Reputable, NOT predatory

For each (give 8 options — mix of journals and conferences):
1. Name
2. Publisher
3. Impact Factor / Ranking
4. Open Access? Cost?
5. Submission Link
6. Why it fits this paper
7. Typical review timeline

Include at least:
- 2 IEEE journals/conferences
- 2 ACM venues
- 2 Springer/Elsevier options
- 2 open access options (MDPI, Frontiers, etc.)"""
        result = self.run(task)
        if paper_id:
            # Store top recommendations
            for line in result.split('\n'):
                if "IEEE" in line or "ACM" in line or "Springer" in line:
                    add_journal_target(paper_id, line.strip(), "Various", 0, 1)
        return result

    def check_predatory(self, journal_name: str) -> str:
        """Check if journal is predatory"""
        journal_lower = journal_name.lower()
        is_predatory = any(p in journal_lower for p in PREDATORY_PUBLISHERS)
        is_trusted = any(t in journal_lower for t in TRUSTED_PUBLISHERS)

        task = f"""Evaluate if this journal is legitimate or predatory:
Journal: {journal_name}

Check against:
1. Beall's List of predatory publishers
2. Is it indexed in Scopus/WoS/IEEE/ACM?
3. Does it have a legitimate peer review process?
4. Is the editorial board real?
5. What is its reputation in the AI/ML community?

Give a clear SAFE ✅ or AVOID ❌ verdict with reasoning."""

        llm_check = self.run(task)

        if is_predatory:
            return f"❌ **AVOID** — {journal_name} matches known predatory publisher patterns.\n\n{llm_check}"
        elif is_trusted:
            return f"✅ **SAFE** — {journal_name} is from a trusted publisher.\n\n{llm_check}"
        else:
            return f"⚠️ **VERIFY** — {journal_name} needs manual verification.\n\n{llm_check}"

    # ─── Submission ───────────────────────────────────────────────────

    def draft_submission_email(self, paper_title: str, journal: str,
                                editor: str = "Editor-in-Chief") -> str:
        task = f"""Draft a formal manuscript submission email:

To: {editor}, {journal}
Paper Title: {paper_title}
Author: {PERSONAL_NAME}, {AFFILIATION}
Previous Publication: ML-based Diabetes Prediction (2025)

Include:
1. Formal subject line
2. Paper title and brief significance (2 sentences)
3. Why it fits this journal specifically
4. Confirmation it's original, not under review elsewhere
5. Author contact details
6. Professional closing

Formal academic tone. 200-250 words max."""
        return self.run(task)

    def draft_cover_letter(self, paper_title: str, journal: str,
                            abstract: str = "") -> str:
        task = f"""Write a formal cover letter for journal submission:

Paper: {paper_title}
Journal: {journal}
Abstract: {abstract[:500] if abstract else 'AI/ML research paper'}
Author: {AAQIL_PROFILE}

Cover letter should include:
1. What the paper investigates
2. Key contribution and novelty
3. Why this journal is appropriate
4. Statement of originality
5. No conflict of interest declaration
6. Corresponding author details

Academic format. 300-400 words."""
        return self.run(task)

    # ─── Dashboard ────────────────────────────────────────────────────

    def research_dashboard(self) -> str:
        papers = get_papers()
        if not papers:
            return "No papers yet. Start with: 'write paper for <project>'"

        result = "📚 **Research Dashboard:**\n\n"
        status_emoji = {
            "draft": "✏️", "review": "🔍",
            "submitted": "📬", "accepted": "✅",
            "rejected": "❌", "revision": "🔄"
        }

        counts = {}
        for p in papers:
            counts[p["status"]] = counts.get(p["status"], 0) + 1

        for status, count in counts.items():
            result += f"{status_emoji.get(status, '📌')} {status.capitalize()}: {count}\n"

        result += "\n**Papers:**\n"
        for p in papers:
            result += f"\n{status_emoji.get(p['status'], '📌')} **{p['title'][:60]}**\n"
            result += f"  Project: {p['project']} | Format: {p['format'].upper()}\n"
            result += f"  Created: {p['created_at'][:10]}\n"
            if p["target_journal"]:
                result += f"  Target: {p['target_journal']}\n"
            if p["decision"]:
                result += f"  Decision: {p['decision']}\n"

        return result

    def show_papers(self) -> str:
        papers = get_papers()
        if not papers:
            return "No papers tracked yet."
        result = f"📄 **All Papers ({len(papers)}):**\n\n"
        for p in papers:
            result += f"[{p['id']}] **{p['title']}**\n"
            result += f"  Status: {p['status']} | {p['created_at'][:10]}\n\n"
        return result

    def update_paper_status(self, paper_id: int, status: str, journal: str = "", decision: str = "") -> str:
        update_paper_status(paper_id, status, journal, decision)
        return f"✅ Paper {paper_id} updated to **{status}**"

    def improve_paper(self, paper_id: int, feedback: str) -> str:
        papers = get_papers()
        paper = next((p for p in papers if str(p["id"]) == str(paper_id)), None)
        if not paper:
            return f"❌ Paper ID {paper_id} not found."
        
        task = f"""Improve this research paper based on the following feedback:
Feedback: {feedback}

Original Paper excerpt (first 2000 chars):
{paper['content'][:2000]}...

Write a detailed revision plan and an improved introduction incorporating this feedback."""
        return self.run(task)

    def handle(self, task: str) -> str:
        return self.think_and_act(task)