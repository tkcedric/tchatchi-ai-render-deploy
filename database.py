import sqlite3
import os

# Le chemin du disque persistant sera fourni par Render via la variable d'environnement 'RENDER_DISK_PATH'.
# Si cette variable n'existe pas (ce qui sera le cas lors de l'exécution sur votre machine locale),
# le code utilisera '.' comme valeur par défaut, ce qui correspond au répertoire courant.
DATA_DIR = os.environ.get('RENDER_DISK_PATH', '.')

# On construit le chemin complet vers le fichier de la base de données.
# Sur Render, ce sera quelque chose comme '/var/data/tchatchi-data/stats.db'.
# En local, ce sera simplement 'stats.db' dans le dossier de votre projet.
DATABASE_FILE = os.path.join(DATA_DIR, 'stats.db')

def init_db():
    """
    Initialise la base de données. Crée le répertoire de données s'il n'existe pas,
    puis crée la table 'stats' si elle n'existe pas.
    Cette fonction est conçue pour être appelée au démarrage de l'application.
    """
    try:
        # S'assurer que le répertoire où la base de données doit être stockée existe.
        os.makedirs(DATA_DIR, exist_ok=True)
        
        conn = sqlite3.connect(DATABASE_FILE)
        cursor = conn.cursor()
        
        # Création de la table pour stocker les compteurs de statistiques.
        # 'stat_key' sera le nom du compteur (ex: 'lessons_generated')
        # 'stat_value' sera sa valeur numérique.
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS stats (
                stat_key TEXT PRIMARY KEY,
                stat_value INTEGER NOT NULL
            )
        ''')
        
        conn.commit()
        conn.close()
        print(f"Database initialized successfully at {DATABASE_FILE}")
        
    except Exception as e:
        print(f"ERROR during database initialization: {e}")


def increment_stat(key):
    """
    Incrémente la valeur d'un compteur de 1. Si le compteur n'existe pas, il est créé avec une valeur de 1.
    
    Args:
        key (str): Le nom du compteur à incrémenter (ex: 'lessons_generated').
    """
    try:
        conn = sqlite3.connect(DATABASE_FILE)
        cursor = conn.cursor()
        
        # On essaie d'abord de mettre à jour la valeur existante.
        cursor.execute('UPDATE stats SET stat_value = stat_value + 1 WHERE stat_key = ?', (key,))
        
        # Si aucune ligne n'a été mise à jour (ce qui signifie que la clé n'existait pas),
        # on l'insère avec une valeur initiale de 1.
        if cursor.rowcount == 0:
            cursor.execute('INSERT INTO stats (stat_key, stat_value) VALUES (?, ?)', (key, 1))
            
        conn.commit()
        conn.close()

    except Exception as e:
        print(f"ERROR incrementing stat '{key}': {e}")


def get_all_stats():
    """
    Récupère toutes les statistiques de la base de données et les retourne sous forme de dictionnaire.
    
    Returns:
        dict: Un dictionnaire où les clés sont les noms des compteurs et les valeurs sont leurs valeurs.
              Retourne un dictionnaire vide en cas d'erreur.
    """
    try:
        conn = sqlite3.connect(DATABASE_FILE)
        cursor = conn.cursor()
        
        cursor.execute('SELECT stat_key, stat_value FROM stats')
        stats = dict(cursor.fetchall())
        
        conn.close()
        return stats
        
    except Exception as e:
        print(f"ERROR fetching all stats: {e}")
        return {}


# Ce bloc de code ne s'exécutera que si vous lancez ce script directement
# avec la commande "python database.py". C'est utile pour initialiser
# la base de données manuellement en local pour la première fois.
if __name__ == '__main__':
    print("Running database initialization manually...")
    init_db()
    print("Manual initialization complete.")