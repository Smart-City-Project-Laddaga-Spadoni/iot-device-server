bind = "0.0.0.0:5000"
workers = 2  # Numero di worker, puoi aumentare in base alle tue necessità
worker_class = "eventlet"  # Necessario per Flask-SocketIO