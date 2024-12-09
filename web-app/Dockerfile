FROM python:3.9-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY static/assets /app/assets
COPY . .
EXPOSE 5000
ENV FLASK_ENV=development
ENV FLASK_DEBUG=1
CMD ["python", "app.py"]