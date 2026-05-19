FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY nas_control_plane /app/nas_control_plane
COPY shared /app/shared
COPY terminal_agent /app/terminal_agent

EXPOSE 8765

CMD ["python", "-m", "nas_control_plane.server"]
