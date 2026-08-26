"""
index_syllabus.py

Script à lancer MANUELLEMENT pour indexer les programmes officiels MINESEC
dans la base vectorielle du RAG.

Usage : python index_syllabus.py

NOUVEAU : lit directement les PDF depuis l'intérieur du zip, sans extraction
manuelle ni renommage de fichiers — dépose juste le zip au chemin indiqué
dans ZIP_PATH ci-dessous.
"""

import os
import re
import io
import zipfile
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

# NOUVEAU : chemin vers le zip. Dépose-le ici, sans le décompresser.
ZIP_PATH = "static/pdf/syllabus/PROGRAMMES_D_ETUDE_MINESEC.zip"

# =======================================================================
# CONFIGURATION : chaque entrée référence un fichier À L'INTÉRIEUR du zip
# (chemin exact, avec accents). "classe" à None si le PDF couvre plusieurs
# classes (détection automatique).
# =======================================================================
SOURCES = [
    # --- MATHÉMATIQUES ---
    {"fichier": "PROGRAMMES D'ETUDE MINESEC/SYSTEME FRANCOPHONE/ENSEIGNEMENT GENERAL/1ER CYCLE/PREMIER CYCLE/PROGRAMME_MATH _6ème _5ème.pdf", "matiere": "Mathématiques", "classe": None},
    {"fichier": "PROGRAMMES D'ETUDE MINESEC/SYSTEME FRANCOPHONE/ENSEIGNEMENT GENERAL/1ER CYCLE/PREMIER CYCLE/programme_Mathématiques_4ème_3ème.pdf", "matiere": "Mathématiques", "classe": None},

    # --- SCIENCES / PHYSIQUE / CHIMIE / SVT ---
    {"fichier": "PROGRAMMES D'ETUDE MINESEC/SYSTEME FRANCOPHONE/ENSEIGNEMENT GENERAL/1ER CYCLE/PREMIER CYCLE/programme_sciences_6et5.pdf", "matiere": "Sciences", "classe": None},
    {"fichier": "PROGRAMMES D'ETUDE MINESEC/SYSTEME FRANCOPHONE/ENSEIGNEMENT GENERAL/2ND CYCLE/programme_de_Physique_2ndeC.pdf", "matiere": "Physique", "classe": "Seconde C"},
    {"fichier": "PROGRAMMES D'ETUDE MINESEC/SYSTEME FRANCOPHONE/ENSEIGNEMENT GENERAL/2ND CYCLE/programme_de_chimie_2ndeC.pdf", "matiere": "Chimie", "classe": "Seconde C"},
    {"fichier": "PROGRAMMES D'ETUDE MINESEC/SYSTEME FRANCOPHONE/ENSEIGNEMENT GENERAL/2ND CYCLE/Programme_de_SVTEEHB_Classe_de_2nde.pdf", "matiere": "SVT", "classe": "Seconde"},

    # --- HISTOIRE / GÉOGRAPHIE ---
    {"fichier": "PROGRAMMES D'ETUDE MINESEC/SYSTEME FRANCOPHONE/ENSEIGNEMENT GENERAL/1ER CYCLE/PREMIER CYCLE/programme_HISTOIRE_6e_5e_ESG.pdf", "matiere": "Histoire", "classe": None},
    {"fichier": "PROGRAMMES D'ETUDE MINESEC/SYSTEME FRANCOPHONE/ENSEIGNEMENT GENERAL/1ER CYCLE/PREMIER CYCLE/programme_Histoire_4ème_3ème.pdf", "matiere": "Histoire", "classe": None},
    {"fichier": "PROGRAMMES D'ETUDE MINESEC/SYSTEME FRANCOPHONE/ENSEIGNEMENT GENERAL/2ND CYCLE/PROGRAMME_HISTOIRE_Tle_ESG.pdf", "matiere": "Histoire", "classe": "Terminale ESG"},
    {"fichier": "PROGRAMMES D'ETUDE MINESEC/SYSTEME FRANCOPHONE/ENSEIGNEMENT GENERAL/2ND CYCLE/PROGRAMME_HISTOIRE_Tle_EST.pdf", "matiere": "Histoire", "classe": "Terminale EST"},
    {"fichier": "PROGRAMMES D'ETUDE MINESEC/SYSTEME FRANCOPHONE/ENSEIGNEMENT GENERAL/1ER CYCLE/PREMIER CYCLE/programme_Géographie_4ème_3ème.pdf", "matiere": "Géographie", "classe": None},
    {"fichier": "PROGRAMMES D'ETUDE MINESEC/SYSTEME FRANCOPHONE/ENSEIGNEMENT GENERAL/1ER CYCLE/PREMIER CYCLE/programme_GEOGRAPHIE_6e_5e ESG.pdf", "matiere": "Géographie", "classe": None},
    {"fichier": "PROGRAMMES D'ETUDE MINESEC/SYSTEME FRANCOPHONE/ENSEIGNEMENT GENERAL/2ND CYCLE/PROGRAMME_GEOGRAPHIE_Tle_ESG.pdf", "matiere": "Géographie", "classe": "Terminale ESG"},
    {"fichier": "PROGRAMMES D'ETUDE MINESEC/SYSTEME FRANCOPHONE/ENSEIGNEMENT GENERAL/2ND CYCLE/PROGRAMME_GEOGRAPHIE_Tle_EST.pdf", "matiere": "Géographie", "classe": "Terminale EST"},

    # --- FRANÇAIS / ANGLAIS ---
    {"fichier": "PROGRAMMES D'ETUDE MINESEC/SYSTEME FRANCOPHONE/ENSEIGNEMENT GENERAL/1ER CYCLE/PREMIER CYCLE/programmeFrancais_1erelangue_4em3eme.pdf", "matiere": "Français", "classe": None},
    {"fichier": "PROGRAMMES D'ETUDE MINESEC/SYSTEME FRANCOPHONE/ENSEIGNEMENT GENERAL/2ND CYCLE/PROGRAMMES_FRANCAIS_SECONDE.pdf", "matiere": "Français", "classe": "Seconde"},
    {"fichier": "PROGRAMMES D'ETUDE MINESEC/SYSTEME FRANCOPHONE/ENSEIGNEMENT GENERAL/1ER CYCLE/PREMIER CYCLE/programme_ANGLAIS Syllabus_4e_ESG.pdf", "matiere": "Anglais", "classe": "4ème"},
    {"fichier": "PROGRAMMES D'ETUDE MINESEC/SYSTEME FRANCOPHONE/ENSEIGNEMENT GENERAL/1ER CYCLE/PREMIER CYCLE/programme_ANGLAIS_SBEP_4e.pdf", "matiere": "Anglais (SBEP)", "classe": "4ème"},
    {"fichier": "PROGRAMMES D'ETUDE MINESEC/SYSTEME FRANCOPHONE/ENSEIGNEMENT GENERAL/2ND CYCLE/PROGRAMME_ANGLAIS_SYLLABUS_2DE.pdf", "matiere": "Anglais", "classe": "Seconde"},
    {"fichier": "PROGRAMMES D'ETUDE MINESEC/SYSTEME FRANCOPHONE/ENSEIGNEMENT GENERAL/2ND CYCLE/PROGRAMME_ANGLAIS_SYLLABUS GENERAL_Tle.docx prevalidated.pdf", "matiere": "Anglais", "classe": "Terminale"},

    # --- AUTRES LANGUES ---
    {"fichier": "PROGRAMMES D'ETUDE MINESEC/SYSTEME FRANCOPHONE/ENSEIGNEMENT GENERAL/1ER CYCLE/PREMIER CYCLE/programme_Allemand4e_et_3e.pdf", "matiere": "Allemand", "classe": None},
    {"fichier": "PROGRAMMES D'ETUDE MINESEC/SYSTEME FRANCOPHONE/ENSEIGNEMENT GENERAL/1ER CYCLE/PREMIER CYCLE/programme_Arabe_4eme3eme.pdf", "matiere": "Arabe", "classe": None},
    {"fichier": "PROGRAMMES D'ETUDE MINESEC/SYSTEME FRANCOPHONE/ENSEIGNEMENT GENERAL/1ER CYCLE/PREMIER CYCLE/programme_CHINOIS_4eme3eme.pdf", "matiere": "Chinois", "classe": None},
    {"fichier": "PROGRAMMES D'ETUDE MINESEC/SYSTEME FRANCOPHONE/ENSEIGNEMENT GENERAL/1ER CYCLE/PREMIER CYCLE/programme_Espagnol_4eme3eme.pdf", "matiere": "Espagnol", "classe": None},
    {"fichier": "PROGRAMMES D'ETUDE MINESEC/SYSTEME FRANCOPHONE/ENSEIGNEMENT GENERAL/1ER CYCLE/PREMIER CYCLE/programme_latin_grec_4eme3eme.pdf", "matiere": "Latin-Grec", "classe": None},

    # --- ÉDUCATION CIVIQUE, ARTS, EPS, TECHNOLOGIE ---
    {"fichier": "PROGRAMMES D'ETUDE MINESEC/SYSTEME FRANCOPHONE/ENSEIGNEMENT GENERAL/1ER CYCLE/PREMIER CYCLE/programme_ECM_6E_5E.pdf", "matiere": "Éducation à la Citoyenneté et à la Morale", "classe": None},
    {"fichier": "PROGRAMMES D'ETUDE MINESEC/SYSTEME FRANCOPHONE/ENSEIGNEMENT GENERAL/1ER CYCLE/PREMIER CYCLE/programme_ECM 4ème et 3ème.pdf", "matiere": "Éducation à la Citoyenneté et à la Morale", "classe": None},
    {"fichier": "PROGRAMMES D'ETUDE MINESEC/SYSTEME FRANCOPHONE/ENSEIGNEMENT GENERAL/1ER CYCLE/PREMIER CYCLE/Programme_Education_artistique_4e_3e.pdf", "matiere": "Éducation Artistique", "classe": None},
    {"fichier": "PROGRAMMES D'ETUDE MINESEC/SYSTEME FRANCOPHONE/ENSEIGNEMENT GENERAL/2ND CYCLE/Programme_des_arts_2nde.pdf", "matiere": "Arts", "classe": "Seconde"},
    {"fichier": "PROGRAMMES D'ETUDE MINESEC/SYSTEME FRANCOPHONE/ENSEIGNEMENT GENERAL/2ND CYCLE/PROGRAMME_LIT_POS_LEAN.pdf", "matiere": "Littérature", "classe": None},
    {"fichier": "PROGRAMMES D'ETUDE MINESEC/SYSTEME FRANCOPHONE/ENSEIGNEMENT GENERAL/2ND CYCLE/PROGRAMME_SBEP_2nd.pdf", "matiere": "SBEP", "classe": "Seconde"},
    {"fichier": "PROGRAMMES D'ETUDE MINESEC/SYSTEME FRANCOPHONE/ENSEIGNEMENT  TECHNIQUE/1ER CYCLE/Programme_officiel_EPS.pdf", "matiere": "EPS", "classe": None},
    {"fichier": "PROGRAMMES D'ETUDE MINESEC/SYSTEME FRANCOPHONE/ENSEIGNEMENT  TECHNIQUE/1ER CYCLE/PROGRAMME_DE_TECHNOLOGIE.pdf", "matiere": "Technologie", "classe": None},
    {"fichier": "PROGRAMMES D'ETUDE MINESEC/SYSTEME FRANCOPHONE/ENSEIGNEMENT  TECHNIQUE/1ER CYCLE/PROGRAMME_DE_DESSIN_TECHNIQUE.pdf", "matiere": "Dessin Technique", "classe": None},
    
    # --- INFORMATIQUE (classes/filières supplémentaires) ---
    {"fichier": "PROGRAMMES D'ETUDE MINESEC/SYSTEME FRANCOPHONE/ENSEIGNEMENT GENERAL/2ND CYCLE/programme_INFO_seconde A.pdf", "matiere": "Informatique", "classe": "Seconde A"},
    {"fichier": "PROGRAMMES D'ETUDE MINESEC/SYSTEME FRANCOPHONE/ENSEIGNEMENT GENERAL/2ND CYCLE/programme_INFO_secondeC.pdf", "matiere": "Informatique", "classe": "Seconde C"},
    {"fichier": "PROGRAMMES D'ETUDE MINESEC/SYSTEME FRANCOPHONE/ENSEIGNEMENT GENERAL/2ND CYCLE/programme_INFO_Terminales_A_06_08_2020.pdf", "matiere": "Informatique", "classe": "Terminale A"},
    {"fichier": "PROGRAMMES D'ETUDE MINESEC/SYSTEME FRANCOPHONE/ENSEIGNEMENT GENERAL/2ND CYCLE/programme_INFOS_T CDE_06_08_2020.pdf", "matiere": "Informatique", "classe": "Terminale CDE"},
    {"fichier": "PROGRAMMES D'ETUDE MINESEC/SYSTEME FRANCOPHONE/ENSEIGNEMENT GENERAL/2ND CYCLE/programme_INFO_T TI_06_08_2020.pdf", "matiere": "Informatique", "classe": "Terminale TI"},
    {"fichier": "PROGRAMMES D'ETUDE MINESEC/SYSTEME FRANCOPHONE/ENSEIGNEMENT GENERAL/2ND CYCLE/programme_T ESTP.pdf", "matiere": "Informatique", "classe": "Terminale ESTP"},

        # --- ANGLOPHONE : MATHS / SCIENCES ---
    {"fichier": "PROGRAMMES D'ETUDE MINESEC/ANGLOPHONE SYSTEM/GENERAL EDUCATION/1ST CYCLE/Maths_syllabus_1_2.pdf", "matiere": "Mathematics", "classe": None},
    {"fichier": "PROGRAMMES D'ETUDE MINESEC/ANGLOPHONE SYSTEM/GENERAL EDUCATION/1ST CYCLE/Math_syllabus_F3.pdf", "matiere": "Mathematics", "classe": None},
    {"fichier": "PROGRAMMES D'ETUDE MINESEC/ANGLOPHONE SYSTEM/GENERAL EDUCATION/1ST CYCLE/FORM_ONE _AND _FORM _TWO SYLLABUS_PHYSICS.pdf", "matiere": "Physics", "classe": None},
    {"fichier": "PROGRAMMES D'ETUDE MINESEC/ANGLOPHONE SYSTEM/GENERAL EDUCATION/1ST CYCLE/PHYSICS_teaching _SYLLABUS_F345.pdf", "matiere": "Physics", "classe": None},
    {"fichier": "PROGRAMMES D'ETUDE MINESEC/ANGLOPHONE SYSTEM/GENERAL EDUCATION/1ST CYCLE/Syllabus_anglophone_chemistry_F3.pdf", "matiere": "Chemistry", "classe": None},
    {"fichier": "PROGRAMMES D'ETUDE MINESEC/ANGLOPHONE SYSTEM/GENERAL EDUCATION/1ST CYCLE/SYLLABUS_BIOLOGY_F_345.pdf", "matiere": "Biology", "classe": None},
    {"fichier": "PROGRAMMES D'ETUDE MINESEC/ANGLOPHONE SYSTEM/GENERAL EDUCATION/1ST CYCLE/SYLLABUS_GEOLOGY_ F34.pdf", "matiere": "Geology", "classe": None},
    {"fichier": "PROGRAMMES D'ETUDE MINESEC/ANGLOPHONE SYSTEM/GENERAL EDUCATION/1ST CYCLE/SYLLABUS_HBIO_F_45.pdf", "matiere": "Human Biology", "classe": None},

    # --- ANGLOPHONE : HUMANITIES ---
    {"fichier": "PROGRAMMES D'ETUDE MINESEC/ANGLOPHONE SYSTEM/GENERAL EDUCATION/1ST CYCLE/HIST- FORMS 3-5_ GENERAL EDUCATION (COMPLETE).pdf", "matiere": "History", "classe": None},
    {"fichier": "PROGRAMMES D'ETUDE MINESEC/ANGLOPHONE SYSTEM/GENERAL EDUCATION/1ST CYCLE/GEOG- FORMS 3-5_ GENERAL EDUCATION (COMPLETE).pdf", "matiere": "Geography", "classe": None},
    {"fichier": "PROGRAMMES D'ETUDE MINESEC/ANGLOPHONE SYSTEM/GENERAL EDUCATION/1ST CYCLE/CIT. EDUC.- FORMS 3-5_ GENERAL EDUCATION (COMPLETE).pdf", "matiere": "Citizenship Education", "classe": None},
    {"fichier": "PROGRAMMES D'ETUDE MINESEC/ANGLOPHONE SYSTEM/GENERAL EDUCATION/1ST CYCLE/ECONS- FORMS 3-5_ GENERAL EDUCATION (COMPLETE).pdf", "matiere": "Economics", "classe": None},

    # --- ANGLOPHONE : LANGUES ---
    {"fichier": "PROGRAMMES D'ETUDE MINESEC/ANGLOPHONE SYSTEM/GENERAL EDUCATION/1ST CYCLE/FRENCH_AS SECOND_LANGUAGE_Form345.pdf", "matiere": "French as Second Language", "classe": None},
    {"fichier": "PROGRAMMES D'ETUDE MINESEC/ANGLOPHONE SYSTEM/GENERAL EDUCATION/2ND CYCLE/Syllabus French Upper Sixth Général Education.pdf", "matiere": "French as Second Language", "classe": "Upper Sixth"},

    # --- ANGLOPHONE : INFORMATIQUE (2 fichiers = 2 tranches de niveaux, pas des doublons) ---
    {"fichier": "PROGRAMMES D'ETUDE MINESEC/ANGLOPHONE SYSTEM/GENERAL EDUCATION/1ST CYCLE/Computer_Science _Sylabus_Form1_2.pdf", "matiere": "Computer Science", "classe": None},
    {"fichier": "PROGRAMMES D'ETUDE MINESEC/ANGLOPHONE SYSTEM/GENERAL EDUCATION/1ST CYCLE/Computer_Science_Syllabus F3_4_5.pdf", "matiere": "Computer Science", "classe": None},
    {"fichier": "PROGRAMMES D'ETUDE MINESEC/ANGLOPHONE SYSTEM/GENERAL EDUCATION/2ND CYCLE/CS Syllabus Working Draft 25-082020.pdf", "matiere": "Computer Science", "classe": None},
    {"fichier": "PROGRAMMES D'ETUDE MINESEC/ANGLOPHONE SYSTEM/GENERAL EDUCATION/2ND CYCLE/ICT Syllabus Working Draft 25-082020.pdf", "matiere": "ICT", "classe": None},

# NOUVEAU : ajouter une ligne ici pour chaque nouveau PDF de programme
]


def nettoyer_cellule(texte):
    if not texte:
        return None
    return texte.replace('\uf0b7', '•').replace('\uf0d8', '-').strip()


def nettoyer_titre_lecon(titre):
    if not titre:
        return titre
    titre = re.sub(r'^[•\s]+', '', titre)
    return titre.split('•')[0].strip()


def nettoyer_titre_module(titre):
    titre = re.split(r'\bDUREE\s*:|\bDURÉE\s*:|\bCRÉDIT\s*:|\bCREDIT\s*:|\bCOURS\s*:|\bNUMBER OF\b', titre, flags=re.IGNORECASE)[0]
    return titre.strip(" .:-")


def titre_module_est_un_faux_positif(titre):
    """
    Rejette les 'titres de module' qui sont en fait des en-têtes de tableau
    mal filtrés (ex: 'CONTEXTUALISATION COMPETENCIES TO BE ATTAINED
    RESOURCES', 'Category of actions Core Knowledge...', ou des lignes de
    durée du style 'Form 3 34 Hours/42 Periods...').
    """
    if not titre:
        return True
    t = titre.upper()
    mots_suspects = ['CONTEXTUALISATION', 'RESSOURCES', 'RESOURCES', 'CORE KNOWLEDGE',
                      'CATEGORY OF ACTIONS', 'HOURS/', 'PERIODS']
    if any(mot in t for mot in mots_suspects):
        return True
    # Rejette aussi les titres à prédominance numérique (ex: "Form 4 48 23 19")
    chiffres = sum(c.isdigit() for c in titre)
    if len(titre) > 0 and chiffres / len(titre) > 0.25:
        return True
    return False


def detecter_module_sur_page(texte_page):
    m = re.search(r'TITRE DU MODULE\s*:\s*(.+)', texte_page, re.IGNORECASE)
    if m:
        return nettoyer_titre_module(m.group(1))
    m1b = re.search(r'TITLE OF (?:THE )?MODULE\s*:\s*(.+)', texte_page, re.IGNORECASE)
    if m1b:
        return nettoyer_titre_module(m1b.group(1))
    m2 = re.search(r'\bMODULE\s*[\dIVXLCM]+\s*:\s*(.+)', texte_page, re.IGNORECASE)
    if m2:
        return nettoyer_titre_module(m2.group(1))
    # [\dIVXLCM]+ au lieu de \d+ — certains documents (SVT) utilisent
    # des chiffres romains ("MODULE I :", "MODULE II :") plutôt qu'arabes.
    m3 = re.search(r'MODULE\s*N?°?\s*[\dIVXLCM]+\s*\n(.+)', texte_page, re.IGNORECASE)
    if m3:
        titre = nettoyer_titre_module(m3.group(1))
        if titre and len(titre) > 3:
            return titre
    return None


def detecter_classe_sur_page(texte_page, classe_actuelle):
    m = re.search(r'PRESENTATION DES MODULES DE LA CLASSE DE\s+([A-Za-zème\d]+)', texte_page, re.IGNORECASE)
    if m and not texte_page[m.end():m.end() + 3].strip().startswith('.'):
        return m.group(1)
    # NOUVEAU : re.IGNORECASE ajouté — plusieurs documents (Histoire, Géo,
    # ECM, Maths 4e/3e) utilisent "CLASSE DE X" tout en majuscules, ce que
    # la version précédente (sensible à la casse) ratait systématiquement.
    m2 = re.search(r'^Classe de\s+(\w+)', texte_page, re.MULTILINE | re.IGNORECASE)
    if m2:
        return m2.group(1)
    # NOUVEAU : 3e format rencontré (Allemand) — "CLASSE : 4ème" avec deux
    # points, sans "de".
    m3 = re.search(r'^CLASSE\s*:\s*(\w+)', texte_page, re.MULTILINE | re.IGNORECASE)
    if m3:
        return m3.group(1)
    # NOUVEAU : format anglophone — "TABLE 10: ... FORM 3" dans le titre du tableau.
    m4 = re.search(r'^TABLE\s*\d+.*?\bFORM\s*(\d+)', texte_page, re.MULTILINE | re.IGNORECASE)
    if m4:
        return f"Form {m4.group(1)}"
    # NOUVEAU : format "FORM THREE CLASS" (en toutes lettres, pas en chiffres)
    m5 = re.search(r'\bFORM\s+(ONE|TWO|THREE|FOUR|FIVE|SIX)\s+CLASS', texte_page, re.IGNORECASE)
    if m5:
        return f"Form {m5.group(1).capitalize()}"
    return classe_actuelle

def est_ligne_entete(row):
    for cell in row:
        if not cell:
            continue
        c = cell.lower().replace('\n', ' ')
        if (('famille de' in c and 'situation' in c) or ('family of' in c and 'situation' in c)
                or ('catégor' in c and 'action' in c and len(cell) < 40)
                or ('categor' in c and 'action' in c and len(cell) < 40)):
            return True
    return False


def table_est_detaillee(table):
    # NOUVEAU : accepte aussi les en-têtes anglais (family/situation/category/action)
    for row in table[:3]:
        t = ' '.join((c or '').lower().replace('\n', ' ') for c in row)
        if (('famille' in t and 'situation' in t and 'catégor' in t and 'action' in t)
                or ('family' in t and 'situation' in t and 'categor' in t and 'action' in t)):
            return True
    return False


def extraire_lecons(fichier_pdf, matiere, classe_defaut=None):
    """NOUVEAU : fichier_pdf est un objet fichier en mémoire (BytesIO), pas un chemin disque."""
    chunks = []
    etat = {"module": None, "competences_module": None, "prerequis": None}
    classe_actuelle = classe_defaut

    with pdfplumber.open(fichier_pdf) as pdf:
        for page in pdf.pages:
            texte_page = page.extract_text() or ""

            classe_actuelle = detecter_classe_sur_page(texte_page, classe_actuelle)

            nouveau_module = detecter_module_sur_page(texte_page)
            if nouveau_module and not titre_module_est_un_faux_positif(nouveau_module):
                etat["module"] = nouveau_module

            table = page.extract_table()
            if not table or not table_est_detaillee(table):
                continue

            for row in table:
                row = [nettoyer_cellule(c) for c in row]
                if len(row) < 5:
                    continue
                if est_ligne_entete(row):
                    continue

                col_competences, col_lecon, col_objectifs, col_prerequis = row[1], row[2], row[3], row[4]

                if col_competences:
                    etat["competences_module"] = col_competences.replace('\n', ' ')
                if col_prerequis:
                    etat["prerequis"] = col_prerequis.replace('\n', ' ')

                if col_lecon and col_objectifs and len(col_objectifs) > 10:
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
    if not os.path.exists(ZIP_PATH):
        logger.error(f"Zip introuvable : {ZIP_PATH}. Dépose-le à cet emplacement exact.")
        return

    total = 0
    with zipfile.ZipFile(ZIP_PATH) as archive:
        noms_disponibles = set(archive.namelist())

        for source in SOURCES:
            chemin_dans_zip = source["fichier"]
            if chemin_dans_zip not in noms_disponibles:
                logger.warning(f"Fichier introuvable dans le zip, ignoré : {chemin_dans_zip}")
                continue

            logger.info(f"Extraction de {chemin_dans_zip}...")
            with archive.open(chemin_dans_zip) as f:
                contenu_pdf = io.BytesIO(f.read())

            chunks = extraire_lecons(contenu_pdf, source["matiere"], source.get("classe"))
            logger.info(f"  -> {len(chunks)} leçon(s) détectée(s)")

            if not chunks:
                logger.warning(f"  -> AUCUNE leçon détectée pour {source['matiere']}. Format probablement différent, à inspecter.")
                continue

            classes_concernees = set(c["classe"] for c in chunks if c["classe"])
            if not classes_concernees:
                logger.warning(f"  -> Aucune classe détectée pour {source['matiere']}.")
            for classe in classes_concernees:
                supabase.table("syllabus_chunks").delete().eq("matiere", source["matiere"]).eq("classe", classe).execute()

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
                total += 1

            logger.info(f"  -> Indexé : {len(chunks)} leçons pour {source['matiere']}")

    logger.info(f"Indexation terminée : {total} leçons au total dans Supabase.")


if __name__ == "__main__":
    indexer_tout()