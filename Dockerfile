FROM python:3.12.0

WORKDIR /app

COPY . .

RUN pip install -r requirements.txt
RUN pip install redis
RUN pip install rq redis
RUN pip install Flask-CORS


EXPOSE 5000

ENV REDIS_URL=redis://host.docker.internal
ENV DB_HOST=host.docker.internal
ENV DB_USER=postgres
ENV DB_PASSWORD=AtOm78180
ENV DB_PORT=5432
ENV DB_NAME=bd_twa_projet
ENV FLASK_APP=app
ENV FLASK_DEBUG=1

CMD ["flask", "run", "--host", "0.0.0.0"]