FROM python:3.12-slim

WORKDIR /app

# Dependencies layer — cached khi code thay đổi nhưng deps không đổi
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Application code
COPY . .

CMD ["python", "bot.py"]
