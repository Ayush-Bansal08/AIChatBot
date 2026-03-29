from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, IpBlocked
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_core.prompts import PromptTemplate
from langchain_core.runnables import RunnableLambda, RunnableParallel
from langchain_core.output_parsers import StrOutputParser
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from dotenv import load_dotenv
load_dotenv()
print("Environment variables loaded.")

app = FastAPI()
print("FastAPI app initialized.")

embeddings = GoogleGenerativeAIEmbeddings(model="models/gemini-embedding-001")
print("Embeddings initialized.")
llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash", temperature=0.7)
print("LLM initialized.")

parser = StrOutputParser()
print("Output parser initialized.")

prompt = PromptTemplate(
    template="""
    You are a helpful assistant.
    Answer ONLY from the provided transcript context.
    If the context is insufficient, just say you don't know.

    {context}
    Question: {question}
    """,
    input_variables=['context', 'question']
)
print("Prompt template initialized.")


class ChatRequest(BaseModel):
    video_id: str      # ← user provides this
    question: str      # ← user provides this


def format_docs(context):
    print("Formatting retrieved documents.")
    return "\n\n".join(doc.page_content for doc in context)


def build_chain(video_id: str):
    print(f"Building chain for video_id: {video_id}")
    # Fetch transcript
    try:
        print("Fetching transcript from YouTube.")
        transcript_list = YouTubeTranscriptApi().fetch(video_id, languages=['en'])
        transcript = " ".join([t.text for t in transcript_list])
        print("Transcript fetched successfully.")
    except TranscriptsDisabled:
        print("Transcript fetch failed: transcripts are disabled.")
        raise HTTPException(status_code=400, detail="Transcripts are disabled for this video.")
    except IpBlocked:
        print("Transcript fetch failed: IP blocked by YouTube.")
        raise HTTPException(status_code=503, detail="YouTube blocked transcript requests. Try again later.")

    # Split and embed
    splitter = RecursiveCharacterTextSplitter(chunk_size=3000, chunk_overlap=200)
    print("Text splitter initialized.")
    chunks = splitter.create_documents([transcript])
    print(f"Transcript split into {len(chunks)} chunks.")
    vectorstore = FAISS.from_documents(chunks, embeddings)
    print("Vector store created.")
    retriever = vectorstore.as_retriever(search_type="similarity", search_kwargs={"k": 4})
    print("Retriever initialized.")

    # Build chain
    parallel_chain = RunnableParallel({
        'context': RunnableLambda(lambda x: x["question"]) | retriever | RunnableLambda(format_docs),
        'question': RunnableLambda(lambda x: x["question"])
    })
    print("Parallel chain initialized.")

    final_chain = parallel_chain | prompt | llm | parser
    print("Final chain ready.")
    return final_chain


@app.post("/chat")
async def chat(request: ChatRequest):
    print(f"Received /chat request for video_id: {request.video_id}")
    chain =  build_chain(request.video_id)
    print("Invoking chain.")
    result =  chain.invoke({"question": request.question})
    print("Chain invocation completed.")
    return {"answer": result}



