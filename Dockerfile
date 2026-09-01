FROM node:22-alpine AS frontend-build

WORKDIR /frontend

COPY package*.json ./
RUN npm ci

COPY index.html ./
COPY public ./public
COPY src ./src
COPY postcss.config.js tailwind.config.js vite.config.js ./

RUN npm run build


FROM python:3.12-slim

WORKDIR /app

COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

COPY backend/app ./backend/app
COPY --from=frontend-build /frontend/dist ./backend/static

ENV PYTHONPATH=/app/backend

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-10000}"]
