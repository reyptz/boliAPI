# Utiliser une image Python officielle en tant que base
FROM python:3.10-slim

# Définir le répertoire de travail
WORKDIR /app

# Copier le fichier requirements.txt
COPY requirements.txt .

# Installer les dépendances
RUN pip install --no-cache-dir -r requirements.txt

# Copier le reste des fichiers de l'application
COPY . .

# Exposer le port sur lequel FastAPI écoute
EXPOSE 8000

# Commande pour démarrer l'application avec Uvicorn
CMD ["uvicorn", "main:app", "--host", "[IP_ADDRESS]", "--port", "8000", "--reload"]