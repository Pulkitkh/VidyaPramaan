# Vidya Pramaan: single container (React build served by FastAPI), synthetic demo data baked in.
FROM node:20-bookworm-slim AS web
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PORT=8000 VP_DEMO_MODE=1
WORKDIR /app
COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt
COPY backend/ backend/
COPY sample-data/ sample-data/
COPY --from=web /web/dist frontend/dist
# Seed the synthetic national dataset at build time so the container starts instantly. The key file the
# seed generates is deleted: at runtime the issuer key is derived from VP_SECRET_KEY (or VP_ISSUER_KEY), and
# the seeded credentials and audit checkpoints are re-signed with it on first start (recorded in the audit trail).
RUN cd backend && python -m app.seed > /dev/null && rm -f data/issuer_ed25519.pem
RUN useradd --create-home app && chown -R app /app
USER app
WORKDIR /app/backend
EXPOSE 8000
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT} --proxy-headers --forwarded-allow-ips='*'"]
