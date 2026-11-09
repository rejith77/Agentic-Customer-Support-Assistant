FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
COPY Sample_Customer_Data.xlsx Detailed_Sample_Refund_Policy.pdf ./data/

ENV CUSTOMER_WORKBOOK=/app/data/Sample_Customer_Data.xlsx \
    REFUND_POLICY_PDF=/app/data/Detailed_Sample_Refund_Policy.pdf \
    FAISS_INDEX_DIR=/app/data/faiss_index

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
