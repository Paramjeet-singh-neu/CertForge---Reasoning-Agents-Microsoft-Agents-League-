# CertForge Hosted Agent container image.
# Foundry Agent Service pulls this from Azure Container Registry, provisions a
# per-session sandbox, assigns an Entra agent identity, and exposes the endpoint.
#
# Python 3.13 per the Hosted Agents prerequisite.
FROM python:3.13-slim

WORKDIR /app

# Install dependencies first for better layer caching.
COPY certforge/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt fastapi uvicorn

# Copy the application (code, synthetic data, knowledge docs).
COPY certforge/ ./certforge/

# Hosted agents listen on 8088 (Responses + Invocations protocols).
EXPOSE 8088

# Secrets (GITHUB_TOKEN) are provided at runtime via a Key Vault connection,
# never baked into the image. Mock fallback keeps it runnable without secrets.
ENV CERTFORGE_MOCK=false

CMD ["python", "certforge/agent/main.py"]
