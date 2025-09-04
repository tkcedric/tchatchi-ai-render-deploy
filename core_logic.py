# core_logic.py - Version corrigée

import logging
from openai import OpenAI
from config import OPENAI_API_KEY, TITLES

# Configuration
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# On vérifie que la clé API est bien là, c'est une bonne pratique
if not OPENAI_API_KEY:
    raise ValueError("Clé OPENAI_API_KEY non trouvée dans la configuration.")

client = OpenAI(api_key=OPENAI_API_KEY,timeout=300)

# Le "Prompt Maître" pour la leçon - Version complète et vérifiée
PROMPT_UNIVERSAL = """Tu es TCHATCHI AI, un expert en ingénierie pédagogique pour le Cameroun.

**RÈGLES ABSOLUES DE FORMATAGE :**
1.  **Format Principal :** Tu DOIS utiliser le formatage **Markdown**.
2.  **Gras :** Utilise `**Texte en gras**` pour TOUS les titres et sous-titres.
3.  **Italique :** Utilise `*Texte en italique*` pour les instructions ou les exemples.
4.  **Listes :** Utilise TOUJOURS un tiret `-` pour les listes à puces.
5.  **Formules :** Utilise le format LaTeX (`$...$` ou `$$...$$`).
6.  **INTERDICTION FORMELLE :** N'utilise JAMAIS, sous aucun prétexte, de balises HTML (`<b>`, `<i>`) ni de blocs de code Markdown (comme ` ```markdown ... ``` `). Ta réponse doit commencer DIRECTEMENT par le premier titre, sans aucune introduction ou balise d'enveloppement.
7.  **IMPORTANT :** Les titres de section (comme `**{objectifs}**`) ne doivent JAMAIS commencer par une puce de liste (`-`, `*`, ou `•`). Ils doivent être sur leur propre ligne.
8.  **IMPORTANT:** la langue dans laquelle la lecon doit etre redigee est: {langue_contenu}
**LANGUE DE RÉDACTION FINALE :** {langue_contenu}

**DONNÉES DE LA LEÇON :**
- Classe: {classe}
- Matière: {matiere} 
- Module: {module}
- Titre: {lecon}
- Extrait du Syllabus: "{syllabus}"


---
**GÉNÈRE MAINTENANT la fiche de leçon en suivant EXACTEMENT cette structure et ces titres :**
<!--
INSTRUCTIONS POUR LE NIVEAU DE LANGUE DE LA FICHE DE LECON:
*Le niveau de langue que tu utilisera dans les differentes parties de la fiche de leçon doit tenir compte du niveau de l'élève; Tu devras déter,iner le niveau en fonction de la valeur de la classe que tu recevra.
* Tu dois utiliser un language simple et facilement compréhensible pour les classes du premier cycle.
-->

**{fiche_de_lecon}**
**{header_matiere}:** {matiere} 
**{header_classe}:** {classe}
**{header_duree}:** 50 minutes
**{header_lecon}:** {lecon}
**{objectifs}**
*(Utilise la liste des objectifs fournie par l'enseignant pour cette partie.Dans le cas ou aucun objectif n'est fourni, formule ici 2-3 objectifs clairs et mesurables en utilisant des listes avec des tirets "-". les objectifs doivent etre formuler avec les verbes de la taxonomie de Bloom. La liste des objectifs sera precedée d'une phrase: A la fin de cette lecon, les apprenants devront etre capables de:)*
*(La phrase: "A la fin de cette lecon, les apprenants devront etre capables de:" devra etre traduite avec {langue_contenu})*

**{situation_probleme}**
*(Rédige ici un scénario détaillé et contextualisé au Cameroun avec Contexte, Tâche, et Consignes.Voici un exemple: Voici un texte synthétique en trois paragraphes, directement exploitable comme situation-problème contextualisée pour une leçon APC en TIC au Cameroun :

Ton oncle vient de rénover sa maison à Garoua et a installé plusieurs appareils modernes : caméra de surveillance, ampoules connectées et une serrure automatique. Il t'a vu contrôler tous ces objets depuis ton téléphone et a été très surpris. Il te demande alors comment tout cela fonctionne.

Tu te rends compte qu'il ne connaît pas le concept d'objets connectés, ni la façon dont ils communiquent entre eux ou avec le téléphone. Tu décides donc de lui expliquer, avec des mots simples, ce qu'est l'Internet des Objets (IoT) et comment ces appareils peuvent fonctionner ensemble grâce à une connexion réseau.

Pour l'aider à mieux comprendre, tu vas lui préparer une courte présentation ou une fiche illustrée qui décrit le fonctionnement de l'IoT à la maison, en prenant des exemples concrets comme l'ampoule intelligente, la caméra Wi-Fi ou la serrure connectée.)*

**{deroulement}**

**{introduction}:**
*- Rédige une ou plusieurs questions de rappel des pré-requis necessaires a la bonne comprehension de la nouvelle lecon.*

**{activite_1}:**
*- Rédige le contenu d'une activité de découverte.*
<!--
INSTRUCTIONS POUR CETTE SECTION:
tu dois concevoir une activite qui va permettre aux eleves de decouvrir tous les concepts cles lies aux ojectifs de la lecon.
-->

**{activite_2}:**
- **{trace_ecrite}:** *(Rédige ici le cours complet et détaillé (minimum 800 mots pour les classes du premier cycle, maximun 1500 mots pour les classes du second cycle) dans le style d'un cours MINESEC.)*
<!--
INSTRUCTIONS POUR CETTE SECTION:
* Tu dois proposer un cours qui explique le plus simplement et detaille possibles les differents concepts de la lecon donnes dans les objectifs.
* Tu devras utiliser des formules proprietes, tableaux de comparaison, des exemples ou description d'illustrations.
* Pour les cours scientifiques il faut mettre un accent sur le trace des courbes, tableau de variation, formule chimiques etc...
* Si tu ne peux pas tracer, donner des descriptions soud forme tabulaire ou code matlab.
-->

**{activite_3}:**
*- Rédige un exercice d'application complet à faire en classe, suivi de son corrigé détaillé.*
<!--
INSTRUCTIONS POUR CETTE SECTION:
tu dois concevoir un exercice qui traite des principaux ojectifs de la lecon et leur corrige detaille.
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
4.  Tu dois séparer le mot source et sa traduction par un point-virgule ';'.affiche le resultat dans un tableau htlm. les entetes des colones du tableau doivent etre le nom de la langue des mots contenus dans la colone.
5. Le titre de cette partie doit etre "BILINGUAL GAME" si la lecon est en francais et "JEU BILINGUE" pour les autres langue

Exemples concrets :
- Si {langue_contenu} est 'Français', une ligne doit ressembler à : "Ensemble;Set"
- Si {langue_contenu} est 'English', une ligne doit ressembler à : "Set;Ensemble"
- Si {langue_contenu} est 'Deutsch', une ligne doit ressembler à : "Menge;Ensemble"

Commence à générer les 5 lignes de données MAINTENANT.
-->
</bilingual_data>
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

def generate_lesson_logic(classe, matiere, module, lecon, langue_contenu, syllabus="N/A"):
    """
    Contient la logique pour générer une fiche de leçon.
    Remplace la fonction generate_and_end du bot.
    """
    logging.info(f"Début de la génération pour la leçon : {lecon}")

    # 1. Déterminer le code de langue pour les titres
    lang_contenu_input = langue_contenu.lower()
    titles_lang_code = 'fr'
    if any(lang in lang_contenu_input for lang in ['english', 'anglais']): titles_lang_code = 'en'
    elif any(lang in lang_contenu_input for lang in ['german', 'allemand']): titles_lang_code = 'de'
    elif any(lang in lang_contenu_input for lang in ['spanish', 'espagnol']): titles_lang_code = 'es'
    elif any(lang in lang_contenu_input for lang in ['italian', 'italien']): titles_lang_code = 'it'
    elif any(lang in lang_contenu_input for lang in ['chinese', 'chinois']): titles_lang_code = 'zh'
    elif any(lang in lang_contenu_input for lang in ['arabic', 'arabe']): titles_lang_code = 'ar'
    
    selected_titles = TITLES.get(titles_lang_code, TITLES['fr'])

    

    # 2. Préparer le prompt complet en assignant chaque clé manuellement
    #    Ceci est la correction pour résoudre la KeyError
    final_prompt = PROMPT_UNIVERSAL.format(
        # Données de la leçon
        classe=classe,
        matiere=matiere, 
        module=module,
        lecon=lecon,
        syllabus=syllabus,
        langue_contenu=langue_contenu,

        # Titres de Section (mapping manuel)
        fiche_de_lecon=selected_titles["FICHE_DE_LECON"],
        objectifs=selected_titles["OBJECTIFS"],
        situation_probleme=selected_titles["SITUATION_PROBLEME"],
        deroulement=selected_titles["DEROULEMENT"],
        introduction=selected_titles["INTRODUCTION"],
        activite_1=selected_titles["ACTIVITE_1"],
        activite_2=selected_titles["ACTIVITE_2"],
        trace_ecrite=selected_titles["TRACE_ECRITE"],
        activite_3=selected_titles["ACTIVITE_3"],
        devoirs=selected_titles["DEVOIRS"],
        jeu_bilingue=selected_titles["JEU_BILINGUE"],

        # Titres de l'en-tête (mapping manuel)
        header_matiere=selected_titles["HEADER_MATIERE"],
        header_classe=selected_titles["HEADER_CLASSE"],
        header_duree=selected_titles["HEADER_DUREE"],
        header_lecon=selected_titles["HEADER_LECON"]
    )

    # 3. Appeler l'IA et retourner le résultat
    generated_text = call_openai_api(final_prompt)
    logging.info("Texte de la leçon généré avec succès.")
    
    return generated_text, titles_lang_code




# =======================================================================
# LOGIQUE POUR L'ACTIVITÉ D'INTÉGRATION
# =======================================================================

PROMPT_INTEGRATION = """Tu es TCHATCHI AI, un expert en ingénierie pédagogique (APC) au Cameroun.
Ta tâche est de créer une Activité d'Intégration complète de 50 minutes.
Le concept est de créer une situation-problème complexe qui force l'élève à combiner plusieurs compétences acquises.

<!--
INSTRUCTIONS POUR LE NIVEAU DE LANGUE DE LA FICHE DE LECON:
*Le niveau de langue que tu utilisera dans les differentes parties de la fiche de leçon doit tenir compte du niveau de l'élève; Tu devras déter,iner le niveau en fonction de la valeur de la classe que tu recevra.
* Tu dois utiliser un language simple et facilement compréhensible pour les classes du premier cycle.
-->

**DONNÉES FOURNIES :**
- Langue de rédaction : {langue_contenu}
- Classe : {classe}
- Matière/Module : {matiere}
- Thèmes / Leçons à intégrer : {liste_lecons}
- Objectifs/Concepts clés : {objectifs_lecons}

---
**INSTRUCTIONS :**
Génère la fiche en format Markdown (`**Titre**`, `*italique*`, `- liste`), en suivant EXACTEMENT la structure et les titres ci-dessous.

**{int_titre_principal}**
**{header_matiere}:** {matiere}
**{header_classe}:** {classe}
**{header_duree}:** 50 minutes
**{int_competences}:** *(Synthétise ici 2-3 compétences clés basées sur les leçons et objectifs fournis.)*

**{int_situation}**
*(Rédige ici un scénario détaillé et contextualisé au Cameroun. Le problème doit être complexe et nécessiter la combinaison des leçons.)*

**{int_guide}**
- **{int_etape_1}: Analyse du problème (10 min):** *Quelles sont les données ? Quelle est la question principale ?*
- **{int_etape_2}: Mobilisation des acquis (15 min):** *L'enseignant guide les élèves.*
- **{int_etape_3}: Résolution en groupe (15 min):** *Les élèves travaillent ensemble.*
- **{int_etape_4}: Synthèse et Correction (10 min):** *Mise en commun et correction.*

**{int_solution}**
*(Fournis ici une solution complète et bien rédigée au problème.)*
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
        
        # Mapping manuel des titres pour éviter les erreurs de casse
        int_titre_principal=selected_titles["INT_TITRE_PRINCIPAL"],
        header_matiere=selected_titles["HEADER_MATIERE"],
        header_classe=selected_titles["HEADER_CLASSE"],
        header_duree=selected_titles["HEADER_DUREE"],
        int_competences=selected_titles["INT_COMPETENCES"],
        int_situation=selected_titles["INT_SITUATION"],
        int_guide=selected_titles["INT_GUIDE"],
        int_etape_1=selected_titles["INT_ETAPE_1"],
        int_etape_2=selected_titles["INT_ETAPE_2"],
        int_etape_3=selected_titles["INT_ETAPE_3"],
        int_etape_4=selected_titles["INT_ETAPE_4"],
        int_solution=selected_titles["INT_SOLUTION"]
    )

    # Appeler l'IA (on réutilise la même fonction call_openai_api)
    generated_text = call_openai_api(final_prompt)
    logging.info("Activité d'intégration générée avec succès.")
    
    return generated_text, titles_lang_code



# =======================================================================
# LOGIQUE POUR L'ÉVALUATION
# =======================================================================
# Dictionnaire des instructions spécifiques pour chaque type d'évaluation

INSTRUCTIONS_EVALUATION = {
    "junior_resources_competencies": """
    **TYPE D'ÉVALUATION DEMANDÉ :** Premier Cycle (Ressources + Compétences) sur 20 points.

    **STRUCTURE OBLIGATOIRE À RECOPIER :**
    **{EVAL_PARTIE_1} (9 points)**

    **{EVAL_SAVOIRS} (4 points)**
    *(Crée ici 2 questions de définition...)*

    **{EVAL_SAVOIR_FAIRE} (5 points)**
    *(Crée ici 2 petits exercices d'application...dans un exercice tu peux proposer une table a deux colonnes: colonne A et colonne B avec quatre lignes. les elements de la conne A seront numerotes de 1 a
     4. ceeux de la colonne B de A a D. l'eleve devra faire des correspondances entre les elements de la colonne A et ceux de la conne B). cet exercice doit etre sur 2 points*

    **{EVAL_PARTIE_2} (9 points)**
    *(Crée ici une **{EVAL_SITUATION_PROBLEME}** riche...)*

    **{EVAL_PRESENTATION} (2 points)**
    """,
    "Resources + Competencies": """
    **TEST TYPE REQUESTED:** Junior Cycle (Resources + Competencies) over 20 marks.

    **MANDATORY STRUCTURE TO COPY:**
    **{EVAL_PARTIE_1} (9 marks)**

    **{EVAL_SAVOIRS} (4 marks)**
    *(Create here 2 definition questions...)*

    **{EVAL_SAVOIR_FAIRE} (5 marks)**
    *(Create here 2 small application exercises...)*

    **{EVAL_PARTIE_2} (9 marks)**
    *(Create here a rich **{EVAL_SITUATION_PROBLEME}**...)*

    **{EVAL_PRESENTATION} (2 marks)**
    """,


    "junior_mcq": """
    **TYPE D'ÉVALUATION DEMANDÉ :** Premier Cycle (QCM Uniquement) sur 20 points.

    **STRUCTURE À RESPECTER SCRUPULEUSEMENT :**
    -   Crée exactement **20 questions à choix multiples (QCM)** pertinentes par rapport aux leçons et au contexte fournis.
    -   Chaque question doit avoir 4 options (A, B, C, D) et une seule réponse correcte.
    -   Les questions doivent couvrir différents niveaux de la taxonomie de Bloom (connaissance, compréhension, application).
    """,

    "second_cycle_fr": """
    **TYPE D'ÉVALUATION DEMANDÉ :** Second Cycle Francophone (Type APC Structuré) sur 20 points.
    **STRUCTURE :** L'épreuve est constituée d'une ou deux **{EVAL_SITUATION_PROBLEME} complexes**...
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

**RÈGLES ABSOLUES :**
1.  **Format :** Utilise exclusivement le format Markdown (`**Titre**`, `*italique*`, `- liste`).
2.  **SÉPARATEUR OBLIGATOIRE :** Après avoir écrit TOUTE l'épreuve, tu DOIS impérativement insérer le séparateur `---CORRIGE---` sur sa propre ligne. C'est une instruction critique. La structure doit être : [TOUTE L'ÉPREUVE] puis `---CORRIGE---` puis [TOUT LE CORRIGÉ].
3.  **Langue :** La totalité de la sortie (épreuve et corrigé) doit être dans la langue demandée.
4.  **Contexte :** Base TOUTES les questions sur le "Contexte du programme" fourni ci-dessous, qui est extrait des documents officiels.

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
    Prépare le prompt et appelle l'API OpenAI pour générer une évaluation.
    """
    logging.info(f"Début de la génération de l'évaluation pour la classe : {classe}")

    lang_contenu_input = langue_contenu.lower()
    titles_lang_code = 'fr'
    if any(lang in lang_contenu_input for lang in ['english', 'anglais']): titles_lang_code = 'en'
    elif any(lang in lang_contenu_input for lang in ['german', 'allemand']): titles_lang_code = 'de'
    elif any(lang in lang_contenu_input for lang in ['spanish', 'espagnol']): titles_lang_code = 'es'
    elif any(lang in lang_contenu_input for lang in ['italian', 'italien']): titles_lang_code = 'it'
    elif any(lang in lang_contenu_input for lang in ['chinese', 'chinois']): titles_lang_code = 'zh'
    elif any(lang in lang_contenu_input for lang in ['arabic', 'arabe']): titles_lang_code = 'ar'
    
    selected_titles = TITLES.get(titles_lang_code, TITLES['fr'])

    # On récupère le modèle d'instructions et on le formate avec les titres traduits
    instructions_template = INSTRUCTIONS_EVALUATION.get(type_epreuve_key, "Générer une évaluation standard.")
    instructions_specifiques = instructions_template.format(**selected_titles)

    final_prompt = PROMPT_EVALUATION.format(
        langue_contenu=langue_contenu,
        classe=classe,
        matiere=matiere,
        duree=duree,
        coeff=coeff,
        liste_lecons=liste_lecons,
        instructions_specifiques=instructions_specifiques,
        contexte_syllabus=contexte_syllabus
    )

    generated_text = call_openai_api(final_prompt)
    logging.info("Évaluation générée avec succès.")
    
    return generated_text, titles_lang_code