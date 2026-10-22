FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libc6-dev \
    libasan8 \
    libubsan1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY . /app
RUN pip install --no-cache-dir -e .

ENTRYPOINT ["c-autograder"]
CMD ["submissions/add.c", "--rules", "rules/add_two_integers.json", "--out-dir", "reports/"]
