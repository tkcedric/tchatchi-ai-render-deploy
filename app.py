# app.py - Version finale avec une machine à états robuste pour la fonctionnalité "Retour"

import logging
from flask import Flask, request, jsonify, send_file, Response, render_template,send_from_directory,after_this_request
import requests
from flask_cors import CORS
from core_logic import generate_lesson_logic, generate_integration_logic, generate_evaluation_logic, generate_digital_lesson_logic
import os
import uuid
import re
import shutil # Importé pour le nettoyage des dossiers
from utils import create_pdf_with_pandoc
from database import increment_stat, get_all_stats, init_db 

# On importe les dictionnaires de menus de notre code original
from bot_data import CLASSES, MATIERES, SUBSYSTEME_FR, SUBSYSTEME_EN, LANGUES_CONTENU_COMPLET, LANGUES_CONTENU_SIMPLIFIE,  REGENERATE_OPTION_FR, REGENERATE_OPTION_EN

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
app = Flask(__name__)
CORS(app)

# initialisation de la bd
init_db()

# --- Configuration pour les fichiers temporaires ---
# On s'assure que le dossier pour les téléchargements temporaires existe.
TEMP_FOLDER = '/tmp/tchatchiai_downloads'
os.makedirs(TEMP_FOLDER, exist_ok=True)


# =======================================================================
# CONSTANTES ET ARCHITECTURE DE CONVERSATION
# =======================================================================
BACK_OPTION_FR = "⬅️ Retour"
BACK_OPTION_EN = "⬅️ Back"

DATA_KEY_FOR_STEP = {
    'select_option': 'flow_type',
    'lecon_ask_subsystem': 'subsystem', 'int_ask_subsystem': 'subsystem', 'eval_ask_subsystem': 'subsystem',
    'lecon_ask_classe': 'classe', 'int_ask_classe': 'classe', 'eval_ask_classe': 'classe',
    'lecon_ask_matiere': 'matiere', 'int_ask_matiere': 'matiere', 'eval_ask_matiere': 'matiere',
    'lecon_ask_module': 'module', 'eval_ask_module': 'module',
    'lecon_ask_lecon': 'lecon',
    'lecon_ask_syllabus_method': None,
    'lecon_get_manual_syllabus': 'syllabus', 'lecon_ask_langue_contenu': 'langue_contenu',
    'int_ask_lecons': 'liste_lecons', 'int_ask_objectifs': 'objectifs_lecons', 'int_ask_langue_contenu': 'langue_contenu',
    'eval_ask_lecons': 'liste_lecons', 'eval_ask_syllabus_method': None,
    'eval_get_manual_syllabus': 'syllabus', 'eval_ask_duree_coeff': ['duree', 'coeff'],
    'eval_ask_type': 'type_epreuve', 'eval_ask_langue_contenu': 'langue_contenu',
    'digital_ask_subsystem': 'subsystem',
    'digital_ask_classe': 'classe',
    'digital_ask_matiere': 'matiere',
    'digital_ask_module': 'module',
    'digital_ask_lecon': 'lecon'
}

CONVERSATION_FLOW = {
    'select_option': {
        'question_fr': "Que souhaitez-vous faire ?", 'question_en': "What would you like to do?",
        'get_options': lambda lang, data: ["Préparer une leçon", "Leçon digitalisée", "Produire une activité d'intégration", "Créer une évaluation"] if lang == 'fr' else ["Prepare a lesson", "Digitalised lesson","Produce an integration activity", "Create an assessment"],
        'get_next_step': lambda msg: {'leçon':'lecon_ask_subsystem', 'lesson':'lecon_ask_subsystem', 'digitalisée': 'digital_ask_subsystem', 'digitalised': 'digital_ask_subsystem', 'intégration':'int_ask_subsystem', 'integration':'int_ask_subsystem', 'évaluation':'eval_ask_subsystem', 'assessment':'eval_ask_subsystem'}.get(next((k for k in ['leçon','lesson','digitalisée', 'digitalised', 'intégration','integration','évaluation','assessment'] if k in msg.lower()),''),None)
    },
    # --- FLUX LEÇON ---
    'lecon_ask_subsystem': {'question_fr': "Veuillez sélectionner le sous-système :", 'question_en': "Please select the subsystem:", 'get_options': lambda l,d: SUBSYSTEME_FR if l=='fr' else SUBSYSTEME_EN, 'get_next_step': lambda m: 'lecon_ask_classe'},
    'lecon_ask_classe': {'question_fr': "Veuillez choisir une classe :", 'question_en': "Please choose a class:", 'get_options': lambda l,d: CLASSES[l].get(d.get('subsystem'),[]), 'get_next_step': lambda m: 'lecon_ask_matiere'},
    'lecon_ask_matiere': {'question_fr': "Choisissez une matière :", 'question_en': "Choose a subject:", 'get_options': lambda l,d: MATIERES[l].get(d.get('subsystem'),[]), 'get_next_step': lambda m: 'lecon_ask_module'},
    'lecon_ask_module': {'question_fr': "Quel est le titre du module ?", 'question_en': "What is the module title?", 'get_options': lambda l,d: [], 'get_next_step': lambda m: 'lecon_ask_lecon', 'is_text_input': True},
    'lecon_ask_lecon': {'question_fr': "Quel est le titre de la leçon ?", 'question_en': "What is the title of the lesson?", 'get_options': lambda l,d: [], 'get_next_step': lambda m: 'lecon_ask_syllabus_method', 'is_text_input': True},
    'lecon_ask_syllabus_method': {'question_fr': "Comment obtenir les informations du syllabus ?", 'question_en': "How to get syllabus info?", 'get_options': lambda l,d: ["🤖 Recherche Automatique (RAG)", "✍️ Fournir Manuellement"] if l=='fr' else ["🤖 Automatic Search (RAG)", "✍️ Provide Manually"], 'get_next_step': lambda m: 'lecon_get_manual_syllabus' if 'Manu' in m else 'lecon_ask_langue_contenu'},
    'lecon_get_manual_syllabus': {'question_fr': "D'accord, veuillez coller l'extrait du syllabus.", 'question_en': "Okay, please paste the syllabus extract.", 'get_options': lambda l,d: [], 'get_next_step': lambda m: 'lecon_ask_langue_contenu', 'is_text_input': True},
    'lecon_ask_langue_contenu': {'question_fr': "En quelle langue le contenu doit-il être rédigé ?", 'question_en': "In which language should the content be written?", 'get_options': lambda l,d: LANGUES_CONTENU_SIMPLIFIE if l=='en' else LANGUES_CONTENU_COMPLET, 'get_next_step': lambda m: 'pending_generation'},
   # --- FLUX ACTIVITE D'INTEGRATION ---
    'int_ask_subsystem': {'question_fr': "Veuillez sélectionner le sous-système :", 'question_en': "Please select the subsystem:", 'get_options': lambda l,d: SUBSYSTEME_FR if l == 'fr' else SUBSYSTEME_EN, 'get_next_step': lambda m: 'int_ask_classe'},
    'int_ask_classe': {'question_fr': "Veuillez choisir une classe :", 'question_en': "Please choose a class:", 'get_options': lambda l,d: CLASSES[l].get(d.get('subsystem'), []), 'get_next_step': lambda m: 'int_ask_matiere'},
    'int_ask_matiere': {'question_fr': "Choisissez une matière :", 'question_en': "Choose a subject:", 'get_options': lambda l,d: MATIERES[l].get(d.get('subsystem'), []), 'get_next_step': lambda m: 'int_ask_lecons'},
    'int_ask_lecons': {'question_fr': "Veuillez lister les leçons ou thèmes à intégrer.", 'question_en': "Please list the lessons or themes to integrate.", 'get_options': lambda l,d: [], 'get_next_step': lambda m: 'int_ask_objectifs', 'is_text_input': True},
    'int_ask_objectifs': {'question_fr': "Quels sont les objectifs ou concepts clés à évaluer ?", 'question_en': "What are the key objectives or concepts to assess?", 'get_options': lambda l,d: [], 'get_next_step': lambda m: 'int_ask_langue_contenu', 'is_text_input': True},
    'int_ask_langue_contenu': {'question_fr': "En quelle langue l'activité doit-elle être rédigée ?", 'question_en': "In which language should the activity be written?", 'get_options': lambda l,d: LANGUES_CONTENU_SIMPLIFIE if l == 'en' else LANGUES_CONTENU_COMPLET, 'get_next_step': lambda m: 'pending_generation'},
    # --- FLUX  EVALUATION ---
    'eval_ask_subsystem': {'question_fr': "Veuillez sélectionner le sous-système :", 'question_en': "Please select the subsystem:", 'get_options': lambda l,d: SUBSYSTEME_FR if l == 'fr' else SUBSYSTEME_EN, 'get_next_step': lambda m: 'eval_ask_classe'},
    'eval_ask_classe': {'question_fr': "Veuillez choisir une classe :", 'question_en': "Please choose a class:", 'get_options': lambda l,d: CLASSES[l].get(d.get('subsystem'), []), 'get_next_step': lambda m: 'eval_ask_matiere'},
    'eval_ask_matiere': {'question_fr': "Choisissez une matière :", 'question_en': "Choose a subject:", 'get_options': lambda l,d: MATIERES[l].get(d.get('subsystem'), []), 'get_next_step': lambda m: 'eval_ask_module'},
    'eval_ask_module': { 'question_fr': "Quel est le titre du module ?", 'question_en': "What is the module title?", 'get_options': lambda l,d: [], 'get_next_step': lambda m: 'eval_ask_lecons', 'is_text_input': True },
    'eval_ask_lecons': {'question_fr': "Sur quelles leçons portera l'évaluation ?", 'question_en': "Which lessons will the assessment cover?", 'get_options': lambda l,d: [], 'get_next_step': lambda m: 'eval_ask_syllabus_method', 'is_text_input': True},
    'eval_ask_syllabus_method': {'question_fr': "Comment obtenir les informations du programme ?", 'question_en': "How to get curriculum info?", 'get_options': lambda l,d: ["🤖 Recherche Automatique (RAG)", "✍️ Fournir Manuellement"] if l == 'fr' else ["🤖 Automatic Search (RAG)", "✍️ Provide Manually"], 'get_next_step': lambda msg: 'eval_get_manual_syllabus' if 'Manu' in msg else 'eval_ask_duree_coeff'},
    'eval_get_manual_syllabus': {'question_fr': "D'accord. Veuillez copier-coller l'extrait du syllabus.", 'question_en': "Alright. Please copy and paste the syllabus extract.", 'get_options': lambda l,d: [], 'get_next_step': lambda m: 'eval_ask_duree_coeff', 'is_text_input': True},
    'eval_ask_duree_coeff': {'question_fr': "Quelle est la durée (ex: 1h30) et le coefficient (ex: 2) ?", 'question_en': "What is the duration (e.g., 1h 30min) and coefficient (e.g., 2)?", 'get_options': lambda l,d: [], 'get_next_step': lambda m: 'eval_ask_type', 'is_text_input': True},
    'eval_ask_type': {'question_fr': "Quel type d'épreuve souhaitez-vous ?", 'question_en': "Which type of test would you like?", 'get_options': lambda l,d: ["Ressources + Compétences", "QCM Uniquement"] if l == 'fr' else ["Resources + Competencies", "MCQ Only"], 'get_next_step': lambda m: 'eval_ask_langue_contenu'},
    'eval_ask_langue_contenu': {'question_fr': "En quelle langue l'épreuve doit-elle être rédigée ?", 'question_en': "In which language should the assessment be written?", 'get_options': lambda l,d: LANGUES_CONTENU_SIMPLIFIE if l == 'en' else LANGUES_CONTENU_COMPLET, 'get_next_step': lambda m: 'pending_generation'},
    # --- FLUX LEÇON DIGITALISÉE ---
    'digital_ask_subsystem': {'question_fr': "Leçon digitalisée : Quel sous-système ?", 'question_en': "Digitalised lesson: Which subsystem?", 'get_options': lambda l,d: SUBSYSTEME_FR if l=='fr' else SUBSYSTEME_EN, 'get_next_step': lambda m: 'digital_ask_classe'},
    'digital_ask_classe': {'question_fr': "Veuillez choisir une classe :", 'question_en': "Please choose a class:", 'get_options': lambda l,d: CLASSES[l].get(d.get('subsystem'),[]), 'get_next_step': lambda m: 'digital_ask_matiere'},
    'digital_ask_matiere': {'question_fr': "Choisissez une matière :", 'question_en': "Choose a subject:", 'get_options': lambda l,d: MATIERES[l].get(d.get('subsystem'),[]), 'get_next_step': lambda m: 'digital_ask_module'},
    'digital_ask_module': {'question_fr': "Quel est le titre du module ?", 'question_en': "What is the module title?", 'get_options': lambda l,d: [], 'get_next_step': lambda m: 'digital_ask_lecon', 'is_text_input': True},
    'digital_ask_lecon': {'question_fr': "Quel est le titre de la leçon à digitaliser ?", 'question_en': "What is the title of the lesson to digitalise?", 'get_options': lambda l,d: [], 'get_next_step': lambda m: 'pending_generation', 'is_text_input': True}
}

def handle_chat_recursive(state, message):
    fake_data = {'message': message, 'state': state}
    with app.test_request_context('/api/chat', method='POST', json=fake_data):
        return handle_chat()
    


@app.route('/api/chat', methods=['POST'])
def handle_chat():
    """
    Gère toute la logique de conversation du chatbot.
    Cette fonction est conçue comme une machine à états qui traite la demande de l'utilisateur
    en suivant un ordre de priorité clair pour éviter les erreurs.
    """
    # --- PHASE 0 : INITIALISATION ---
    # On récupère les données de la requête et on initialise nos variables de travail.
    data = request.get_json()
    user_message = data.get('message')
    state = data.get('state', {})
    
    current_step = state.get('currentStep', 'start')
    lang = state.get('lang', 'en')
    collected_data = state.get('collectedData', {})
    step_history = state.get('step_history', [])
    
    # =======================================================================
    # --- PHASE 1 : GESTION DES ACTIONS SPÉCIALES ---
    # Ces actions (Retour, Régénérer, etc.) ont la priorité sur le flux normal.
    # =======================================================================

    # Action 1: L'utilisateur veut régénérer la dernière ressource.
    if user_message in [REGENERATE_OPTION_FR, REGENERATE_OPTION_EN]:
        # La solution la plus simple : on force l'étape à "generation_step".
        # Le code continuera son exécution et entrera dans le bloc de génération plus bas,
        # en utilisant les "collected_data" qui sont déjà en mémoire.
        current_step = 'generation_step'

    # Action 2: Le frontend nous informe que la conversion PDF a échoué.
    elif user_message == "internal_pdf_generation_failed":
        response_text = "Désolé, la conversion en PDF a échoué. Cela est souvent dû à des caractères spéciaux inattendus. Vous pouvez essayer de régénérer le contenu." if lang == 'fr' else "Sorry, the PDF conversion failed. This is often due to unexpected special characters. You can try regenerating the content."
        options = [REGENERATE_OPTION_FR, "Recommencer"] if lang == 'fr' else [REGENERATE_OPTION_EN, "Restart"]
        # On retourne directement une réponse, car c'est une action terminale.
        return jsonify({'response': response_text, 'options': options, 'state': state})
    
    # Action 3: L'utilisateur veut revenir à l'étape précédente.
    elif user_message in [BACK_OPTION_FR, BACK_OPTION_EN]:
        if not step_history: # S'il n'y a pas d'historique, on recommence.
            state = {'lang': lang, 'currentStep': 'select_option', 'collectedData': {}, 'step_history': []}
        else: # Sinon, on dépile la dernière étape.
            step_to_revert_to = step_history.pop()
            # On retire la donnée collectée à cette étape pour pouvoir la redemander.
            data_key_to_remove = DATA_KEY_FOR_STEP.get(step_to_revert_to)
            if data_key_to_remove:
                if isinstance(data_key_to_remove, list):
                    for key in data_key_to_remove: collected_data.pop(key, None)
                else:
                    collected_data.pop(data_key_to_remove, None)
            # On met à jour l'état pour refléter le retour en arrière.
            state['currentStep'] = step_to_revert_to
            state['collectedData'] = collected_data
            state['step_history'] = step_history
        # On demande à la fonction d'afficher l'étape précédente.
        return handle_chat_recursive(state, "internal_show_step")

    # Action 4: L'utilisateur veut tout recommencer ou a fini un téléchargement.
    elif user_message in ["Recommencer", "Restart", "internal_pdf_download_complete"]:
        state = {'lang': lang, 'currentStep': 'select_option', 'collectedData': {}, 'step_history': []}
        # On demande à la fonction d'afficher la toute première option.
        return handle_chat_recursive(state, "internal_show_step")
    
    # =======================================================================
    # --- PHASE 2 : GESTION DES ÉTAPES DE CONTRÔLE DU FLUX ---
    # Ces étapes ne collectent pas de données mais dirigent la conversation.
    # =======================================================================

    # Étape 'start': Choix de la langue, la toute première interaction.
    if current_step == 'start':
        lang = 'fr' if 'Français' in user_message else 'en'
        state = {'lang': lang, 'currentStep': 'select_option', 'collectedData': {}, 'step_history': []}
        return handle_chat_recursive(state, "internal_show_step")
    
    # Étape 'pending_generation': La collecte de données est terminée, on passe à la génération.
    if current_step == 'pending_generation':
        # On met à jour la variable locale pour que le code entre dans le bloc de génération ci-dessous.
        current_step = 'generation_step'

    # =======================================================================
    # --- PHASE 3 : LE BLOC DE GÉNÉRATION ---
    # Si l'étape est 'generation_step', on appelle l'IA. C'est un bloc terminal.
    # =======================================================================
    if current_step == 'generation_step':
        flow_type = collected_data.get('flow_type')
        try:
            # Sécurité : si on arrive ici sans savoir quoi faire, on lève une erreur.
            if not flow_type:
                raise ValueError("flow_type est manquant dans collected_data. Impossible de générer.")
            
            # Logique de préparation des arguments et d'appel à l'IA (inchangée).
            # ...
            generated_text = ""
            lesson_args = {k: v for k, v in collected_data.items() if k in ['classe', 'matiere', 'module', 'lecon', 'syllabus', 'langue_contenu']}
            integration_args = {k: v for k, v in collected_data.items() if k in ['classe', 'matiere', 'liste_lecons', 'objectifs_lecons', 'langue_contenu']}
            evaluation_args = {k: v for k, v in collected_data.items() if k in ['classe', 'matiere', 'liste_lecons', 'duree', 'coeff', 'langue_contenu', 'type_epreuve_key', 'contexte_syllabus']}
            digital_args = {k: v for k, v in collected_data.items() if k in ['classe', 'matiere', 'module', 'lecon', 'langue_contenu']}

            if flow_type == 'lecon':
                generated_text, _ = generate_lesson_logic(**lesson_args)
                increment_stat('lessons_generated')
            elif flow_type == 'digital':
                generated_text, _ = generate_digital_lesson_logic(**digital_args)
                increment_stat('digital_lessons_generated')
            elif flow_type == 'integration':
                 generated_text, _ = generate_integration_logic(**integration_args)
                 increment_stat('integrations_generated')
            elif flow_type == 'evaluation':
                user_choice = collected_data.get('type_epreuve', '')
                collected_data['type_epreuve_key'] = "junior_mcq" if 'QCM' in user_choice else "junior_resources_competencies"
                collected_data['contexte_syllabus'] = collected_data.get('syllabus', "Non fourni.")
                evaluation_args['type_epreuve_key'] = collected_data['type_epreuve_key']
                evaluation_args['contexte_syllabus'] = collected_data['contexte_syllabus']
                args_to_send = {k: v for k, v in collected_data.items() if k in evaluation_args}
                generated_text, _ = generate_evaluation_logic(**args_to_send)
                increment_stat('evaluations_generated')
            
            increment_stat('total_documents')
            response_text = generated_text
            
            # Préparation des options après la génération (avec "Régénérer").
            if flow_type == 'digital':
                 options_fr = ["Recommencer", REGENERATE_OPTION_FR, "Télécharger en Présentation (PDF)"]
                 options_en = ["Restart", REGENERATE_OPTION_EN, "Download as Presentation (PDF)"]
            else:
                 options_fr = ["Recommencer", REGENERATE_OPTION_FR, "Télécharger en PDF"]
                 options_en = ["Restart", REGENERATE_OPTION_EN, "Download PDF"]
            options = options_fr if lang == 'fr' else options_en
            
            # Mise à jour finale de l'état avant de renvoyer la réponse.
            state['generated_text'] = generated_text
            state['step_history'] = [] # On vide l'historique car le flux est terminé.
            
        except Exception as e:
            logging.error(f"ERREUR LORS DE LA GÉNÉRATION (flow: {flow_type}): {e}")
            response_text = "Désolé, une erreur est survenue." if lang == 'fr' else "Sorry, an error occurred."
            options = ["Recommencer"] if lang == 'fr' else ["Restart"]
            state = {'lang': lang, 'currentStep': 'select_option', 'collectedData': {}, 'step_history': []}
        
        return jsonify({'response': response_text, 'options': options, 'state': state})

    # =======================================================================
    # --- PHASE 4 : GESTION DU FLUX DE CONVERSATION NORMAL ---
    # Si aucune des conditions ci-dessus n'est remplie, on suit la carte de conversation.
    # =======================================================================

    # On récupère la définition de l'étape actuelle.
    step_definition = CONVERSATION_FLOW.get(current_step)
    if not step_definition: # Si l'étape est inconnue, on recommence.
        state = {'lang': lang, 'currentStep': 'select_option', 'collectedData': {}, 'step_history': []}
        return handle_chat_recursive(state, "internal_show_step")

    # Si le message n'est pas "internal_show_step", cela signifie que l'utilisateur a répondu.
    if user_message != "internal_show_step":
        # A. On collecte la donnée fournie par l'utilisateur.
        if current_step == 'select_option':
            # CORRECTION CRUCIALE : On stocke 'flow_type' dans 'collected_data'.
            if 'digital' in user_message.lower(): collected_data['flow_type'] = 'digital'
            elif 'leçon' in user_message.lower() or 'lesson' in user_message.lower(): collected_data['flow_type'] = 'lecon'
            elif 'intégration' in user_message.lower() or 'integration' in user_message.lower(): collected_data['flow_type'] = 'integration'
            elif 'évaluation' in user_message.lower() or 'assessment' in user_message.lower(): collected_data['flow_type'] = 'evaluation'
        else:
            # Pour toutes les autres étapes, on utilise notre dictionnaire de mapping.
            data_key = DATA_KEY_FOR_STEP.get(current_step)
            if data_key:
                if isinstance(data_key, list):
                    parts = user_message.split(',')
                    collected_data[data_key[0]] = parts[0].strip() if parts else "N/A"
                    collected_data[data_key[1]] = parts[1].strip() if len(parts) > 1 else "N/A"
                elif data_key == 'subsystem':
                    collected_data[data_key] = 'esg' if 'général' in user_message.lower() or 'general' in user_message.lower() else 'est'
                else:
                    collected_data[data_key] = user_message

        # B. On détermine l'étape suivante.
        next_step_func = step_definition.get('get_next_step')
        next_step = next_step_func(user_message) if next_step_func else None
        if not next_step: # Si la réponse n'est pas comprise.
            response_text = "Je n'ai pas compris, veuillez réessayer." if lang == 'fr' else "I didn't understand, please try again."
            options = step_definition['get_options'](lang, collected_data)
            return jsonify({'response': response_text, 'options': options, 'state': state})
        
        # C. On met à jour l'état COMPLETEMENT avant l'appel récursif.
        step_history.append(current_step)
        state['currentStep'] = next_step
        state['collectedData'] = collected_data
        state['step_history'] = step_history

        # D. On demande à la fonction d'afficher la nouvelle étape.
        return handle_chat_recursive(state, "internal_show_step")
    
    # Si on arrive ici, cela signifie que le message était "internal_show_step".
    # On se contente donc d'afficher la question et les options de l'étape actuelle.
    response_text = step_definition['question_fr'] if lang == 'fr' else step_definition['question_en']
    options = list(step_definition['get_options'](lang, collected_data))
    is_text_input = step_definition.get('is_text_input', False)
    if step_history:
        options.insert(0, BACK_OPTION_FR if lang == 'fr' else BACK_OPTION_EN)
    
    return jsonify({'response': response_text, 'options': options, 'is_text_input': is_text_input, 'state': state})

#generation pdf
#la fonction handle_generate_pdf

# =======================================================================
# NOUVELLE ARCHITECTURE DE TÉLÉCHARGEMENT EN 2 ÉTAPES
# =======================================================================

# --- ÉTAPE 1 : Génération du PDF ---
@app.route('/api/generate-pdf', methods=['POST'])
def handle_generate_pdf():
    """
    Cette fonction ne fait qu'une chose : elle génère le PDF, le sauvegarde
    sur le serveur, et renvoie le nom du fichier à télécharger au frontend.
    """
    data = request.get_json()
    if not data or 'markdown_text' not in data or 'state' not in data:
        return jsonify({"error": "Données manquantes."}), 400

    markdown_text = data.get('markdown_text')
    state = data.get('state')
    doc_type = state.get('flow_type', 'document')
    lang = state.get('lang', 'en')
    collected_data = state.get('collectedData', {})

      # On récupère 'flow_type' depuis 'collectedData' et non plus depuis 'state'.
    doc_type = collected_data.get('flow_type', 'document')

    # --- Logique de nommage du fichier final (pour l'utilisateur) ---
    def sanitize_title(title_str):
        if not title_str: return "Sans_Titre"
        return re.sub(r'[^\w\s-]', '', title_str).strip().replace(' ', '_')

    prefix_map = {
        ('lecon', 'fr'): "lecon", ('lecon', 'en'): "lesson",
        ('digital', 'fr'): "lecon_digitalisee", ('digital', 'en'): "digital_lesson",
        ('integration', 'fr'): "activite_integration", ('integration', 'en'): "integration_activity",
        ('evaluation', 'fr'): "evaluation", ('evaluation', 'en'): "assessment"
    }
    prefix = prefix_map.get((doc_type, lang), "document")
    title = collected_data.get('lecon') or collected_data.get('module') or "Sans_Titre"
    final_download_name = f"tchatchiai_{prefix}_{sanitize_title(title)}.pdf"

    # On génère un nom de fichier temporaire unique pour le stockage sur le serveur
    temp_filename = f"{uuid.uuid4()}.pdf"
    temp_filepath = os.path.join(TEMP_FOLDER, temp_filename)

    try:
        lang_code = state.get('lang', 'en').lower()
        output_format = 'beamer' if doc_type == 'digital' else 'pdf'

        pdf_success = create_pdf_with_pandoc(
            text=markdown_text, filename=temp_filepath, lang_contenu_code=lang_code,
            doc_type=doc_type, output_format=output_format
        )
        if not pdf_success:
            raise Exception("La conversion Pandoc/LaTeX a échoué.")

        # Au lieu d'envoyer le fichier, on envoie une réponse JSON avec les noms
        return jsonify({
            "success": True,
            "temp_filename": temp_filename, # Le nom unique sur le serveur
            "download_filename": final_download_name # Le nom final pour l'utilisateur
        })

    except Exception as e:
        logging.error(f"Erreur lors de la création du PDF : {e}")
        return jsonify({"error": "Une erreur interne est survenue.", "details": str(e)}), 500


# --- ÉTAPE 2 : Téléchargement et Nettoyage ---
@app.route('/api/download/<temp_filename>/<download_filename>', methods=['GET'])
def download_and_cleanup_file(temp_filename, download_filename):
    """
    Cette fonction sert le fichier demandé avec le bon nom de téléchargement,
    puis programme sa suppression.
    """
    try:
        # On construit le chemin complet vers le fichier temporaire
        filepath = os.path.join(TEMP_FOLDER, temp_filename)
        
        if not os.path.exists(filepath):
            return jsonify({"error": "Fichier non trouvé ou déjà supprimé."}), 404

        # On prépare la réponse en envoyant le fichier
        response = send_file(filepath, as_attachment=True)
        
        # **LA CORRECTION EST ICI**
        # On force l'en-tête 'Content-Disposition' pour que le navigateur utilise le bon nom de fichier.
        # C'est la méthode la plus fiable.
        response.headers["Content-Disposition"] = f"attachment; filename=\"{download_filename}\""
        
        # On programme le nettoyage du fichier APRES l'envoi de la réponse
        @after_this_request
        def cleanup(response):
            try:
                os.remove(filepath)
                logging.info(f"Fichier temporaire supprimé : {temp_filename}")
            except Exception as e:
                logging.error(f"Erreur lors de la suppression du fichier temporaire {temp_filename}: {e}")
            return response
            
        return response

    except Exception as e:
        logging.error(f"Erreur inattendue dans la route de téléchargement: {e}")
        return jsonify({"error": "Une erreur de serveur est survenue lors du téléchargement."}), 500




# =======================================================================
# ROUTES FOR STATS
# =======================================================================

@app.route('/api/stats')
def get_stats():
    """Endpoint pour récupérer les statistiques d'utilisation."""
    # get_all_stats() already returns the dictionary in the correct format.
    # We can just return it directly.
    stats = get_all_stats()
    return jsonify(stats)
# =======================================================================
# ROUTES FOR STATIC PAGES
# =======================================================================

@app.route('/')
def index():
    """Serve the main application page"""
    return render_template('index.html')

@app.route('/about')
def about_page():
    """Route for the About page"""
    return render_template('about.html')

@app.route('/donate')
def donate_page():
    """Route for the Donate page"""
    return render_template('donate.html')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)