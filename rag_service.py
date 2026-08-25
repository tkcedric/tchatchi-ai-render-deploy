"""
rag_service.py

Contient la fonction appelée EN DIRECT pendant la conversation (contrairement
à index_syllabus.py qui tourne à part, une fois). Quand l'enseignant choisit
"🤖 Recherche Automatique (RAG)", cette fonction cherche les modules de
programme les plus pertinents pour classe+matière+leçon demandées, et
renvoie un texte de contexte à injecter dans le prompt de génération.
"""

import logging
from openai import OpenAI
from config import OPENAI_API_KEY
from database import supabase  # on réutilise le client Supabase déjà initialisé

logger = logging.getLogger(__name__)
openai_client = OpenAI(api_key=OPENAI_API_KEY)

# En dessous de ce score de similarité (entre 0 et 1), on considère qu'aucun
# résultat n'est assez pertinent, et on bascule sur le mode manuel plutôt que
# de risquer d'injecter du contenu hors-sujet dans le prompt.
SEUIL_PERTINENCE = 0.5


def rechercher_syllabus(classe, matiere, module, lecon):
    """
    Cherche dans Supabase les modules de programme les plus proches
    sémantiquement de la leçon demandée.

    Retourne soit :
    - un texte de contexte (concaténation des meilleurs résultats), si un
      résultat suffisamment pertinent a été trouvé
    - None si rien de pertinent n'a été trouvé (le code appelant doit alors
      basculer sur la saisie manuelle)
    """
    requete = f"{classe} {matiere} {module} {lecon}"

    try:
        embedding_requete = openai_client.embeddings.create(
            model="text-embedding-3-small",
            input=requete
        ).data[0].embedding
    except Exception as e:
        logger.error(f"Erreur lors de la génération de l'embedding RAG : {e}")
        return None

    try:
        resultat = supabase.rpc("match_syllabus", {
            "query_embedding": embedding_requete,
            "match_count": 3,
            "filter_matiere": matiere,
            "filter_classe": classe
        }).execute()
    except Exception as e:
        logger.error(f"Erreur lors de la recherche RAG dans Supabase : {e}")
        return None

    resultats = resultat.data or []

    # Si aucun résultat pour cette classe exacte (ex: "Terminale D" alors que
    # le programme indexé dit juste "Terminale"), on retente sans filtre de
    # classe, uniquement filtré par matière.
    if not resultats:
        try:
            resultat = supabase.rpc("match_syllabus", {
                "query_embedding": embedding_requete,
                "match_count": 3,
                "filter_matiere": matiere,
                "filter_classe": None
            }).execute()
            resultats = resultat.data or []
        except Exception as e:
            logger.error(f"Erreur lors du second essai RAG (sans filtre classe) : {e}")
            return None

    if not resultats:
        logger.info(f"RAG : aucun résultat trouvé pour '{requete}'")
        return None

    meilleur_score = resultats[0]["similarity"]
    if meilleur_score < SEUIL_PERTINENCE:
        logger.info(f"RAG : meilleur score {meilleur_score:.2f} sous le seuil ({SEUIL_PERTINENCE}), abandon.")
        return None

        # On assemble les résultats pertinents en un seul texte de contexte
    morceaux = []
    for r in resultats:
        if r["similarity"] >= SEUIL_PERTINENCE:
            morceaux.append(
                f"[Module : {r['module_titre']} | Leçon : {r['lecon_titre']}]\n"
                f"Objectifs : {r['objectifs']}\n"
                f"Prérequis : {r['prerequis'] or 'Non spécifié'}"
            )

    logger.info(f"RAG : {len(morceaux)} module(s) injecté(s), meilleur score = {meilleur_score:.2f}")
    return "\n\n---\n\n".join(morceaux)