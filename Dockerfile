# BillCheck for Hugging Face Spaces (Docker SDK): runs as user 1000 on port 7860.
# Secrets (Space settings, never in this file): PAYPAL_CLIENT_ID, PAYPAL_CLIENT_SECRET, FIREWORKS_API_KEY.
FROM python:3.12-slim
RUN useradd -m -u 1000 user
USER user
ENV HOME=/home/user PATH=/home/user/.local/bin:$PATH PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    BILLCHECK_FRAME_ANCESTORS=https://huggingface.co BILLCHECK_DAILY_CAP_USD=2.00 \
    BILLCHECK_CLIENT_IP_HEADER=X-Forwarded-For
WORKDIR /home/user/app
COPY --chown=user pyproject.toml README.md LICENSE ./
COPY --chown=user src ./src
RUN pip install --no-cache-dir --user .
EXPOSE 7860
CMD ["uvicorn", "billcheck.web.app:app", "--host", "0.0.0.0", "--port", "7860"]
