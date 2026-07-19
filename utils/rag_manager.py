"""
utils/rag_manager.py
A semantic retrieval-augmented memory manager.
Indexes resume text and provides semantic QA over candidate history.
"""

import os
import json
import logging
import math
import re
from dotenv import load_dotenv
import litellm

load_dotenv()
logger = logging.getLogger(__name__)

DB_PATH = "data/candidate_rag.json"

def get_embedding(text: str) -> list:
    """
    Generate text embeddings using LiteLLM.
    Falls back to a empty list on failure or if no OpenAI API key is present.
    """
    if not text.strip() or not os.getenv("OPENAI_API_KEY"):
        return []
    try:
        model = os.getenv("EMBEDDING_MODEL", "openai/text-embedding-3-small")
        response = litellm.embedding(model=model, input=[text])
        return response["data"][0]["embedding"]
    except Exception as e:
        logger.error(f"[RAG Embedding] Failed: {e}")
        return []

def cosine_similarity(v1: list, v2: list) -> float:
    if not v1 or not v2 or len(v1) != len(v2):
        return 0.0
    dot_product = sum(a * b for a, b in zip(v1, v2))
    norm_a = math.sqrt(sum(a * a for a in v1))
    norm_b = math.sqrt(sum(b * b for b in v2))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot_product / (norm_a * norm_b)

def chunk_text(text: str, chunk_size: int = 500, overlap: int = 100) -> list:
    """Chunks text into small segments with overlap."""
    words = text.split()
    chunks = []
    i = 0
    while i < len(words):
        chunk_words = words[i:i + chunk_size]
        chunks.append(" ".join(chunk_words))
        i += chunk_size - overlap
    return chunks

def index_resume(resume_text: str) -> int:
    """Chunks and embeds the candidate's resume, storing results in a local JSON database."""
    chunks = chunk_text(resume_text, chunk_size=100, overlap=20)
    data = []
    
    for i, c in enumerate(chunks):
        embedding = get_embedding(c)
        data.append({
            "id": i,
            "text": c,
            "embedding": embedding
        })
        
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    with open(DB_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f)
        
    return len(data)

def tf_idf_fallback_search(query: str, records: list, limit: int = 3) -> list:
    """Simulates keyword similarity search when vector API is unavailable."""
    query_words = set(re.findall(r"\w+", query.lower()))
    scored_records = []
    for rec in records:
        text_words = re.findall(r"\w+", rec["text"].lower())
        matches = len(query_words.intersection(text_words))
        score = matches / max(1, len(query_words))
        scored_records.append((score, rec))
        
    scored_records.sort(key=lambda x: x[0], reverse=True)
    return [rec for score, rec in scored_records[:limit] if score > 0]

def query_candidate_history(query: str, limit: int = 3) -> str:
    """
    Search indexed candidate history for matching chunks.
    Uses vector cosine similarity, falling back to keyword overlaps.
    """
    if not os.path.exists(DB_PATH):
        return "No resume indexes found. Please upload and index your resume first."
        
    try:
        with open(DB_PATH, "r", encoding="utf-8") as f:
            records = json.load(f)
    except Exception:
        return "Error reading indices."

    query_vector = get_embedding(query)
    
    if query_vector and any(rec.get("embedding") for rec in records):
        # Perform cosine search
        matches = []
        for rec in records:
            emb = rec.get("embedding")
            if not emb:
                continue
            sim = cosine_similarity(query_vector, emb)
            matches.append((sim, rec))
        matches.sort(key=lambda x: x[0], reverse=True)
        results = [rec for sim, rec in matches[:limit]]
    else:
        # Fallback to TF-IDF logic
        results = tf_idf_fallback_search(query, records, limit)
        
    if not results:
        return "No relevant sections found in your candidate profile."
        
    context = "\n\n".join([f"--- Section ---\n{res['text']}" for res in results])
    
    # Run completion to build answer
    prompt = f"""You are CareerAgent's internal RAG oracle.
Below are relevant snippets of the candidate's resume/profile:
{context}

Question:
{query}

Using ONLY the snippets above, construct a direct, concise response answering the candidate's question. Focus on evidence from these snippets. If the snippet doesn't answer it, tell them honestly.
"""
    try:
        # Prioritize OpenRouter, fallback to Groq
        if os.getenv("OPENROUTER_API_KEY"):
            model = "openrouter/google/gemma-4-26b-a4b-it:free"
            api_key = os.getenv("OPENROUTER_API_KEY")
        else:
            model = os.getenv("LLM_MODEL", "groq/llama-3.3-70b-versatile")
            api_key = os.getenv("GROQ_API_KEY")
            
        r = litellm.completion(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            max_tokens=600,
            api_key=api_key
        )
        return r.choices[0].message.content.strip()
    except Exception as e:
        logger.error(f"[RAG Oracle Completion Failed]: {e}")
        return f"Found relevant sections:\n\n{context}"
