FROM python:3.8.5

# ffmpeg
RUN apt-get -y update
RUN apt-get install -y ffmpeg

# sox
RUN apt-get install -y sox

# TODO: cache pip install
RUN pip install -U pip
COPY . .
RUN pip install .

ENV TEMP_PATH /tmp
ENV PORT $PORT
CMD ["python", "pypedal/main.py"]
