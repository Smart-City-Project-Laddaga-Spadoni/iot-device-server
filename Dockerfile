# Usa un'immagine base di Python
FROM python:3.9-slim

# Imposta la directory di lavoro
WORKDIR /app

# Copia i file requirements.txt e installa le dipendenze
COPY requirements.txt requirements.txt
RUN pip install -r requirements.txt

# Copia il resto del codice dell'applicazione
COPY . .

# Esporta le variabili d'ambiente
ENV FLASK_RUN_HOST=0.0.0.0
ENV FLASK_RUN_PORT=5000

# Comando per avviare l'applicazione
CMD ["flask", "run", "--host=0.0.0.0", "--port=5000"]