"""
index_syllabus.py

Script à lancer MANUELLEMENT à chaque fois qu'on veut ajouter ou mettre à
jour des programmes officiels MINESEC dans la base vectorielle du RAG.

Usage : python index_syllabus.py

Découpage au niveau LEÇON : chaque ligne du tableau officiel ("Catégorie
d'actions") devient un chunk avec son module parent, ses objectifs
("Exemples d'actions") et ses prérequis ("Savoirs essentiels").

Le module parent est détecté via le texte brut de la page (marqueur fiable
"TITRE DU MODULE :"), pas via la colonne du tableau lui-même — celle-ci
utilise des cellules fusionnées qui se comportent mal quand un module
s'étend sur plusieurs pages PDF.
"""

import os
import re
import logging
import pdfplumber
from openai import OpenAI
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

SOURCES = [
    {
        "fichier": "static/pdf/syllabus/Programme_informatique_6eme_et_5eme.pdf",
        "matiere": "Informatique",
        "classe": None,  # détection automatique (fichier multi-classes)
    },
    {
        "fichier": "static/pdf/syllabus/programme_seconde_EST.pdf",
        "matiere": "Informatique",
        "classe": "Seconde EST",
    },
    # NOUVEAU : ajouter une ligne ici pour chaque nouveau PDF de programme
]


def nettoyer_cellule(texte):
    """Remplace les caractères de puce spéciaux (bullets Wingdings) par des puces lisibles."""
    if not texte:
        return None
    return texte.replace('\uf0b7', '•').replace('\uf0d8', '-').strip()


def nettoyer_titre_lecon(titre):
    """
    Retire une puce parasite en début de titre, et coupe si plusieurs
    catégories se sont retrouvées collées dans la même cellule
    (artefact occasionnel de l'extraction de tableau en fin de page).
    """
    if not titre:
        return titre
    titre = re.sub(r'^[•\s]+', '', titre)
    titre = titre.split('•')[0].strip()
    return titre


def detecter_module_sur_page(texte_page):
    """
    Cherche un marqueur fiable de nouveau module dans le texte brut de la
    page (pas dans le tableau). Formats vus dans les PDF MINESEC :
    - "X.Y TITRE DU MODULE : ..."
    - "MODULE N : ..."
    """
    m = re.search(r'TITRE DU MODULE\s*:\s*(.+)', texte_page)
    if m:
        return m.group(1).strip()
    m2 = re.search(r'\bMODULE\s*\d\s*:\s*(.+)', texte_page)
    if m2:
        return m2.group(1).strip()
    return None


def extraire_lecons(chemin_pdf, matiere, classe_defaut=None):
    """
    Découpe un PDF de programme en chunks au niveau LEÇON, en combinant :
    - le texte brut de la page pour détecter fiablement le module en cours
    - le tableau structuré (extract_table) pour séparer chaque leçon avec
      ses objectifs et prérequis
    """
    chunks = []
    etat = {"module": None, "competences_module": None, "prerequis": None}
    classe_actuelle = classe_defaut

    with pdfplumber.open(chemin_pdf) as pdf:
        for page in pdf.pages:
            texte_page = page.extract_text() or ""

            # Détection du changement de classe (utile pour les PDF multi-classes)
            m = re.search(r'PRESENTATION DES MODULES DE LA CLASSE DE\s+([A-Za-zème\d]+)', texte_page)
            if m and not texte_page[m.end():m.end() + 3].strip().startswith('.'):
                classe_actuelle = m.group(1)

            # Détection du module en cours (source de vérité fiable)
            nouveau_module = detecter_module_sur_page(texte_page)
            if nouveau_module:
                etat["module"] = nouveau_module

            table = page.extract_table()
            if not table:
                continue

            for row in table:
                row = [nettoyer_cellule(c) for c in row]
                if len(row) < 5:
                    continue
                if row[0] and ('CADRE' in row[0] or 'Famille de' in row[0] or 'Classe de' in row[0]):
                    continue

                col_competences, col_lecon, col_objectifs, col_prerequis = row[1], row[2], row[3], row[4]

                if col_competences:
                    etat["competences_module"] = col_competences.replace('\n', ' ')
                if col_prerequis:
                    etat["prerequis"] = col_prerequis.replace('\n', ' ')

                if col_lecon and col_objectifs:
                    chunks.append({
                        "classe": classe_actuelle,
                        "matiere": matiere,
                        "module": etat["module"],
                        "competences_module": etat["competences_module"],
                        "lecon": nettoyer_titre_lecon(col_lecon.replace('\n', ' ')),
                        "objectifs": col_objectifs.replace('\n', ' '),
                        "prerequis": etat["prerequis"],
                    })
    return chunks


def construire_texte_embedding(chunk):
    """Assemble les champs structurés en un texte naturel pour l'embedding."""
    parties = [f"Matière : {chunk['matiere']}. Classe : {chunk['classe']}."]
    if chunk["module"]:
        parties.append(f"Module : {chunk['module']}.")
    if chunk["competences_module"]:
        parties.append(f"Compétences visées par le module : {chunk['competences_module']}.")
    parties.append(f"Leçon : {chunk['lecon']}.")
    parties.append(f"Objectifs de la leçon : {chunk['objectifs']}.")
    if chunk["prerequis"]:
        parties.append(f"Savoirs essentiels (prérequis) : {chunk['prerequis']}.")
    return " ".join(parties)


def generer_embedding(texte):
    reponse = openai_client.embeddings.create(model="text-embedding-3-small", input=texte)
    return reponse.data[0].embedding


def indexer_tout():
    total = 0
    for source in SOURCES:
        chemin = source["fichier"]
        if not os.path.exists(chemin):
            logger.warning(f"Fichier introuvable, ignoré : {chemin}")
            continue

        logger.info(f"Extraction de {chemin}...")
        chunks = extraire_lecons(chemin, source["matiere"], source.get("classe"))
        logger.info(f"  -> {len(chunks)} leçon(s) détectée(s)")

        # NOUVEAU : on supprime les anciennes entrées en se basant sur les
        # classes RÉELLEMENT trouvées dans ce fichier (pas sur la config),
        # ce qui fonctionne correctement dans les deux cas de figure :
        # - PDF multi-classes (ex: 6ème ET 5ème dans le même fichier)
        # - PDF classe unique (ex: Seconde EST)
        # Sans ça, réindexer un PDF "classe unique" pourrait supprimer par
        # erreur les données d'un AUTRE fichier de la même matière mais
        # couvrant une classe différente.
        classes_concernees = set(c["classe"] for c in chunks if c["classe"])
        if not classes_concernees:
            logger.warning(
                f"  -> Aucune classe détectée pour {chemin} (ni dans le PDF, ni via 'classe' dans SOURCES). "
                f"Vérifie la configuration de ce fichier."
            )
        for classe in classes_concernees:
            supabase.table("syllabus_chunks").delete().eq("matiere", source["matiere"]).eq("classe", classe).execute()
            logger.info(f"  -> Anciennes entrées supprimées pour [{classe}] {source['matiere']}")

        for chunk in chunks:
            texte_embedding = construire_texte_embedding(chunk)
            embedding = generer_embedding(texte_embedding)
            supabase.table("syllabus_chunks").insert({
                "classe": chunk["classe"],
                "matiere": chunk["matiere"],
                "module_titre": chunk["module"],
                "lecon_titre": chunk["lecon"],
                "objectifs": chunk["objectifs"],
                "prerequis": chunk["prerequis"],
                "contenu": texte_embedding,
                "embedding": embedding
            }).execute()
            logger.info(f"  -> Indexé : [{chunk['classe']}] {chunk['module']} / {chunk['lecon']}")
            total += 1

    logger.info(f"Indexation terminée : {total} leçons au total dans Supabase.")


if __name__ == "__main__":
    indexer_tout()