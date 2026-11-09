import os

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    embedding_model: str = "text-embedding-3-small"
    langsmith_tracing: bool = True
    langsmith_api_key: str = ""
    langsmith_project: str = "customer-support-assistant"
    langsmith_endpoint: str = "https://api.smith.langchain.com"
    customer_workbook: str = "data/Sample_Customer_Data.xlsx"
    refund_policy_pdf: str = "data/Detailed_Sample_Refund_Policy.pdf"
    faiss_index_dir: str = "data/faiss_index"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()

# LangChain and LangGraph read tracing configuration from the process
# environment. Pydantic reads .env values without exporting them, so export
# the settings here for local Uvicorn runs as well as Docker.
if settings.langsmith_api_key:
    os.environ["LANGSMITH_TRACING"] = str(settings.langsmith_tracing).lower()
    os.environ["LANGSMITH_API_KEY"] = settings.langsmith_api_key
    os.environ["LANGSMITH_PROJECT"] = settings.langsmith_project
    os.environ["LANGSMITH_ENDPOINT"] = settings.langsmith_endpoint
