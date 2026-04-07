import re
import time
from datetime import datetime, timezone
from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, IpBlocked
from langchain_text_splitters import RecursiveCharacterTextSplitter
from transformers import pipeline
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_community.llms import HuggingFacePipeline
from langchain_core.prompts import PromptTemplate
from langchain_core.runnables import RunnableLambda, RunnableParallel
from langchain_core.output_parsers import StrOutputParser
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from dotenv import load_dotenv
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[1]
load_dotenv(BASE_DIR / "backend" / ".env")
load_dotenv(BASE_DIR / ".env")
print("Environment variables loaded.")


app = FastAPI()
print("FastAPI app initialized.")


embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
print("Embeddings initialized.")


hf_pipe = pipeline(
    "text-generation",
    model="Qwen/Qwen2.5-0.5B-Instruct",
    max_new_tokens=350,
    do_sample=False,
    return_full_text=False,   
    eos_token_id=None,
    pad_token_id=151643,      
)
llm = HuggingFacePipeline(pipeline=hf_pipe)
print("LLM initialized.")



PROMPT_LEAK_PATTERNS = [
    r"^.*?Context\s*:\s*\[.*?\]\s*",
    r"^.*?Answer\s*:\s*",
    r"\bContext\s*:\s*\[The narrator\].*",
    r"\[The narrator\].*",
]


META_PATTERNS = [
    r"I do not need to provide.*",
    r"The (summary|answer) is (concise|brief|focused|correct|accurate).*",
    r"The key takeaway is.*",
    r"Overall,? the (speaker|narrator|video).*",
    r"In (summary|conclusion|short),?.*",
    r"I hope this (helps|answers|clarifies).*",
    r"Please note that.*",
    r"As (an AI|a helpful assistant|a language model).*",
    r"Note\s*:.*",
    r"This (is a|provides a) (concise|brief|short) summary.*",
    r"The above (summary|answer|response).*",
    r"I have (provided|given|summarized).*",
]


def clean_output(text: str) -> str:
    """
    Full cleaning pipeline applied to every model output.
    Order: strip leaks → strip meta → dedupe sentences → trim to complete sentence.
    """
    if not text:
        return ""

    text = text.strip()

   
    for pattern in PROMPT_LEAK_PATTERNS:
        text = re.sub(pattern, "", text, flags=re.IGNORECASE | re.DOTALL).strip()

    
    answer_match = re.search(r"\bAnswer\s*:\s*", text, re.IGNORECASE)
    if answer_match:
        text = text[answer_match.end():].strip()

    
    sentences = re.split(r'(?<=[.!?])\s+', text)
    cleaned = [
        s for s in sentences
        if not any(re.search(p, s, re.IGNORECASE) for p in META_PATTERNS)
    ]
    text = " ".join(cleaned).strip()

    
    unique, seen_normalized = [], set()
    for s in re.split(r'(?<=[.!?])\s+', text):
        norm = re.sub(r'\s+', ' ', s.strip().lower())
        if norm not in seen_normalized and len(s.strip()) > 5:
            seen_normalized.add(norm)
            unique.append(s.strip())
    text = " ".join(unique).strip()

    
    if not text:
        return ""
    boundaries = list(re.finditer(r'(?<=[.!?])\s', text))
    if boundaries:
        text = text[:boundaries[-1].start() + 1].strip()
    elif text[-1] not in ".!?":
        last_punct = max(text.rfind("."), text.rfind("!"), text.rfind("?"))
        if last_punct > 0:
            text = text[:last_punct + 1].strip()

    return text.strip()



class RobustOutputParser(StrOutputParser):
    def parse(self, text: str) -> str:
        raw = super().parse(text)
        return clean_output(raw)


parser = RobustOutputParser()
print("Output parser initialized.")



prompt = PromptTemplate(
    template="""<|im_start|>system
You are a precise assistant. Use only the transcript excerpts below to answer.
Rules you must follow without exception:
1. Write only the answer — no explanations, no preamble, no commentary about your answer.
2. Do NOT repeat or rephrase the context. Do NOT echo back what was given to you.
3. Do NOT include phrases like "The summary is", "Overall", "In conclusion", "I hope this helps".
4. End every sentence with proper punctuation. Never stop mid-sentence.
5. Maximum 4 sentences. Be direct and factual.
<|im_end|>
<|im_start|>user
Transcript excerpts:
{context}

{question}
<|im_end|>
<|im_start|>assistant
""",
    input_variables=["context", "question"],
)
print("Prompt template initialized.")



SUMMARY_KEYWORDS = {
    "summary", "summarize", "summarise", "overview", "about",
    "explain", "what is", "what's", "describe", "tell me about",
    "what does", "gist", "main point", "key point",
}


def detect_k(question: str) -> int:
    q = question.lower()
    return 6 if any(kw in q for kw in SUMMARY_KEYWORDS) else 3



retriever_cache: dict = {}



class ChatRequest(BaseModel):
    video_id: str
    question: str


def record_step(process_log, name: str, status: str, started_at: float, details: str = ""):
    elapsed_ms = int((time.perf_counter() - started_at) * 1000)
    process_log.append(
        {
            "step": name,
            "status": status,
            "duration_ms": elapsed_ms,
            "details": details,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    )



def format_docs(docs) -> str:
    return "\n\n".join(doc.page_content for doc in docs)


def fetch_transcript(video_id: str) -> str:
    """Fetch, clean and return raw transcript text."""
    try:
        print(f"Fetching transcript for: {video_id}")
        transcript_list = YouTubeTranscriptApi().fetch(video_id, languages=["en"])
        raw = " ".join(t.text for t in transcript_list)
        raw = re.sub(r'\[.*?\]', '', raw)        # Remove [Music], [Applause] etc.
        raw = re.sub(r'\s+', ' ', raw).strip()
        print(f"Transcript fetched: {len(raw)} characters.")
        return raw
    except TranscriptsDisabled:
        raise HTTPException(status_code=400, detail="Transcripts are disabled for this video.")
    except IpBlocked:
        raise HTTPException(status_code=503, detail="YouTube blocked transcript requests. Try again later.")
    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Failed to fetch transcript. Check video ID and availability. ({exc})"
        ) from exc


def get_or_build_vectorstore(video_id: str):
    """Return cached vector store payload or build a new one from scratch."""
    if video_id in retriever_cache:
        print("Using cached vector store.")
        payload = retriever_cache[video_id]
        return payload, "cache_hit"

    transcript = fetch_transcript(video_id)
    splitter = RecursiveCharacterTextSplitter(chunk_size=900, chunk_overlap=120)
    chunks = splitter.create_documents([transcript])
    print(f"Split into {len(chunks)} chunks.")

    vectorstore = FAISS.from_documents(chunks, embeddings)
    payload = {
        "vectorstore": vectorstore,
        "chunk_count": len(chunks),
        "transcript_chars": len(transcript),
    }
    retriever_cache[video_id] = payload
    print("Vector store built and cached.")
    return payload, "cache_miss"


def prepare_prompt(video_id: str, question: str, process_log: list):
    k = detect_k(question)
    step_start = time.perf_counter()
    vector_payload, cache_state = get_or_build_vectorstore(video_id)
    record_step(
        process_log,
        "Vector store preparation",
        "done",
        step_start,
        f"cache={cache_state}, chunks={vector_payload['chunk_count']}, transcript_chars={vector_payload['transcript_chars']}",
    )

    step_start = time.perf_counter()
    retriever = vector_payload["vectorstore"].as_retriever(
        search_type="similarity",
        search_kwargs={"k": k}
    )
    docs = retriever.invoke(question)
    context = format_docs(docs)
    record_step(
        process_log,
        "Context retrieval",
        "done",
        step_start,
        f"k={k}, docs_returned={len(docs)}",
    )

    step_start = time.perf_counter()
    prompt_text = prompt.format(context=context, question=question)
    record_step(
        process_log,
        "Prompt assembly",
        "done",
        step_start,
        f"context_chars={len(context)}",
    )

    return prompt_text



@app.post("/chat")
async def chat(request: ChatRequest):
    print(f"\n── /chat ── video={request.video_id} | q='{request.question}'")
    try:
        process_log = []
        total_start = time.perf_counter()

        prep_start = time.perf_counter()
        prompt_text = prepare_prompt(request.video_id, request.question, process_log)
        record_step(process_log, "Preparation complete", "done", prep_start)

        for attempt in range(2):
            print(f"Attempt {attempt + 1}/2 ...")
            generation_start = time.perf_counter()
            raw = llm.invoke(prompt_text)
            result = parser.parse(raw if isinstance(raw, str) else str(raw)).strip()
            record_step(
                process_log,
                "Answer generation",
                "done",
                generation_start,
                f"attempt={attempt + 1}, chars={len(result)}",
            )
            print(f"Cleaned result: '{result}'")

            if result:
                record_step(
                    process_log,
                    "Request complete",
                    "done",
                    total_start,
                    f"total_ms={int((time.perf_counter() - total_start) * 1000)}",
                )
                return {"answer": result, "process": process_log}

            print("Empty result — retrying...")
            process_log.append(
                {
                    "step": "Retry decision",
                    "status": "retry",
                    "duration_ms": 0,
                    "details": f"Empty answer on attempt {attempt + 1}",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
            )

        raise HTTPException(
            status_code=500,
            detail="Model returned an empty response after 2 attempts. Try rephrasing your question."
        )

    except HTTPException:
        raise
    except Exception as exc:
        print(f"Unexpected error: {exc}")
        raise HTTPException(status_code=500, detail=f"Failed to generate response: {exc}") from exc



@app.get("/health")
async def health():
    return {
        "status": "ok",
        "model": "Qwen/Qwen2.5-0.5B-Instruct",
        "cached_videos": list(retriever_cache.keys()),
    }
