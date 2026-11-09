from pathlib import Path

from langchain_community.document_loaders import PyPDFLoader
from langchain_community.vectorstores import FAISS
from langchain_openai import OpenAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.config import settings


class PolicyRetriever:
    def __init__(self):
        if not settings.openai_api_key:
            raise ValueError("OPENAI_API_KEY is required to build the refund policy search index")
        self.embeddings = OpenAIEmbeddings(model=settings.embedding_model, api_key=settings.openai_api_key)
        index_path = Path(settings.faiss_index_dir)
        if (index_path / "index.faiss").exists() and (index_path / "index.pkl").exists():
            self.vectorstore = FAISS.load_local(
                str(index_path), self.embeddings, allow_dangerous_deserialization=True
            )
        else:
            pdf_path = Path(settings.refund_policy_pdf)
            if not pdf_path.exists():
                raise FileNotFoundError(f"Refund policy PDF not found: {pdf_path}")
            pages = PyPDFLoader(str(pdf_path)).load()
            chunks = RecursiveCharacterTextSplitter(chunk_size=850, chunk_overlap=120).split_documents(pages)
            self.vectorstore = FAISS.from_documents(chunks, self.embeddings)
            index_path.parent.mkdir(parents=True, exist_ok=True)
            self.vectorstore.save_local(str(index_path))
        self.retriever = self.vectorstore.as_retriever(search_kwargs={"k": 4})

    def search(self, query: str, k: int = 4) -> list[str]:
        retriever = self.retriever if k == 4 else self.vectorstore.as_retriever(search_kwargs={"k": k})
        docs = retriever.invoke(query)
        return [doc.page_content for doc in docs]
