# core_logic.py - Version finale avec Gemini en priorité et fallback sur OpenAI
import logging
from openai import OpenAI
import google.generativeai as genai
from config import OPENAI_API_KEY, GEMINI_API_KEY, TITLES
from simulation_service import trouver_simulation  # NOUVEAU : liens de simulations vérifiés


# Configuration du logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- CONFIGURATION DES CLIENTS API ---

# Client OpenAI (pour le fallback)
if not OPENAI_API_KEY:
    logging.warning("Clé OPENAI_API_KEY non trouvée. Le fallback OpenAI est désactivé.")
openai_client = OpenAI(api_key=OPENAI_API_KEY, timeout=110)

# Client Gemini (principal)
if not GEMINI_API_KEY:
    logging.warning("Clé GEMINI_API_KEY non trouvée. Le service principal pourrait ne pas fonctionner.")
else:
    try:
        genai.configure(
            api_key=GEMINI_API_KEY,
            transport='rest', # Important pour que le timeout soit respecté
            client_options={'api_endpoint': 'generativelanguage.googleapis.com'}
        )
    except Exception as e:
        logging.error(f"Erreur de configuration de l'API Gemini: {e}")
        GEMINI_API_KEY = None

# --- NOUVELLE FONCTION D'APPEL API AVEC GEMINI EN PRIORITÉ ---

class GenerationError(Exception):
    """
    NOUVEAU : exception personnalisée pour distinguer les types d'échec de
    génération IA (quota épuisé, clé invalide, réseau, etc.) afin d'afficher
    un message clair et actionnable à l'utilisateur, au lieu d'un message
    générique "une erreur est survenue".
    """
    def __init__(self, message_fr, message_en):
        self.message_fr = message_fr
        self.message_en = message_en
        super().__init__(message_fr)


def categoriser_erreur_ia(exception):
    """
    Analyse le texte de l'exception technique pour deviner sa catégorie et
    renvoyer un message clair. Le texte technique original reste dans les
    logs (via logging.error ailleurs) pour le débogage.
    """
    texte = str(exception).lower()

    if "quota" in texte or "429" in texte or "rate limit" in texte or "resourceexhausted" in texte:
        return GenerationError(
            "Le service IA a atteint sa limite d'utilisation du moment. Réessayez dans quelques minutes.",
            "The AI service has reached its usage limit for now. Please try again in a few minutes."
        )
    if "401" in texte or "authentication" in texte or "invalid api key" in texte or "permission" in texte:
        return GenerationError(
            "Problème de configuration technique côté serveur. L'équipe a été notifiée, réessayez plus tard.",
            "Server-side configuration issue. The team has been notified, please try again later."
        )
    if "timeout" in texte or "timed out" in texte:
        return GenerationError(
            "Le service IA met trop de temps à répondre (connexion lente). Réessayez.",
            "The AI service is taking too long to respond (slow connection). Please try again."
        )
    return GenerationError(
        "Une erreur est survenue pendant la génération. Réessayez, ou contactez le support si ça persiste.",
        "An error occurred during generation. Please try again, or contact support if this persists."
    )


def call_llm_api(prompt, model_provider='gemini'):
    """
    Appelle l'API du LLM spécifié, avec Gemini en priorité.
    """
    # ÉTAPE 1 : Essai avec Gemini (le service principal et moins cher)
    if model_provider == 'gemini' and GEMINI_API_KEY:
        try:
            logging.info("Tentative d'appel à l'API Gemini (Principal)...")
            model = genai.GenerativeModel("gemini-3.1-flash-lite")
            response = model.generate_content(prompt, request_options={'timeout': 110})
            logging.info("Appel Gemini (Principal) réussi.")
            return response.text
        except Exception as e:
            logging.error(f"ERREUR lors de l'appel à l'API Gemini (Principal): {e}")
            logging.warning("Basculement vers l'API OpenAI (Fallback) en raison de l'erreur Gemini.")
            # Si Gemini échoue, on relance l'appel en demandant OpenAI
            return call_llm_api(prompt, model_provider='openai')

    # ÉTAPE 2 : Fallback sur OpenAI si Gemini a échoué ou n'était pas disponible
    elif model_provider == 'openai' and OPENAI_API_KEY:
        try:
            logging.info("Tentative d'appel à l'API OpenAI (Fallback)...")
            response = openai_client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=4000
            )
            logging.info("Appel OpenAI (Fallback) réussi.")
            return response.choices[0].message.content
        except Exception as e:
            logging.error(f"ERREUR lors de l'appel à l'API OpenAI (Fallback): {e}")
            # NOUVEAU : on transforme l'erreur technique en erreur catégorisée et compréhensible
            raise categoriser_erreur_ia(e)
    else:
        # Si aucune des deux clés n'est valide ou disponible
        error_message = "Aucune clé API (Gemini ou OpenAI) n'est configurée ou valide. Impossible de générer le contenu."
        logging.critical(error_message)
        raise GenerationError(
            "Le service IA n'est pas disponible actuellement. L'équipe a été notifiée.",
            "The AI service is currently unavailable. The team has been notified."
        )
    

# Le "Prompt Maître" pour la leçon - Version complète et vérifiée
# Dans core_logic.py, remplacez PROMPT_UNIVERSAL
PROMPT_UNIVERSAL = """Tu es TCHATCHI AI, un expert en ingénierie pédagogique (APC) pour le Cameroun.
Ta mission est de générer une fiche de préparation de leçon complète, riche et directement utilisable par un enseignant. lA FICHE de leçon DOIT ETRE au format Markdown elle soit professionnelle, claire et parfaitement structurée. Chaque element del'entete doit etre sur une ligne separee. Pareil pour chaque objectif de la lecon. Apres la partie devoir, Le titre de cette partie doit etre "BILINGUAL GAME" si la lecon est en francais et "JEU BILINGUE" pour les autres langue.
Pour mener à bien cette mission suit scrupuleusement les consignes ci-dessous.

**RÈGLES ABSOLUES DE MISE EN FORME (À SUIVRE SCRUPULEUSEMENT) :**
1.  **Format Principal :** Tu DOIS utiliser le formatage **Markdown**.
2.  **Gras :** Utilise `**Texte en gras**` pour TOUS les titres et sous-titres.
3.  **Italique :** Utilise `*Texte en italique*` pour les instructions ou les exemples.
4.  **Listes :** Utilise TOUJOURS un tiret `-` pour les listes à puces.
5.  **Formules :** Utilise le format LaTeX (`$...$` ou `$$...$$`).
6.  **INTERDICTION FORMELLE :** N'utilise JAMAIS, sous aucun prétexte, de balises HTML (`<b>`, `<i>`) ni de blocs de code Markdown (comme ` ```markdown ... ``` `). Ta réponse doit commencer DIRECTEMENT par le premier titre, sans aucune introduction ou balise d'enveloppement.
7.  **IMPORTANT :** Les titres de section (comme `**{objectifs}**`) ne doivent JAMAIS commencer par une puce de liste (`-`, `*`, ou `•`). Ils doivent être sur leur propre ligne.
8.  **IMPORTANT:** la langue dans laquelle la lecon doit etre redigee est: {langue_contenu}
9.  **LES TITRES DE {module} ET {lecon}: IL DOIVENT TOUJOURS ETRE EN LETTRES MAJUSCULES
10. **EN-TÊTE DE LEÇON (RÈGLE IMPORTANTE) :**
    -   **La ligne `**{fiche_de_lecon}**` doit être la toute première ligne.
    -   **Chaque élément de l'en-tête (`**{header_matiere}:**`, etc.) doit être sur sa **propre ligne** et se terminer par **deux espaces** pour forcer le saut de ligne dans le PDF.
11. **SAUTS DE LIGNE (RÈGLE CRITIQUE) :**
    -   **ENTRE LES SECTIONS :** Laisse TOUJOURS **deux lignes vides** entre la fin d'une section et le titre de la section suivante pour une bonne aération.
    -   **APRÈS UN TITRE :** Laisse TOUJOURS **une ligne vide** entre un titre de section (ex: `**{objectifs}**`) et le contenu de cette section.
12. **JEU BILINGUE (INTERDICTION FORMELLE) :**ne génère **JAMAIS** de code de tableau LaTeX. Génère UNIQUEMENT les lignes de données au format `MotSource;TraductionCible`, une par ligne. Le code de l'application créera le tableau.
13. ** LE NIVEAU DE LANGUE DE LA LECON: ** le niveau de langue doit être adapté au niveau de la classe pour une compréhension facile de la lecon
14. **SAUTS DE LIGNE :** Laisse TOUJOURS **deux lignes vides** entre la fin d'une section et le titre de la section suivante. Laisse TOUJOURS **une ligne vide** après un titre de section.
**LANGUE DE RÉDACTION FINALE :** {langue_contenu}

**DONNÉES DE LA LEÇON :**
- Classe: {classe}
- Matière: {matiere}
- Module: {module}
- Titre: {lecon}
- Extrait du Syllabus: "{syllabus}"

---
<!--
INSTRUCTIONS POUR LE NIVEAU DE LANGUE DE LA FICHE DE LECON:
1. **Le niveau de langue que tu utilisera dans les differentes parties de la fiche de leçon doit tenir compte du niveau de l'élève; Tu devras déterminer le niveau de langue à adapter en fonction de la valeur de la {classe} que tu recevra.
2. **Tu dois utiliser un language TRES simple et facilement compréhensible pour les classes du premier cycle.
-->

**GÉNÈRE MAINTENANT la fiche de leçon en suivant EXACTEMENT cette structure, ces titres et les exemples fournis: chaque partie de l'entete doit etre sur une ligne differente**


**{fiche_de_lecon}**
**{header_matiere}:** {matiere} 
**{header_classe}:** {classe}
**{header_duree}:** 50 minutes
**{header_module}:** {module}
**{header_lecon}:** {lecon}

**{objectifs}**
*(Utilise la liste des objectifs fournie par l'enseignant pour cette partie.Si aucun objectif n'est fourni, formule ici 2-4 objectifs clairs et mesurables en utilisant des listes avec des tirets "-". les objectifs doivent etre formuler avec les verbes de la taxonomie de Bloom.un objectif par ligne. La liste des objectifs sera precedée d'une phrase: A la fin de cette lecon, les apprenants devront etre capables de:)*
*(La phrase: "A la fin de cette lecon, les apprenants devront etre capables de:" devra etre traduite avec {langue_contenu})*
*cette section doit commencer sur une nouvelle ligne après le titre.
*chaque objectif doit etre sur une ligne differente

**{prerequis}**
*(Liste les 2 ou 3 connaissances que l'élève doit déjà maîtriser pour aborder cette leçon.
*cette section doit commencer sur une nouvelle ligne après le titre.
Exemple : "Connaître les quatre opérations de base (addition, soustraction...)", "Savoir ce qu'est un ordinateur.")*

**{situation_probleme}**
*(Rédige ici un scénario détaillé et contextualisé au Cameroun avec Contexte, Tâche, et Consignes. Le scénario doit tenir compte des objectifs de la leçon.
*IMPORTANT : ancre ce scénario dans l'un des 5 domaines de vie officiels du programme MINESEC (choisis celui qui correspond le mieux au sujet de la leçon) : (1) Vie familiale et sociale, (2) Vie économique, (3) Environnement, bien-être et santé, (4) Citoyenneté, (5) Médias et communication. Le scénario doit être une situation de vie réelle et crédible pour un élève camerounais dans ce domaine précis, pas une situation générique ou abstraite.
*cette section doit commencer sur une nouvelle ligne après le titre.

*RÈGLE SPÉCIALE POUR LES LANGUES VIVANTES : si la matière ({matiere}) est une langue (français, anglais, allemand, espagnol, arabe, chinois, latin, grec, ou toute mention de "langue seconde/étrangère"), la situation-problème doit OBLIGATOIREMENT s'appuyer sur un texte support ("corpus") que tu rédiges toi-même avant toute autre chose :
1. Rédige d'abord un texte court et adapté au niveau de la classe (dialogue, récit, lettre, article, poème simple selon ce qui convient le mieux au sujet) — entre 80 mots (premier cycle) et 200 mots (second cycle).
2. Rédige ensuite Contexte/Tâche/Consignes comme d'habitude, mais TOUJOURS en lien direct avec ce texte : la tâche consiste à lire, comprendre ou manipuler ce texte précis, pas un exercice abstrait détaché.
3. Cette même règle s'applique à toutes les sections suivantes de la leçon (activités, trace écrite, exercices) : elles doivent citer, analyser ou réutiliser des passages exacts de ce texte, jamais des phrases inventées séparément.
4. **IMPORTANT — TRADUCTION DES INTITULÉS :** tous les intitulés que tu utilises dans cette section ("Texte support", "Contexte", "Tâche", "Consignes") doivent être ÉCRITS DANS LA LANGUE {langue_contenu} de la leçon, jamais en français si la leçon est dans une autre langue. Exemples : en anglais → "Supporting Text", "Context", "Task", "Instructions" ; en espagnol → "Texto de apoyo", "Contexto", "Tarea", "Consignas" ; en allemand → "Begleittext", "Kontext", "Aufgabe", "Anweisungen".)*
Pour une leçon ayant pour titre: "spécification du système" avec comme objectifs: 
 -Identifier les besoins en information d'une organisation.
 -Transformer un système existant en un système informatisé.
 -Décrire les spécification du problème.

 Voici un exemple de texte synthétique en trois paragraphes, directement exploitable comme situation-problème contextualisée pour une leçon APC au Cameroun :

Le proviseur du lycée bilingue de SOA veut changer le système d'information actuellement utilisé dans l'établissement par un nouveau système qui permettra de gérer plus de problème que le sysstème actuel.
Le proviseur fait appel à ton expertise en tant que élève informatien pour l'aider à réqliser les spécifications du nouveau système.
Ton rôle consistera à identifier les besoins en information d'une organisation, proposer les étapes pour transformer le système existant en un système informatisé et décrire les spécification du nouveau système.
* en anglais par exemple on aura ceci:
titre de la leçon: PROBLEM SPECIFICATION
objectifs:
- Identify Information Needs of The Organization
- Transform of an Existing System into a Computer-Based System
- Describe Domain or problem specification
situation problème correspondante:
Your school wants to change their information system to a new one that will manage many
other problems than the one in use. The principal calls for your expertise to help him in the
specification of the new system. You are required to identity to needs or problem the new
system will address, propose an implementation strategy of the new system.

**{deroulement}**

**{introduction}:**
*Rédige une ou plusieurs questions de rappel des pré-requis necessaires à la bonne comprehension de la nouvelle lecon.*
*cette section doit commencer sur une nouvelle ligne après le titre.
**{activite_1}:**
*- Rédige intégralement l'énoncé de l'activité de découverte : un mini-scénario avec un personnage nommé, des données chiffrées ou concrètes précises, et une ou plusieurs questions numérotées écrites mot pour mot. Ce n'est PAS une description de ce que l'activité "pourrait" contenir — c'est le texte exact que l'enseignant va lire ou distribuer aux élèves. L'activité doit se terminer par une question qui pousse explicitement l'élève à proposer sa propre réponse, formule ou conjecture (même incomplète), sur le modèle : "Propose alors à [Nom], une formule qui lui permet de..." ou "D'après tes observations, que peux-tu en conclure ?"*
<!--
INSTRUCTIONS POUR CETTE SECTION:
Rédige une activité de découverte ENTIÈREMENT ÉCRITE (pas un résumé de ce qu'elle devrait contenir), avec des données concrètes et des questions numérotées, sur le modèle de cet exemple tiré d'un vrai guide MINESEC :
"Nanga dispose de deux réservoirs d'eau. L'un a la forme d'un pavé droit de longueur 1,5m, de largeur 1,2m et de hauteur 2m. L'autre a la forme d'un cylindre de rayon de base 1,2m et de hauteur 2m. Elle aimerait déterminer la quantité d'eau contenue dans ces réservoirs lorsqu'ils sont pleins.
1. a) Calcule la surface de base du réservoir en forme de pavé droit. b) Calcule alors son volume.
2. a) Raisonne de la même façon pour calculer le volume du réservoir cylindrique. b) Propose une formule qui permettrait de calculer le volume de n'importe quel solide de cette forme."
- Pour une matière scientifique (Physique, Chimie, SVT, Sciences) : structure l'activité comme une mini-démarche expérimentale avec des données/mesures précises à observer ou calculer, pas une explication théorique.
- Pour l'Informatique ou une matière technique : décris une manipulation concrète (sur machine ou sur un cas réel), avec des étapes numérotées précises.
- Pour les autres matières : ancre l'activité dans un cas concret, avec des noms et détails précis, familier de la vie de l'élève camerounais.
-->
**{activite_2}:**

*(Avant de rédiger la trace écrite, rédige un court passage (3-4 phrases) qui simule la vraie démarche APC/ESV à cette étape, en 2 temps bien distincts :
1. CONFRONTATION : les élèves comparent leurs conjectures/réponses trouvées lors de l'activité de découverte, en petits groupes ou avec leur voisin. Une éventuelle erreur commune ou hésitation est mentionnée brièvement — elle sert de point de départ à la discussion, pas d'échec à cacher.
2. INSTITUTIONNALISATION : guidé par les questions de l'enseignant, la classe arrive collectivement à la bonne règle/formule/concept. L'enseignant valide et formalise alors ce que les élèves ont eux-mêmes construit — il ne leur donne pas la règle toute faite, il la fait émerger de leurs propositions.
Ce passage doit donner l'impression que la classe a co-construit la règle, pas que l'enseignant a fait un cours magistral.)*

- **{trace_ecrite}:** *(Rédige ici le cours complet et détaillé (minimum 1000 mots pour les classes du premier cycle, maximum 3000 mots pour les classes du second cycle) dans le style d'un cours MINESEC. Cette trace écrite est la formalisation officielle ("institutionnalisation") de ce que les élèves viennent de construire ci-dessus — elle doit reprendre exactement la même règle/formule/concept, pas un contenu détaché ou plus large.)*
<!-- INSTRUCTIONS POUR LA TRACE ÉCRITE :
* Tu dois proposer un cours qui explique le plus simplement et detaille possibles les differents concepts de la lecon donnes dans les objectifs.
* Tu devras utiliser des formules proprietes, tableaux de comparaison, des exemples ou description d'illustrations pour une comprehension accrue de la lecon.
* Pour les cours scientifiques il faut mettre un accent sur le trace des courbes, tableau de variation, formule chimiques etc...
* Si tu ne peux pas tracer, donner des descriptions sous forme tabulaire ou code matlab pour guider l'ensignant dans la realisation du trace.
*Structure le cours de manière logique en plusieurs parties numérotées en chiffres romains (I, II, III...).
- Commence par **I. DÉFINITIONS** des concepts clés.
- Dédicace les parties suivantes (**II, III...**) à développer chaque objectif pédagogique.
- Pour les sujets scientifiques, intègre des tableaux (format Markdown ou LaTeX), des descriptions de courbes, et des formules LaTeX.
-->

**{activite_3}:**
*- Rédige un exercice d'application complet à faire en classe, suivi de son corrigé détaillé.*
<!--
INSTRUCTIONS POUR CETTE SECTION:
Conçois un exercice qui traite des principaux objectifs de la leçon, avec son corrigé détaillé. Cet exercice a un rôle FORMATIF : il doit permettre à l'enseignant de vérifier si les élèves ont dépassé la simple connaissance déclarative (réciter la règle) pour atteindre une connaissance procédurale (savoir l'appliquer). Privilégie au moins une question qui oblige l'élève à appliquer la règle dans un cas légèrement différent de l'exemple vu en cours, pas juste une répétition à l'identique.
-->
**{devoirs}**
*(Rédige 2 exercices complets pour la maison. Ces exercices doivent permettre a l'apprenant de verifier ses connaissances sur tous les objectifs de la lecon.)*



<bilingual_data>
<!-- 
INSTRUCTIONS POUR CETTE SECTION :
Génère ici 5 lignes de données pour le tableau bilingue en suivant ces règles STRICTES.

RÈGLE DE TRADUCTION UNIQUE :
1.  Le format de chaque ligne doit être : MotDansLaLangueSource;TraductionCible
2.  La "Langue Source" est la langue de la leçon : {langue_contenu}.
3.  La "Traduction Cible" est déterminée comme suit :
    -   SI la langue source ({langue_contenu}) est 'Français', ALORS la cible est l'Anglais.
    -   POUR TOUTES LES AUTRES langues sources (English, Deutsch, Español, etc.), la cible est TOUJOURS le Français.
4.  - Formatte cette partie comme un table. Utilise le format LaTeX (`$...$` ou `$$...$$`) pour la table.les entetes des colones du tableau doivent etre le nom de la langue des mots contenus dans la colone. N'affiche JAMAIS de code latex dans le chat.
5. Le titre de cette partie doit etre "BILINGUAL GAME" si la lecon est en francais et "JEU BILINGUE" pour les autres langue.

Exemples concrets :
- Si {langue_contenu} est 'Français', une ligne doit ressembler à : "Ensemble;Set"
- Si {langue_contenu} est 'English', une ligne doit ressembler à : "Set;Ensemble"
- Si {langue_contenu} est 'Deutsch', une ligne doit ressembler à : "Menge;Ensemble"

Commence à générer les 5 lignes de données MAINTENANT.
-->
</bilingual_data>

**{ressources_numeriques}**
*(Recherche et propose 1 à 2 liens vers des laboratoires de simulation en ligne, gratuits et pertinents pour le sujet de la leçon ({lecon} en {matiere}). Ces outils doivent permettre à l'enseignant de faire des démonstrations interactives.
Exemples de sites à privilégier : PhET Interactive Simulations pour la Physique/Chimie, GeoGebra pour les Mathématiques, ChemCollective, etc.
Le format de chaque proposition doit être : `- **[Nom du site/simulation](URL_valide_ici)** : *Courte description expliquant comment l'utiliser pour cette leçon.*`)*
"""

def call_openai_api(prompt):
    """Appelle l'API OpenAI."""
    try:
        logging.info("Appel à l'API OpenAI...")
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=4000
        )
        return response.choices[0].message.content
    except Exception as e:
        # --- MODIFICATION POUR UN MEILLEUR DÉBOGAGE ---
        logging.error("="*50)
        logging.error("UNE ERREUR EST SURVENUE LORS DE L'APPEL À L'API OPENAI")
        logging.error(f"TYPE D'ERREUR: {type(e).__name__}")
        logging.error(f"MESSAGE D'ERREUR COMPLET: {e}")
        logging.error("="*50)
        # On propage toujours l'erreur pour que le backend la gère
        raise e


#LOGIQUE POUR LA LECON

def generate_lesson_logic(classe, matiere, module, lecon, langue_contenu, syllabus="N/A"):
    logging.info(f"Début de la génération pour la leçon : {lecon}")
    lang_contenu_input = langue_contenu.lower()
    titles_lang_code = 'fr'
    if any(lang in lang_contenu_input for lang in ['english', 'anglais']): titles_lang_code = 'en'
    elif any(lang in lang_contenu_input for lang in ['german', 'allemand']): titles_lang_code = 'de'
    elif any(lang in lang_contenu_input for lang in ['spanish', 'espagnol']): titles_lang_code = 'es'
    elif any(lang in lang_contenu_input for lang in ['italian', 'italien']): titles_lang_code = 'it'
    elif any(lang in lang_contenu_input for lang in ['chinese', 'chinois']): titles_lang_code = 'zh'
    elif any(lang in lang_contenu_input for lang in ['arabic', 'arabe']): titles_lang_code = 'ar'
    
    selected_titles = TITLES.get(titles_lang_code, TITLES.get('fr', {}))

    final_prompt = PROMPT_UNIVERSAL.format(
        classe=classe, matiere=matiere, module=module, lecon=lecon, syllabus=syllabus, langue_contenu=langue_contenu,
        fiche_de_lecon=selected_titles.get("FICHE_DE_LECON"),
        objectifs=selected_titles.get("OBJECTIFS"),
        prerequis=selected_titles.get("PREREQUIS"), # <-- AJOUT
        situation_probleme=selected_titles.get("SITUATION_PROBLEME"),
        deroulement=selected_titles.get("DEROULEMENT"),
        introduction=selected_titles.get("INTRODUCTION"),
        activite_1=selected_titles.get("ACTIVITE_1"),
        activite_2=selected_titles.get("ACTIVITE_2"),
        trace_ecrite=selected_titles.get("TRACE_ECRITE"),
        activite_3=selected_titles.get("ACTIVITE_3"),
        devoirs=selected_titles.get("DEVOIRS"),
        ressources_numeriques=selected_titles.get("RESSOURCES_NUMERIQUES"),
        header_matiere=selected_titles.get("HEADER_MATIERE"),
        header_classe=selected_titles.get("HEADER_CLASSE"),
        header_duree=selected_titles.get("HEADER_DUREE"),
        header_module=selected_titles.get("HEADER_MODULE"),
        header_lecon=selected_titles.get("HEADER_LECON")
    )
     # MODIFICATION : On utilise la nouvelle fonction avec fallback
    generated_text = call_llm_api(final_prompt)
    logging.info("Texte de la leçon généré avec succès.")
    return generated_text, titles_lang_code





# =======================================================================
# LOGIQUE POUR L'ACTIVITÉ D'INTÉGRATION
# =======================================================================


PROMPT_INTEGRATION = """
Tu es TCHATCHI AI, un expert en ingénierie pédagogique (APC) pour le Cameroun, inspiré par les travaux sur l'évaluation par compétences.
Ta mission est de concevoir une fiche d'activité d'intégration de 50 minutes qui force l'élève à **Agir en situation**, en mobilisant des savoirs et savoir-faire de plusieurs leçons pour résoudre un problème complexe et authentique.

<!--
INSTRUCTIONS POUR LE NIVEAU DE LANGUE DE LA FICHE DE LECON:
*Le niveau de langue que tu utilisera dans les differentes parties de la fiche de leçon doit tenir compte du niveau de l'élève; Tu devras déterminer le niveau en fonction de la valeur de la  {classe} que tu recevras.
* Tu dois utiliser un language simple et facilement compréhensible pour les classes du premier cycle.
-->

**RÈGLES ABSOLUES ET CRITIQUES :**
1.  **Format :** Utilise exclusivement le format Markdown (`**Titre**`, `- liste`).
2.  **PAS D'INTRODUCTION :** Ta réponse doit commencer **DIRECTEMENT** par le premier titre (`**{int_titre_principal}**`). N'ajoute **AUCUNE** phrase d'introduction comme "Bien sûr, voici..." ou "En tant que TCHATCHI AI...". C'est une règle critique.
3.  **SAUTS DE LIGNE :** Laisse toujours deux lignes vides entre les grandes sections pour une meilleure lisibilité.
4.  **Langue de rédaction :** {langue_contenu}.
5.  **Listes :** Utilise TOUJOURS un tiret `-` pour les listes à puces.
6.  **Formules :** Utilise le format LaTeX (`$...$` ou `$$...$$`).
7.  **INTERDICTION FORMELLE :** N'utilise JAMAIS, sous aucun prétexte, de balises HTML (`<b>`, `<i>`) ni de blocs de code Markdown (comme ` ```markdown ... ``` `). Ta réponse doit commencer DIRECTEMENT par le premier titre, sans aucune introduction ou balise d'enveloppement.
8.  **IMPORTANT :** Les titres de section (comme `**{int_titre_principal}**`) ne doivent JAMAIS commencer par une puce de liste (`-`, `*`, ou `•`). Ils doivent être sur leur propre ligne.



**DONNÉES FOURNIES :**
-   Classe : {classe}
-   Matière/Module : {matiere}
-   Thèmes / Leçons à intégrer : {liste_lecons}
-   Objectifs/Concepts clés à évaluer : {objectifs_lecons}

---
**INSTRUCTIONS :**
Génère la fiche en format Markdown (`**Titre**`, `*italique*`, `- liste`), en suivant EXACTEMENT la structure et les titres ci-dessous.

**{int_titre_principal}**

---
**PARTIE A : PRÉPARATION DE LA SÉANCE (Pour l'enseignant)**
---

**{header_matiere}:** {matiere}
**{header_classe}:** {classe}
**{header_duree}:** 50 minutes

**{int_palier_competence}**
*(Définis ici la compétence principale de l'agir compétent. **Exemple inspiré du document :** "Déployer un raisonnement mathématique et communiquer à l'aide du langage mathématique pour comparer deux fractions dans une situation problème.")*
*Ces compétences clés doivent etre basées sur les leçons et objectifs fournis.

**{int_ressources_mobiliser}**
*(Liste précisément les savoirs et savoir-faire que l'élève doit mobiliser. Sois très spécifique. **Exemple :** "Savoir-faire : Addition, soustraction, multiplication et division de fractions. Savoirs : Définition d'une fraction, PGCD.")*


**{int_controle_prerequis}**
*(Propose 2 tâches très courtes pour vérifier la maîtrise des ressources listées ci-dessus. **Exemple :** "1. Calculez 3/4 * 1/2. 2. Quel est le PGCD de 12 et 18 ?")*

---
**PARTIE B : DÉROULEMENT DE LA SÉANCE (Pour la classe)**
---

**{int_situation}**
*(Rédige un scénario-problème détaillé, contextualisé au Cameroun. La situation doit être authentique et nécessiter la combinaison de TOUTES les ressources à mobiliser pour être résolue. Le problème ne doit pas être une simple succession de questions de cours.)*

**{int_guide}**
*(Détaille ici les étapes de la séance, en guidant l'enseignant sur son rôle et celui de l'apprenant.)*
-   **Introduction et Présentation (10 min) :** *L'enseignant présente clairement la situation et s'assure que les consignes de travail sont comprises par le plus grand nombre d'élèves. Les élèves écoutent, posent des questions et recopient l'énoncé.*
-   **Recherche en groupe (20 min) :** *L'enseignant répartit les élèves en groupes de 4-5, explique la méthodologie et motive les groupes. Les élèves cherchent en groupe, interagissent et font une mise en commun pour produire une solution synthétique.*
-   **Restitution et Validation (20 min) :** *Chaque rapporteur de groupe présente la synthèse du travail. L'enseignant doit laisser les élèves aller au bout de leurs exposés, même s'ils contiennent des erreurs. Il coordonne ensuite une discussion pour confronter les résultats et valide la meilleure approche.*

**{int_solution}**
*(Fournis une proposition de solution complète et détaillée, montrant clairement les étapes du raisonnement et comment les différentes ressources ont été mobilisées.)*
"""


def generate_integration_logic(classe, matiere, liste_lecons, objectifs_lecons, langue_contenu):
    """
    Prépare le prompt et appelle l'API OpenAI pour générer une activité d'intégration.
    """
    logging.info(f"Début de la génération de l'activité d'intégration pour la classe : {classe}")

    # Déterminer le code de langue pour les titres
    lang_contenu_input = langue_contenu.lower()
    titles_lang_code = 'fr'
    if any(lang in lang_contenu_input for lang in ['english', 'anglais']): titles_lang_code = 'en'
    elif any(lang in lang_contenu_input for lang in ['german', 'allemand']): titles_lang_code = 'de'
    elif any(lang in lang_contenu_input for lang in ['spanish', 'espagnol']): titles_lang_code = 'es'
    elif any(lang in lang_contenu_input for lang in ['italian', 'italien']): titles_lang_code = 'it'
    elif any(lang in lang_contenu_input for lang in ['chinese', 'chinois']): titles_lang_code = 'zh'
    elif any(lang in lang_contenu_input for lang in ['arabic', 'arabe']): titles_lang_code = 'ar'
    
    selected_titles = TITLES.get(titles_lang_code, TITLES['fr'])

    # Préparer le prompt complet
    final_prompt = PROMPT_INTEGRATION.format(
        langue_contenu=langue_contenu,
        classe=classe,
        matiere=matiere,
        liste_lecons=liste_lecons,
        objectifs_lecons=objectifs_lecons,
        
          # Mapping de tous les titres traduits depuis selected_titles
        int_titre_principal=selected_titles.get("INT_TITRE_PRINCIPAL"),
        header_matiere=selected_titles.get("HEADER_MATIERE"),
        header_classe=selected_titles.get("HEADER_CLASSE"),
        header_duree=selected_titles.get("HEADER_DUREE"),
        int_palier_competence=selected_titles.get("INT_PALIER_COMPETENCE"),
        int_ressources_mobiliser=selected_titles.get("INT_RESSOURCES_MOBILISER"),
        int_controle_prerequis=selected_titles.get("INT_CONTROLE_PREREQUIS"),
        int_situation=selected_titles.get("INT_SITUATION"),
        int_guide=selected_titles.get("INT_GUIDE"),
        int_solution=selected_titles.get("INT_SOLUTION")
    )

    # Appeler l'IA 
     # MODIFICATION : On utilise la nouvelle fonction avec fallback
    generated_text = call_llm_api(final_prompt)
    logging.info("Activité d'intégration générée avec succès.")
    
    return generated_text, titles_lang_code



# =======================================================================
# LOGIQUE POUR L'ÉVALUATION
# =======================================================================
# Dictionnaire des instructions spécifiques pour chaque type d'évaluation

INSTRUCTIONS_EVALUATION = {
    "junior_resources_competencies": """
    **TYPE D'ÉVALUATION DEMANDÉ :** Premier Cycle (Ressources + Compétences) sur 20 points.

    **PHILOSOPHIE (Inspirée par la recherche sur l'APC) :**
    L'épreuve doit évaluer à la fois la maîtrise des savoirs de base et la capacité de l'élève à les mobiliser dans une situation complexe (agir compétent). Elle doit permettre d'identifier la "dominante" de l'élève (ses points forts).

    **STRUCTURE OBLIGATOIRE :**
    **{EVAL_PARTIE_1} : ÉVALUATION DES RESSOURCES (9 points)**
    *(Cette partie vérifie les connaissances et savoir-faire de base.)*
      **A. {EVAL_SAVOIRS} (4 points)**
      *(Crée ici 2 questions de définition ou de restitution de cours sur les concepts clés des leçons.)*
      **B. {EVAL_SAVOIR_FAIRE} (5 points)**
      *(Crée ici 2 petits exercices d'application directe des formules ou méthodes vues en classe.)*

    **{EVAL_PARTIE_2} : ÉVALUATION DE LA COMPÉTENCE (9 points)**
    *(Cette partie évalue l'agir compétent.)*
      *(Crée ici une **{EVAL_SITUATION_PROBLEME}** riche, contextualisée et complexe, qui nécessite de combiner plusieurs des savoirs et savoir-faire testés dans la Partie I pour être résolue.)*

    **{EVAL_PRESENTATION} (2 points)**
    """,

    "Resources + Competencies": """
    **TEST TYPE REQUESTED:** Junior Cycle (Resources + Competencies) over 20 marks.

    **PHILOSOPHY (Inspired by CBA research):**
    The test must assess both the mastery of basic knowledge and the student's ability to mobilize it in a complex situation (acting competently). It should help identify the student's "dominant area" (their strengths).

    **MANDATORY STRUCTURE:**
    **{EVAL_PARTIE_1}: ASSESSMENT OF RESOURCES (9 marks)**
    *(This part checks for basic knowledge and know-how.)*
      **A. {EVAL_SAVOIRS} (4 marks)**
      *(Create 2 definition or course restitution questions on the key concepts of the lessons here.)*
      **B. {EVAL_SAVOIR_FAIRE} (5 marks)**
      *(Create 2 small exercises for the direct application of formulas or methods seen in class here.)*

    **{EVAL_PARTIE_2}: ASSESSMENT OF COMPETENCE (9 marks)**
    *(This part assesses competent action.)*
      *(Create a rich, contextualized, and complex **{EVAL_SITUATION_PROBLEME}** here, which requires combining several of the knowledge and know-how elements tested in Part I to be solved.)*

    **{EVAL_PRESENTATION} (2 marks)**
    """,



    "junior_mcq": """
    
    **PHILOSOPHIE (Inspirée par la recherche sur l'APC) :**
    L'épreuve doit évaluer à la fois la maîtrise des savoirs de base et la capacité de l'élève à les mobiliser dans une situation complexe (agir compétent). Elle doit permettre d'identifier la "dominante" de l'élève (ses points forts).

    **TYPE D'ÉVALUATION DEMANDÉ :** Premier Cycle (QCM Uniquement) sur 20 points.

    **STRUCTURE À RESPECTER SCRUPULEUSEMENT :**
    -   Crée exactement **20 questions à choix multiples (QCM)** pertinentes par rapport aux leçons et au contexte fournis.
    -   Chaque question doit avoir 4 options (A, B, C, D) et une seule réponse correcte.
    -   Les questions doivent couvrir différents niveaux de la taxonomie de Bloom (connaissance, compréhension, application).
    """,

    "second_cycle_fr": """
    **TYPE D'ÉVALUATION DEMANDÉ :** Second Cycle Francophone (Type APC Structuré) sur 20 points.

    **PHILOSOPHIE :**
    Au second cycle, l'épreuve évalue prioritairement l'agir compétent en situation complexe, plus que la restitution isolée de savoirs. Chaque situation-problème doit obliger l'élève à mobiliser ET combiner plusieurs ressources (savoirs, savoir-faire) issues de différentes leçons, pas une seule ressource à la fois.

    **STRUCTURE OBLIGATOIRE :**
    **{EVAL_PARTIE_1} : ÉVALUATION DES RESSOURCES (6 points)**
    *(2-3 questions courtes et précises qui vérifient la maîtrise des savoirs/savoir-faire indispensables pour aborder les situations-problèmes de la Partie II. Ces questions ne doivent pas être un pré-requis contournable : sans elles, l'élève ne peut pas réussir la Partie II.)*

    **{EVAL_PARTIE_2} : ÉVALUATION DE LA COMPÉTENCE (12 points)**
    *(Rédige 1 ou 2 **{EVAL_SITUATION_PROBLEME}** complexes et contextualisées au Cameroun, adaptées au niveau second cycle. Chaque situation doit :
    - présenter un contexte réaliste et une tâche claire avec consignes numérotées,
    - nécessiter la combinaison d'au moins 2-3 ressources différentes pour être résolue,
    - permettre de distinguer plusieurs niveaux de réussite (un élève qui ne mobilise qu'une partie des ressources doit pouvoir obtenir une note partielle cohérente, pas 0).)*

    **{EVAL_PRESENTATION} (2 points)**
    *(Grille de présentation : orthographe, clarté du raisonnement, soin de la copie.)*
    """,
    "second_cycle_en": """
    **TYPE D'ÉVALUATION DEMANDÉ :** Second Cycle Anglophone (GCE Style) sur 50 points au total.
    **STRUCTURE :**
    1.  **{EVAL_QCM_TITRE} (20 marks)**
           -   Crée exactement **20 questions à choix multiples (QCM)** pertinentes par rapport aux leçons et au contexte fournis.
           -   Chaque question doit avoir 4 options (A, B, C, D) et une seule réponse correcte.
           -   Les questions doivent couvrir différents niveaux de la taxonomie de Bloom (connaissance, compréhension, application).
    2.  **{EVAL_STRUCTURED_TITRE} (30 marks)**
        -   Crée 2 ou 3 problèmes complexes basés sur des **{EVAL_SITUATION_PROBLEME}**...
    """
}

# PROMPT EVALUATION

PROMPT_EVALUATION = """Tu es TCHATCHI AI, un expert en docimologie (la science de l'évaluation) pour le système éducatif camerounais.
Ta tâche est de générer une épreuve complète ET son corrigé détaillé, prêts à être imprimés.


**RÈGLES ABSOLUES ET CRITIQUES :**
1.  **Format :** Utilise exclusivement le format Markdown.
2.  **PAS D'INTRODUCTION :** Ta réponse doit commencer **DIRECTEMENT** par l'en-tête de l'épreuve. N'ajoute **AUCUNE** phrase d'introduction.
3.  **SÉPARATEUR OBLIGATOIRE :** Après avoir écrit TOUTE l'épreuve, tu DOIS impérativement insérer le séparateur `---CORRIGE---` sur sa propre ligne.
4.  **Langue :** La totalité de la sortie doit être dans la langue demandée : {langue_contenu}.
5.  **Contexte :** Base TOUTES les questions sur le "Contexte du programme" fourni.
6.  **Listes :** Utilise TOUJOURS un tiret `-` pour les listes à puces.
7.  **Formules :** Utilise le format LaTeX (`$...$` ou `$$...$$`).
8.  **INTERDICTION FORMELLE :** N'utilise JAMAIS, sous aucun prétexte, de balises HTML (`<b>`, `<i>`) ni de blocs de code Markdown (comme ` ```markdown ... ``` `). Ta réponse doit commencer DIRECTEMENT par le premier titre, sans aucune introduction ou balise d'enveloppement.
9.  **IMPORTANT :** Les titres de section (comme `**{EVAL_QCM_TITRE} **`) ne doivent JAMAIS commencer par une puce de liste (`-`, `*`, ou `•`). Ils doivent être sur leur propre ligne.




<!--
INSTRUCTIONS POUR LE NIVEAU DE LANGUE DE LA FICHE DE LECON:
*Le niveau de langue que tu utilisera dans les differentes parties de la fiche de leçon doit tenir compte du niveau de l'élève; Tu devras déter,iner le niveau en fonction de la valeur de la classe que tu recevra.
* Tu dois utiliser un language simple et facilement compréhensible pour les classes du premier cycle.
-->

**DONNÉES FOURNIES PAR L'ENSEIGNANT :**
- Langue de rédaction : {langue_contenu}
- Classe : {classe}
- Matière : {matiere}
- Durée : {duree}
- Coefficient : {coeff}
- Leçons à évaluer : {liste_lecons}
- Contexte du programme (fourni par RAG si disponible) :
---
{contexte_syllabus}
---

**INSTRUCTIONS SPÉCIFIQUES AU TYPE D'ÉPREUVE DEMANDÉ :**
---
{instructions_specifiques}
---

**TACHE :**
Commence à générer l'épreuve complète MAINTENANT.
"""


def generate_evaluation_logic(classe, matiere, liste_lecons, duree, coeff, langue_contenu, type_epreuve_key, contexte_syllabus):
    """
    Prépare le prompt et appelle l'API pour générer une évaluation.
    Version corrigée pour éviter les KeyError.
    """
    logging.info(f"Début de la génération de l'évaluation pour la classe : {classe}")

    lang_contenu_input = langue_contenu.lower()
    titles_lang_code = 'fr'
    if any(lang in lang_contenu_input for lang in ['english', 'anglais']): titles_lang_code = 'en'
    # ... (les autres elif pour les langues restent les mêmes) ...
    elif any(lang in lang_contenu_input for lang in ['german', 'allemand']): titles_lang_code = 'de'
    elif any(lang in lang_contenu_input for lang in ['spanish', 'espagnol']): titles_lang_code = 'es'
    elif any(lang in lang_contenu_input for lang in ['italian', 'italien']): titles_lang_code = 'it'
    elif any(lang in lang_contenu_input for lang in ['chinese', 'chinois']): titles_lang_code = 'zh'
    elif any(lang in lang_contenu_input for lang in ['arabic', 'arabe']): titles_lang_code = 'ar'

    # --- DÉBUT DE LA CORRECTION MAJEURE ---

    # 1. On récupère le template d'instructions spécifique au type d'épreuve.
    instructions_specifiques = INSTRUCTIONS_EVALUATION.get(type_epreuve_key, "Générer une évaluation standard.")

    # 2. On crée un dictionnaire unique 'format_args' qui contient TOUT ce dont le prompt a besoin.
    # On commence par les données dynamiques de la conversation.
    format_args = {
        'langue_contenu': langue_contenu,
        'classe': classe,
        'matiere': matiere,
        'duree': duree,
        'coeff': coeff,
        'liste_lecons': liste_lecons,
        'instructions_specifiques': instructions_specifiques,
        'contexte_syllabus': contexte_syllabus
    }

    # 3. On récupère TOUS les titres statiques (traduits) pour la langue choisie.
    all_titles_for_lang = TITLES.get(titles_lang_code, TITLES.get('fr', {}))
    
    # 4. On ajoute ces titres statiques à notre dictionnaire 'format_args'.
    # La méthode .update() fusionne les deux dictionnaires.
    format_args.update(all_titles_for_lang)

    # 5. On formate le prompt final en une seule fois.
    # La double étoile (**) décompresse le dictionnaire 'format_args' pour que chaque
    # clé corresponde à une variable dans le prompt. C'est la méthode standard pour ce cas.
    final_prompt = PROMPT_EVALUATION.format(**format_args)
    
    # --- FIN DE LA CORRECTION MAJEURE ---

    # On appelle l'IA avec le prompt maintenant correctement et complètement formaté.
    generated_text = call_llm_api(final_prompt)
    logging.info("Évaluation générée avec succès.")
    
    return generated_text, titles_lang_code


# =======================================================================
# PROMPT LECON DIGITALISEE (CORRECTED VERSION)
# =======================================================================

PROMPT_DIGITAL_LESSON = """
Tu es TCHATCHI AI, un expert en ingénierie pédagogique pour le MINESEC au Cameroun.
Ta mission est de créer une présentation de leçon digitalisée au format Markdown, en suivant la structure pédagogique officielle.
<!--
**RÈGLES ABSOLUES ET CRITIQUES POUR ÉVITER LES ERREURS DE COMPILATION :**
1.  **STRUCTURE STRICTE :** Chaque diapositive DOIT commencer par `## Diapositive X : Titre` (ou `## Slide X : Title` si en anglais). C'est la seule utilisation de titres (`##`).
2.  **PAS DE SOUS-TITRES :** N'utilise **JAMAIS** de titres de niveau 3 ou plus (`###`, `####`, etc.). Utilise `**Texte en gras**` pour mettre en évidence des sections à l'intérieur d'une diapositive.
3.  **PROFONDEUR DE LISTE LIMITÉE :** La règle la plus importante. N'utilise **JAMAIS** plus de **DEUX** niveaux de listes imbriquées.
    - `Niveau 1 (Correct)`
      - `Niveau 2 (Correct)`
        - `Niveau 3 (INTERDIT !)`
4.  **CARACTÈRES SPÉCIAUX :** Évite d'utiliser des caractères spéciaux complexes ou des symboles inhabituels qui pourraient poser problème à LaTeX.
5.  **LANGUE :** Rédige tout le contenu dans la langue `{langue_contenu}`. Le mot pour "Diapositive" doit être "Slide" si la langue est l'anglais, et "Diapositive" sinon.
6.  **LES TITRES DE {module} ET {lecon}: IL DOIVENT TOUJOURS ETRE EN LETTRES MAJUSCULES
7. **JEU BILINGUE (INTERDICTION FORMELLE) :**ne génère **JAMAIS** de code de tableau LaTeX. Génère UNIQUEMENT les lignes de données au format `MotSource;TraductionCible`, une par ligne. Le code de l'application créera le tableau.
8.  **Format :** Utilise exclusivement le format Markdown.
9.  **PAS D'INTRODUCTION :** Ta réponse doit commencer **DIRECTEMENT** par l'en-tête de la leçon. N'ajoute **AUCUNE** phrase d'introduction.
10.  **Contexte :** Base TOUTES les questions sur le "Contexte du programme" fourni.
11.  **Formules :** Utilise le format LaTeX (`$...$` ou `$$...$$`).
12.  **INTERDICTION FORMELLE :** N'utilise JAMAIS, sous aucun prétexte, de balises HTML (`<b>`, `<i>`) ni de blocs de code Markdown (comme ` ```markdown ... ``` `). Ta réponse doit commencer DIRECTEMENT par le premier titre, sans aucune introduction ou balise d'enveloppement.

-->
**DONNÉES DE LA LEÇON :**
- Classe: {classe}
- Matière: {matiere}
- Module: {module}
- Titre de la leçon: {lecon}

---

**GÉNÈRE MAINTENANT LA PRÉSENTATION EN SUIVANT SCRUPULEUSEMENT CE PLAN ET CES RÈGLES :**


`## Diapositive 1 : {titre_et_introduction}`
- **Matière :** {matiere}
- **Classe :** {classe}
- **Module:** {module}
- **Titre de la leçon:** {lecon}
- **Objectifs:**
*(Formule ici 2-4 objectifs clairs et mesurables. Commence par une phrase comme "À la fin de cette leçon, les apprenants devront être capables de :" traduite dans la langue {langue_contenu}, suivie d'une liste à puces.)*
- *(Le mot "Diapositive" doit être "Diapositive" si {langue_contenu} est le français, et "Slide " sinon.)*

`## Diapositive 2 : {prerequis}`
- *(Liste 2 ou 3 concepts que les élèves doivent connaître et pose une question simple pour les vérifier.)*
- *(Le mot "Diapositive" doit être "Diapositive" si {langue_contenu} est le français, et "Slide " sinon.)*

`## Diapositive 3 : {application_vie_reelle}`
- *(Rédige ici un scénario détaillé et contextualisé au Cameroun. Le scénario doit être simple et directement lié aux objectifs de la leçon.)*
- *(Le mot "Diapositive" doit être "Diapositive" si {langue_contenu} est le français, et "Slide " sinon.)*

`## Diapositive 4 : {concepts_cles} - Concept 1`
- *(Explique le premier concept majeur de la leçon. Sois clair et concis.)*
  - *(Le mot "Diapositive" doit être "Diapositive" si {langue_contenu} est le français, et "Slide " sinon.)*

`## Diapositive 5 : {concepts_cles} - Concept 2`
- *(Explique le deuxième concept majeur et continue ce modèle pour chaque concept clé.)*
  - *(Le mot "Diapositive" doit être "Diapositive" si {langue_contenu} est le français, et "Slide " sinon.)*

`## Diapositive 6 : {exercices_application}`
- *(Propose 1 ou 2 exercices courts à faire en classe qui couvrent les objectifs. Par exemple, un petit QCM de 3 questions ou un exercice d'application directe.)*
- *(Le mot "Diapositive" doit être "Diapositive" si {langue_contenu} est le français, et "Slide " sinon.)*

`## Diapositive 7 : Corrigé de l'exercice 1`
- *(Fournis le corrigé détaillé du premier exercice d'application.)*
- *(Le mot "Diapositive" doit être "Diapositive" si {langue_contenu} est le français, et "Slide " sinon.)*

`## Diapositive 8 : Corrigé de l'exercice 2`
- *(Fournis le corrigé détaillé du second exercice, s'il y en a un.)*
- *(Le mot "Diapositive" doit être "Diapositive" si {langue_contenu} est le français, et "Slide " sinon.)*

`## Diapositive 9 : RÉSUMÉ / SUMMARY`
- *(Fais un résumé très concis des points clés de la leçon en quelques puces.)*
- *(Le titre de cette diapositive doit être "Résumé" si {langue_contenu} est le français, et "Summary" sinon.)*
- *(Le mot "Diapositive" doit être "Diapositive" si {langue_contenu} est le français, et "Slide " sinon.)*

`## Diapositive 10 : {devoirs}`
- *(Rédige 1 ou 2 exercices clairs pour la maison pour renforcer les concepts vus.)*
- *(Le mot "Diapositive" doit être "Diapositive" si {langue_contenu} est le français, et "Slide " sinon.)*

`## Diapositive 11 : JEU BILINGUE / BILINGUAL GAME`
- **Titre :** *(Le titre de cette diapositive doit être "BILINGUAL GAME" si {langue_contenu} est le français, et "JEU BILINGUE" sinon.)*
- **Instructions pour l'IA (ne pas afficher) :**
    <!--
    Génère ici une liste de 5 termes importants de la leçon et leur traduction.
    Le format doit être une simple liste à puces Markdown, comme ceci :
    - MotSource 1 : TraductionCible 1
    - MotSource 2 : TraductionCible 2
    - ...

    RÈGLES DE TRADUCTION :
    1. La "Langue Source" est la langue de la leçon : {langue_contenu}.
    2. La "Traduction Cible" est déterminée comme suit :
        - SI la langue source ({langue_contenu}) est 'Français', ALORS la cible est l'Anglais.
        - POUR TOUTES LES AUTRES langues sources, la cible est TOUJOURS le Français.
    
    Exemple si {langue_contenu} est 'English':
    - Equation : Équation
    - Factorization : Factorisation
    
    Exemple si {langue_contenu} est 'Français':
    - Équation : Equation
    - Factorisation : Factorization
    -->
- *(Affiche ici la liste des 5 mots et leur traduction sous forme de liste à puces.)*
"""


# FONCTION DE LA LECON DIGITALISEE

def generate_digital_lesson_logic(classe, matiere, module, lecon, langue_contenu="Français", **kwargs):
    logging.info(f"Début de la génération de la leçon digitalisée : {lecon}")
    
    lang_contenu_input = langue_contenu.lower()
    titles_lang_code = 'fr'
    if any(lang in lang_contenu_input for lang in ['english', 'anglais']): titles_lang_code = 'en'
    elif any(lang in lang_contenu_input for lang in ['german', 'allemand']): titles_lang_code = 'de'
    elif any(lang in lang_contenu_input for lang in ['spanish', 'espagnol']): titles_lang_code = 'es'
    elif any(lang in lang_contenu_input for lang in ['italian', 'italien']): titles_lang_code = 'it'
    elif any(lang in lang_contenu_input for lang in ['chinese', 'chinois']): titles_lang_code = 'zh'
    elif any(lang in lang_contenu_input for lang in ['arabic', 'arabe']): titles_lang_code = 'ar'
    
    selected_titles = TITLES.get(titles_lang_code, TITLES.get('fr', {}))

    final_prompt = PROMPT_DIGITAL_LESSON.format(
        classe=classe, matiere=matiere, module=module, lecon=lecon, langue_contenu=langue_contenu,
        # On passe les nouveaux titres traduits
        titre_et_introduction=selected_titles.get("TITRE_ET_INTRODUCTION", "Introduction"),  # NOUVEAU, avec valeur de secours
        plan_lecon=selected_titles.get("PLAN_LECON"),
        prerequis=selected_titles.get("PREREQUIS"),
        application_vie_reelle=selected_titles.get("APPLICATION_VIE_REELLE"),
        concepts_cles=selected_titles.get("CONCEPTS_CLES"),
        exercices_application=selected_titles.get("EXERCICES_APPLICATION"),
        devoirs=selected_titles.get("DEVOIRS")
    )

     # MODIFICATION : On utilise la nouvelle fonction avec fallback
    generated_text = call_llm_api(final_prompt)
    logging.info("Présentation digitalisée générée avec succès.")

    # NOUVEAU : ajout d'une simulation interactive VÉRIFIÉE (pas générée par l'IA).
    # On cherche dans notre base statique une simulation pertinente pour ce
    # sujet, et on l'ajoute directement en Python après la génération —
    # jamais via le prompt, pour garantir que le lien est toujours réel.
    simulation = trouver_simulation(matiere, lecon, module)
    if simulation:
        titre_diapo = "Diapositive Supplémentaire" if titles_lang_code == 'fr' else "Additional Slide"
        titre_section = "Simulation Interactive Recommandée" if titles_lang_code == 'fr' else "Recommended Interactive Simulation"
        generated_text += (
            f"\n\n## {titre_diapo} : {titre_section}\n"
            f"- **[{simulation['nom']}]({simulation['url']})** : *{simulation['description']}*\n"
        )
        logging.info(f"Simulation ajoutée à la leçon digitalisée : {simulation['nom']}")
    else:
        logging.info("Aucune simulation pertinente trouvée dans la base pour cette leçon.")

    return generated_text, titles_lang_code