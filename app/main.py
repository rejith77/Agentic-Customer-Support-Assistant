from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from app.config import settings
from app.data_store import CustomerData
from app.graph import SupportAgent
from app.policy_rag import PolicyRetriever


class ChatRequest(BaseModel):
    question: str = Field(min_length=2, max_length=2000)


class ChatResponse(BaseModel):
    answer: str
    route: str
    facts: list[str] = []
    evidence: list[str] = []


@asynccontextmanager
async def lifespan(app: FastAPI):
    data = CustomerData(settings.customer_workbook)
    policy = PolicyRetriever()
    app.state.agent = SupportAgent(data, policy)
    yield


app = FastAPI(title="Agentic AI Customer Support", version="1.0.0", lifespan=lifespan)
LOCAL_ORIGIN_REGEX = r"^https?://(localhost|127\.0\.0\.1|0\.0\.0\.0)(:\d+)?$"
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=LOCAL_ORIGIN_REGEX,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type"],
    allow_private_network=True,
)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/", include_in_schema=False)
def home():
    return RedirectResponse(url="/chat")


@app.get("/chat", include_in_schema=False)
def chat_page():
    return FileResponse(Path(__file__).with_name("chat.html"), media_type="text/html")


@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest):
    try:
        return app.state.agent.ask(request.question)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Unable to answer this request: {exc}") from exc
