# Dockerfile

# Étape 1: Définir notre image de base.
FROM python:3.11-slim

# Étape 2: Mettre à jour et installer les dépendances système.
# J'ajoute 'fonts-liberation' ici pour corriger la dernière erreur PDF.
RUN apt-get update && apt-get install -y --no-install-recommends \
    pandoc \
    texlive-xetex \
    texlive-fonts-recommended \
    texlive-lang-french \
    lmodern \
    fonts-liberation \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Étape 3: Définir le répertoire de travail.
WORKDIR /app

# Étape 4: Copier et installer les dépendances Python.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Étape 5: Copier le reste de notre application.
COPY . .

# Étape 6: Exposer le port.
EXPOSE 10000

# Étape 7: La commande pour lancer notre application.
CMD ["gunicorn", "--worker-tmp-dir", "/dev/shm", "--bind", "0.0.0.0:10000", "app:app"]