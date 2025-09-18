# app.py - Version finale avec une machine à états robuste pour la fonctionnalité "Retour"

import logging
from flask import Flask, request, jsonify, send_file, Response, render_template
import requests
from flask_cors import CORS
from core_logic import generate_lesson_logic, generate_integration_logic, generate_evaluation_logic
import os
import uuid
from utils import create_pdf_with_pandoc
from database import increment_stat, get_all_stats, init_db 

# On importe les dictionnaires de menus de notre code original
from bot_data import CLASSES, MATIERES, SUBSYSTEME_FR, SUBSYSTEME_EN, LANGUES_CONTENU_COMPLET, LANGUES_CONTENU_SIMPLIFIE

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
app = Flask(__name__)
CORS(app)

# initialisation de la bd
init_db()

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
    'eval_ask_type': 'type_epreuve', 'eval_ask_langue_contenu': 'langue_contenu'
}

CONVERSATION_FLOW = {
    'select_option': {
        'question_fr': "Que souhaitez-vous faire ?", 'question_en': "What would you like to do?",
        'get_options': lambda lang, data: ["Préparer une leçon", "Produire une activité d'intégration", "Créer une évaluation"] if lang == 'fr' else ["Prepare a lesson", "Produce an integration activity", "Create an assessment"],
        'get_next_step': lambda msg: {'leçon':'lecon_ask_subsystem', 'lesson':'lecon_ask_subsystem', 'intégration':'int_ask_subsystem', 'integration':'int_ask_subsystem', 'évaluation':'eval_ask_subsystem', 'assessment':'eval_ask_subsystem'}.get(next((k for k in ['leçon','lesson','intégration','integration','évaluation','assessment'] if k in msg.lower()),''),None)
    },
    'lecon_ask_subsystem': {'question_fr': "Veuillez sélectionner le sous-système :", 'question_en': "Please select the subsystem:", 'get_options': lambda l,d: SUBSYSTEME_FR if l=='fr' else SUBSYSTEME_EN, 'get_next_step': lambda m: 'lecon_ask_classe'},
    'lecon_ask_classe': {'question_fr': "Veuillez choisir une classe :", 'question_en': "Please choose a class:", 'get_options': lambda l,d: CLASSES[l].get(d.get('subsystem'),[]), 'get_next_step': lambda m: 'lecon_ask_matiere'},
    'lecon_ask_matiere': {'question_fr': "Choisissez une matière :", 'question_en': "Choose a subject:", 'get_options': lambda l,d: MATIERES[l].get(d.get('subsystem'),[]), 'get_next_step': lambda m: 'lecon_ask_module'},
    'lecon_ask_module': {'question_fr': "Quel est le titre du module ?", 'question_en': "What is the module title?", 'get_options': lambda l,d: [], 'get_next_step': lambda m: 'lecon_ask_lecon', 'is_text_input': True},
    'lecon_ask_lecon': {'question_fr': "Quel est le titre de la leçon ?", 'question_en': "What is the title of the lesson?", 'get_options': lambda l,d: [], 'get_next_step': lambda m: 'lecon_ask_syllabus_method', 'is_text_input': True},
    'lecon_ask_syllabus_method': {'question_fr': "Comment obtenir les informations du syllabus ?", 'question_en': "How to get syllabus info?", 'get_options': lambda l,d: ["🤖 Recherche Automatique (RAG)", "✍️ Fournir Manuellement"] if l=='fr' else ["🤖 Automatic Search (RAG)", "✍️ Provide Manually"], 'get_next_step': lambda m: 'lecon_get_manual_syllabus' if 'Manu' in m else 'lecon_ask_langue_contenu'},
    'lecon_get_manual_syllabus': {'question_fr': "D'accord, veuillez coller l'extrait du syllabus.", 'question_en': "Okay, please paste the syllabus extract.", 'get_options': lambda l,d: [], 'get_next_step': lambda m: 'lecon_ask_langue_contenu', 'is_text_input': True},
    'lecon_ask_langue_contenu': {'question_fr': "En quelle langue le contenu doit-il être rédigé ?", 'question_en': "In which language should the content be written?", 'get_options': lambda l,d: LANGUES_CONTENU_SIMPLIFIE if l=='en' else LANGUES_CONTENU_COMPLET, 'get_next_step': lambda m: 'pending_generation'},
    'int_ask_subsystem': {'question_fr': "Veuillez sélectionner le sous-système :", 'question_en': "Please select the subsystem:", 'get_options': lambda l,d: SUBSYSTEME_FR if l == 'fr' else SUBSYSTEME_EN, 'get_next_step': lambda m: 'int_ask_classe'},
    'int_ask_classe': {'question_fr': "Veuillez choisir une classe :", 'question_en': "Please choose a class:", 'get_options': lambda l,d: CLASSES[l].get(d.get('subsystem'), []), 'get_next_step': lambda m: 'int_ask_matiere'},
    'int_ask_matiere': {'question_fr': "Choisissez une matière :", 'question_en': "Choose a subject:", 'get_options': lambda l,d: MATIERES[l].get(d.get('subsystem'), []), 'get_next_step': lambda m: 'int_ask_lecons'},
    'int_ask_lecons': {'question_fr': "Veuillez lister les leçons ou thèmes à intégrer.", 'question_en': "Please list the lessons or themes to integrate.", 'get_options': lambda l,d: [], 'get_next_step': lambda m: 'int_ask_objectifs', 'is_text_input': True},
    'int_ask_objectifs': {'question_fr': "Quels sont les objectifs ou concepts clés à évaluer ?", 'question_en': "What are the key objectives or concepts to assess?", 'get_options': lambda l,d: [], 'get_next_step': lambda m: 'int_ask_langue_contenu', 'is_text_input': True},
    'int_ask_langue_contenu': {'question_fr': "En quelle langue l'activité doit-elle être rédigée ?", 'question_en': "In which language should the activity be written?", 'get_options': lambda l,d: LANGUES_CONTENU_SIMPLIFIE if l == 'en' else LANGUES_CONTENU_COMPLET, 'get_next_step': lambda m: 'pending_generation'},
    'eval_ask_subsystem': {'question_fr': "Veuillez sélectionner le sous-système :", 'question_en': "Please select the subsystem:", 'get_options': lambda l,d: SUBSYSTEME_FR if l == 'fr' else SUBSYSTEME_EN, 'get_next_step': lambda m: 'eval_ask_classe'},
    'eval_ask_classe': {'question_fr': "Veuillez choisir une classe :", 'question_en': "Please choose a class:", 'get_options': lambda l,d: CLASSES[l].get(d.get('subsystem'), []), 'get_next_step': lambda m: 'eval_ask_matiere'},
    'eval_ask_matiere': {'question_fr': "Choisissez une matière :", 'question_en': "Choose a subject:", 'get_options': lambda l,d: MATIERES[l].get(d.get('subsystem'), []), 'get_next_step': lambda m: 'eval_ask_module'},
    'eval_ask_module': { 'question_fr': "Quel est le titre du module ?", 'question_en': "What is the module title?", 'get_options': lambda l,d: [], 'get_next_step': lambda m: 'eval_ask_lecons', 'is_text_input': True },
    'eval_ask_lecons': {'question_fr': "Sur quelles leçons portera l'évaluation ?", 'question_en': "Which lessons will the assessment cover?", 'get_options': lambda l,d: [], 'get_next_step': lambda m: 'eval_ask_syllabus_method', 'is_text_input': True},
    'eval_ask_syllabus_method': {'question_fr': "Comment obtenir les informations du programme ?", 'question_en': "How to get curriculum info?", 'get_options': lambda l,d: ["🤖 Recherche Automatique (RAG)", "✍️ Fournir Manuellement"] if l == 'fr' else ["🤖 Automatic Search (RAG)", "✍️ Provide Manually"], 'get_next_step': lambda msg: 'eval_get_manual_syllabus' if 'Manu' in msg else 'eval_ask_duree_coeff'},
    'eval_get_manual_syllabus': {'question_fr': "D'accord. Veuillez copier-coller l'extrait du syllabus.", 'question_en': "Alright. Please copy and paste the syllabus extract.", 'get_options': lambda l,d: [], 'get_next_step': lambda m: 'eval_ask_duree_coeff', 'is_text_input': True},
    'eval_ask_duree_coeff': {'question_fr': "Quelle est la durée (ex: 1h30) et le coefficient (ex: 2) ?", 'question_en': "What is the duration (e.g., 1h 30min) and coefficient (e.g., 2)?", 'get_options': lambda l,d: [], 'get_next_step': lambda m: 'eval_ask_type', 'is_text_input': True},
    'eval_ask_type': {'question_fr': "Quel type d'épreuve souhaitez-vous ?", 'question_en': "Which type of test would you like?", 'get_options': lambda l,d: ["Ressources + Compétences", "QCM Uniquement"] if l == 'fr' else ["Resources + Competencies", "MCQ Only"], 'get_next_step': lambda m: 'eval_ask_langue_contenu'},
    'eval_ask_langue_contenu': {'question_fr': "En quelle langue l'épreuve doit-elle être rédigée ?", 'question_en': "In which language should the assessment be written?", 'get_options': lambda l,d: LANGUES_CONTENU_SIMPLIFIE if l == 'en' else LANGUES_CONTENU_COMPLET, 'get_next_step': lambda m: 'pending_generation'}
}

def handle_chat_recursive(state, message):
    fake_data = {'message': message, 'state': state}
    with app.test_request_context('/api/chat', method='POST', json=fake_data):
        return handle_chat()

@app.route('/api/chat', methods=['POST'])
def handle_chat():
    data = request.get_json()
    user_message = data.get('message')
    state = data.get('state', {})
    
    current_step = state.get('currentStep', 'start')
    lang = state.get('lang', 'en')
    collected_data = state.get('collectedData', {})
    step_history = state.get('step_history', [])
    
    # --- 1. GESTION DES ACTIONS SPÉCIALES (ONT LA PRIORITÉ) ---
    if user_message in [BACK_OPTION_FR, BACK_OPTION_EN]:
        if not step_history:
            state = {'lang': lang, 'currentStep': 'select_option', 'collectedData': {}, 'step_history': []}
        else:
            step_to_revert_to = step_history.pop()
            data_key_to_remove = DATA_KEY_FOR_STEP.get(step_to_revert_to)
            if data_key_to_remove:
                if isinstance(data_key_to_remove, list):
                    for key in data_key_to_remove: collected_data.pop(key, None)
                else:
                    collected_data.pop(data_key_to_remove, None)
            state['currentStep'] = step_to_revert_to
            state['collectedData'] = collected_data
            state['step_history'] = step_history
        return handle_chat_recursive(state, "internal_show_step")

    if user_message in ["Recommencer", "Restart", "internal_pdf_download_complete"]:
        state = {'lang': lang, 'currentStep': 'select_option', 'collectedData': {}, 'step_history': []}
        return handle_chat_recursive(state, "internal_show_step")
    
    # --- 2. GESTION DES ÉTAPES SPÉCIALES (qui ne sont pas dans la "carte") ---
    if current_step == 'start':
        lang = 'fr' if 'Français' in user_message else 'en'
        state = {'lang': lang, 'currentStep': 'select_option', 'collectedData': {}, 'step_history': []}
        return handle_chat_recursive(state, "internal_show_step")
    
    if current_step == 'pending_generation':
        # **CORRECTION CRUCIALE** : On s'assure que l'état est bien sauvegardé avant de passer à la génération
        state['currentStep'] = 'generation_step'
        return handle_chat_recursive(state, "internal_trigger_generation")
    
   # NOUVEAU BLOC CORRIGÉ

    if current_step == 'generation_step':
        flow_type = state.get('flow_type')
        try:
            generated_text = ""
            
            # On définit les arguments attendus pour chaque fonction
            lesson_args = ['classe', 'matiere', 'module', 'lecon', 'syllabus', 'langue_contenu']
            integration_args = ['classe', 'matiere', 'liste_lecons', 'objectifs_lecons', 'langue_contenu']
            evaluation_args = ['classe', 'matiere', 'liste_lecons', 'duree', 'coeff', 'langue_contenu', 'type_epreuve_key', 'contexte_syllabus']

            if flow_type == 'lecon':
                # On filtre le dictionnaire pour ne garder que les clés attendues
                args_to_send = {key: collected_data[key] for key in lesson_args if key in collected_data}
                generated_text, _ = generate_lesson_logic(**args_to_send)
                increment_stat('lessons_generated')

            elif flow_type == 'integration':
                args_to_send = {key: collected_data[key] for key in integration_args if key in collected_data}
                generated_text, _ = generate_integration_logic(**args_to_send)
                increment_stat('integrations_generated')

            elif flow_type == 'evaluation':
                # On prépare les données spécifiques à l'évaluation
                user_choice = collected_data.get('type_epreuve', '')
                collected_data['type_epreuve_key'] = "junior_mcq" if 'QCM' in user_choice else "junior_resources_competencies"
                collected_data['contexte_syllabus'] = collected_data.get('syllabus', "Non fourni.") # Utiliser .get pour éviter les erreurs
                
                args_to_send = {key: collected_data[key] for key in evaluation_args if key in collected_data}
                generated_text, _ = generate_evaluation_logic(**args_to_send)
                increment_stat('evaluations_generated')
            else:
                raise ValueError(f"Type de flux inconnu ou manquant: {flow_type}")
            
            increment_stat('total_documents')
            response_text = generated_text
            options = ["Recommencer", "Télécharger en PDF"] if lang == 'fr' else ["Restart", "Download PDF"]
            state['generated_text'] = generated_text
            state['step_history'] = []
        except Exception as e:
            logging.error(f"ERREUR LORS DE LA GÉNÉRATION (flow: {flow_type}): {e}")
            response_text = "Désolé, une erreur critique est survenue durant la génération." if lang == 'fr' else "Sorry, a critical error occurred during generation."
            options = ["Recommencer"] if lang == 'fr' else ["Restart"]
            state = {'lang': lang, 'currentStep': 'select_option', 'collectedData': {}, 'step_history': []}
        return jsonify({'response': response_text, 'options': options, 'state': state})

    # --- 3. GESTION DU FLUX DE CONVERSATION NORMAL (en utilisant la "carte") ---
    step_definition = CONVERSATION_FLOW.get(current_step)
    
    if not step_definition:
        state = {'lang': lang, 'currentStep': 'select_option', 'collectedData': {}, 'step_history': []}
        return handle_chat_recursive(state, "internal_show_step")

    # NOUVEAU BLOC CORRIGÉ

    # A. Traiter la réponse de l'utilisateur (si on ne fait pas que ré-afficher)
    if user_message != "internal_show_step":
        
        # **CORRECTION** : On gère spécifiquement l'étape 'select_option' pour définir le 'flow_type'
        if current_step == 'select_option':
            if 'leçon' in user_message.lower() or 'lesson' in user_message.lower():
                state['flow_type'] = 'lecon'
            elif 'intégration' in user_message.lower() or 'integration' in user_message.lower():
                state['flow_type'] = 'integration'
            elif 'évaluation' in user_message.lower() or 'assessment' in user_message.lower():
                state['flow_type'] = 'evaluation'
        
        # Logique de collecte de données pour les autres étapes
        else:
            data_key = DATA_KEY_FOR_STEP.get(current_step)
            if data_key:
                if isinstance(data_key, list):
                    parts = user_message.split(',')
                    collected_data[data_key[0]] = parts[0].strip() if len(parts) > 0 else "N/A"
                    collected_data[data_key[1]] = parts[1].strip() if len(parts) > 1 else "N/A"
                elif data_key == 'subsystem':
                    collected_data[data_key] = 'esg' if 'général' in user_message.lower() or 'general' in user_message.lower() else 'est'
                else:
                    collected_data[data_key] = user_message
        
        next_step_func = step_definition.get('get_next_step')
        next_step = next_step_func(user_message) if next_step_func else None
        
        if not next_step:
            response_text = "Je n'ai pas compris, veuillez réessayer." if lang == 'fr' else "I didn't understand, please try again."
            options = list(step_definition['get_options'](lang, collected_data))
            if step_history: options.insert(0, BACK_OPTION_FR if lang == 'fr' else BACK_OPTION_EN)
            return jsonify({'response': response_text, 'options': options, 'is_text_input': step_definition.get('is_text_input', False), 'state': state})
            
        step_history.append(current_step)
        state['currentStep'] = next_step
        
        # On met à jour l'état AVANT l'appel récursif
        state['step_history'] = step_history
        state['collectedData'] = collected_data
        return handle_chat_recursive(state, "internal_show_step")

    # B. Afficher la question et les options de l'étape actuelle
    response_text = step_definition['question_fr'] if lang == 'fr' else step_definition['question_en']
    options = list(step_definition['get_options'](lang, collected_data))
    is_text_input = step_definition.get('is_text_input', False)
    
    if step_history:
        options.insert(0, BACK_OPTION_FR if lang == 'fr' else BACK_OPTION_EN)

    state['collectedData'] = collected_data
    state['step_history'] = step_history
    return jsonify({'response': response_text, 'options': options, 'is_text_input': is_text_input, 'state': state})

# =======================================================================
# LE RESTE DU FICHIER EST INCHANGÉ
# =======================================================================

#generation pdf

@app.route('/api/generate-pdf', methods=['POST'])
def handle_generate_pdf():
    data = request.get_json()
    if not data or 'markdown_text' not in data or 'state' not in data:
        return jsonify({"error": "Données manquantes pour la génération du PDF."}), 400

    markdown_text = data.get('markdown_text')
    state = data.get('state')
    
    # --- LOGIQUE DE NOMMAGE DYNAMIQUE ---
    doc_type = state.get('flow_type', 'document')
    lang = state.get('lang', 'en')
    collected_data = state.get('collectedData', {})
    
    # On construit un nom de base à partir des données collectées
    base_name = "Document"
    if doc_type == 'lecon':
        lecon_name = collected_data.get('lecon', 'Lecon').replace(' ', '_')
        base_name = f"Fiche_Lecon_{lecon_name}" if lang == 'fr' else f"Lesson_Plan_{lecon_name}"
    elif doc_type == 'integration':
        module_name = collected_data.get('module', 'Module').replace(' ', '_')
        base_name = f"Activite_Integration_{module_name}" if lang == 'fr' else f"Integration_Activity_{module_name}"
    elif doc_type == 'evaluation':
        module_name = collected_data.get('module', 'Evaluation').replace(' ', '_')
        base_name = f"Evaluation_{module_name}" if lang == 'fr' else f"Assessment_{module_name}"

    final_download_name = f"{base_name}.pdf"
    # --- FIN DE LA LOGIQUE DE NOMMAGE ---

    pdf_filename_temp = f"temp_{uuid.uuid4()}.pdf"
    
    try:
        lang = state.get('lang', 'en').lower()
        doc_type = state.get('flow_type', 'lecon').lower()

        pdf_success = create_pdf_with_pandoc(
            text=markdown_text,
            filename=pdf_filename_temp,
            lang_contenu_code=lang,
            doc_type=doc_type
        )
        if not pdf_success:
            raise Exception("La conversion Pandoc/LaTeX a échoué.")

        return send_file(pdf_filename_temp, as_attachment=True, download_name=final_download_name)
    except Exception as e:
        logging.error(f"Erreur lors de la création du PDF : {e}")
        return jsonify({"error": "Une erreur interne est survenue.", "details": str(e)}), 500
    finally:
        if os.path.exists(pdf_filename_temp):
            os.remove(pdf_filename_temp)










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
    app.run(debug=True, port=5000)