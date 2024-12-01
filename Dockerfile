FROM python:3.9-slim
WORKDIR /web-app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
WORKDIR /web-app/routes
EXPOSE 5000

CMD ["python", "../web-app/routes/app.py"]