FROM python:3.8.5

# ffmpeg
RUN apt-get -y update
RUN apt-get install -y ffmpeg

# sox
RUN apt-get install -y sox

RUN pip install -U pip setuptools

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
RUN pip install -e .

ENV TEMP_DIR /tmp
ENV PORT ${PORT:-8000}

EXPOSE $PORT
CMD ["python", "pypedal/main.py"]
