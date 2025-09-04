# Dockerfile

# Étape 1: Définir notre image de base. On prend une version officielle de Python.
FROM python:3.11-slim

# Étape 2: Définir le répertoire de travail à l'intérieur de notre machine virtuelle.
WORKDIR /app

# Étape 3: Mettre à jour et installer les dépendances système (pandoc et LaTeX).
# C'est ici que nous contournons les limitations de Render.
# 'RUN' s'exécute avec les pleins droits d'administrateur.
RUN apt-get update && apt-get install -y --no-install-recommends \
    pandoc \
    texlive-xetex \
    texlive-fonts-recommended \
    texlive-lang-french \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Étape 4: Copier le fichier des dépendances Python et les installer.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Étape 5: Copier tout le reste de notre application dans la machine.
COPY . .

# Étape 6: Exposer le port que Gunicorn utilisera. Render s'y connectera.
EXPOSE 10000

# Étape 7: La commande pour lancer notre application.
# Render utilisera cette commande au démarrage.
CMD ["gunicorn", "--worker-tmp-dir", "/dev/shm", "--bind", "0.0.0.0:10000", "app:app"]