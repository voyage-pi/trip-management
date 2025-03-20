FROM python:3.12-slim

WORKDIR /app

COPY ./requirements.txt /code/requirements.txt


RUN pip install --no-cache-dir --upgrade -r /code/requirements.txt


COPY ./app /app

CMD ["fastapi", "run", "main.py", "--reload", "--port", "8080"]
