FROM python:3.12-slim

WORKDIR /app

COPY ./requirements.txt /code/requirements.txt


RUN pip install --no-cache-dir --upgrade -r /code/requirements.txt


COPY ./app /app

CMD ["uvicorn", "main:app", "--reload", "--host", "0.0.0.0", "--port", "8080"]
