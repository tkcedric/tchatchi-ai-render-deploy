# app.py - Version finale avec le nouvel endpoint /api/chat

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

# (Plus tard, on importera la logique de génération d'ici)
# from core_logic import generate_lesson_logic



def handle_chat_recursive(state, message):
    """
    Fonction helper pour appeler la logique de chat de manière interne,
    simulant une nouvelle requête de l'utilisateur.
    """
    # Crée un faux corps de requête
    fake_data = {
        'message': message,
        'state': state
    }
    
    # Contourne le contexte de la requête Flask pour un appel interne
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
    
    # =======================================================================
    # MACHINE À ÉTATS DE LA CONVERSATION - VERSION FINALE SIMPLIFIÉE
    # =======================================================================
    
      # On gère le cas spécial du trigger de génération envoyé par le frontend
    if user_message == "internal_trigger_generation":
        state['currentStep'] = 'generation_step'

    # Étape 0 : Commandes globales
    if user_message in ["Recommencer", "Restart"]:
        lang_to_keep = state.get('lang', 'en')
        state = {'lang': lang_to_keep, 'currentStep': 'select_option', 'collectedData': {}}
        response_text = "Recommençons. Que souhaitez-vous faire ?" if lang_to_keep == 'fr' else "Let's start over. What would you like to do?"
        options = ["Préparer une leçon", "Produire une activité d'intégration", "Créer une évaluation"] if lang_to_keep == 'fr' else ["Prepare a lesson", "Produce an integration activity", "Create an assessment"]

       # =======================================================================
    # NOUVELLE SECTION POUR GÉRER LA FIN DU TÉLÉCHARGEMENT
    # =======================================================================
    elif user_message == "internal_pdf_download_complete":
        lang_to_keep = state.get('lang', 'en')
        # On réinitialise l'état pour une nouvelle conversation, en gardant la langue
        state = {'lang': lang_to_keep, 'currentStep': 'select_option', 'collectedData': {}}
        response_text = "Que souhaitez-vous faire maintenant ?" if lang_to_keep == 'fr' else "What would you like to do now?"
        options = ["Préparer une leçon", "Produire une activité d'intégration", "Créer une évaluation"] if lang_to_keep == 'fr' else ["Prepare a lesson", "Produce an integration activity", "Create an assessment"]
    
    # Étape 1 : Démarrage
    elif current_step == 'start':
        if 'Français' in user_message:
            state.update({'lang': 'fr', 'currentStep': 'select_option'})
            lang = 'fr'
            response_text = ["Langue sélectionnée : Français.", "Que souhaitez-vous faire ?"]
            options = ["Préparer une leçon", "Produire une activité d'intégration", "Créer une évaluation"]
        else: # English par défaut
            state.update({'lang': 'en', 'currentStep': 'select_option'})
            lang = 'en'
            response_text = ["Language selected: English.", "What would you like to do?"]
            options = ["Prepare a lesson", "Produce an integration activity", "Create an assessment"]

    # Étape 2 : Aiguillage
    elif current_step == 'select_option':
        if 'leçon' in user_message.lower() or 'lesson' in user_message.lower():
            state.update({'flow_type': 'lecon', 'currentStep': 'lecon_ask_subsystem'})
            response_text = ["Ok, nous allons preparer une lecon.","Veuillez sélectionner le sous-système :"] if lang == 'fr' else ["Ok, we are going to prepare a lesson.","Please select the subsystem:"]
            options = SUBSYSTEME_FR if lang == 'fr' else SUBSYSTEME_EN
        elif 'intégration' in user_message.lower() or 'integration' in user_message.lower():
            state.update({'flow_type': 'integration', 'currentStep': 'int_ask_subsystem'})
            response_text = ["Ok, nous allons preparer une activite d'integration.","Veuillez sélectionner le sous-système :"] if lang == 'fr' else ["Ok, we are going to prepare an Integration Activity.","Please select the subsystem:"]
            options = SUBSYSTEME_FR if lang == 'fr' else SUBSYSTEME_EN
        elif 'évaluation' in user_message.lower() or 'assessment' in user_message.lower():
            state.update({'flow_type': 'evaluation', 'currentStep': 'eval_ask_subsystem'})
            response_text = ["Ok, nous allons preparer une evaluation.","Veuillez sélectionner le sous-système :"] if lang == 'fr' else ["Ok, we are going to prepare an evaluation.","Please select the subsystem:"]
            options = SUBSYSTEME_FR if lang == 'fr' else SUBSYSTEME_EN
            
    # ==========================================================
    # FLUX "LEÇON"
    # ==========================================================
    elif current_step.startswith('lecon_'):
        if current_step == 'lecon_ask_subsystem':
            collected_data['subsystem'] = 'esg' if 'général' in user_message.lower() or 'general' in user_message.lower() else 'est'
            state['currentStep'] = 'lecon_ask_classe'
            response_text = "Veuillez choisir une classe :" if lang == 'fr' else "Please choose a class:"
            options = CLASSES[lang][collected_data['subsystem']]
        elif current_step == 'lecon_ask_classe':
            collected_data['classe'] = user_message
            state['currentStep'] = 'lecon_ask_matiere'
            response_text = "Choisissez une matière :" if lang == 'fr' else "Choose a subject:"
            options = MATIERES[lang][collected_data.get('subsystem', 'esg')]
        elif current_step == 'lecon_ask_matiere':
            collected_data['matiere'] = user_message
            state['currentStep'] = 'lecon_ask_module'
            response_text = "Quel est le titre du module ?" if lang == 'fr' else "What is the module title?"
            options = []
        elif current_step == 'lecon_ask_module':
            collected_data['module'] = user_message
            state['currentStep'] = 'lecon_ask_lecon'
            response_text = "Quel est le titre de la leçon ?" if lang == 'fr' else "What is the title of the lesson?"
            options = []
        elif current_step == 'lecon_ask_lecon':
            collected_data['lecon'] = user_message
            state['currentStep'] = 'lecon_ask_syllabus_method'
            response_text = "Comment obtenir les informations du syllabus ?" if lang == 'fr' else "How to get the syllabus information?"
            options = ["🤖 Recherche Automatique (RAG)", "✍️ Fournir Manuellement"] if lang == 'fr' else ["🤖 Automatic Search (RAG)", "✍️ Provide Manually"]
# Dans app.py, remplacez les deux derniers elif du flux "leçon"

        elif current_step == 'lecon_ask_syllabus_method':
            if 'Manuellement' in user_message or 'Manually' in user_message:
                state['currentStep'] = 'lecon_get_manual_syllabus'
                response_text = "D'accord, veuillez coller l'extrait du syllabus." if lang == 'fr' else "Okay, please paste the syllabus extract."
                options = []
            else: # RAG
                collected_data['syllabus'] = "Contexte du syllabus trouvé par RAG..."
                state['currentStep'] = 'lecon_ask_langue_contenu'
                response_text = "En quelle langue le contenu doit-il être rédigé ?" if lang == 'fr' else "In which language should the content be written?"
                options = LANGUES_CONTENU_SIMPLIFIE if lang == 'en' else LANGUES_CONTENU_COMPLET
                
        elif current_step == 'lecon_get_manual_syllabus':
            collected_data['syllabus'] = user_message
            state['currentStep'] = 'lecon_ask_langue_contenu'
            response_text = "En quelle langue le contenu doit-il être rédigé ?" if lang == 'fr' else "In which language should the content be written?"
            options = LANGUES_CONTENU_SIMPLIFIE if lang == 'en' else LANGUES_CONTENU_COMPLET

        elif current_step == 'lecon_ask_langue_contenu':
            collected_data['langue_contenu'] = user_message
            state['collectedData'] = collected_data
            state['currentStep'] = 'pending_generation'
            response_text = "⏳ Préparation du contenu... Veuillez patienter."
            options = []
            return jsonify({'response': response_text, 'options': options, 'state': state})
        

    # ==========================================================
    # FLUX COMPLET POUR "ACTIVITÉ D'INTÉGRATION"
    # ==========================================================
    elif current_step == 'int_ask_subsystem':
        subsystem_code = 'esg' if 'général' in user_message.lower() or 'general' in user_message.lower() else 'est'
        collected_data['subsystem'] = subsystem_code
        state['currentStep'] = 'int_ask_classe'
        response_text = "Veuillez choisir une classe :" if lang == 'fr' else "Please choose a class:"
        options = CLASSES[lang][subsystem_code]
    elif current_step == 'int_ask_classe':
        collected_data['classe'] = user_message
        state['currentStep'] = 'int_ask_matiere'
        response_text = "Choisissez une matière :" if lang == 'fr' else "Choose a subject:"
        options = MATIERES[lang][collected_data.get('subsystem', 'esg')]
    elif current_step == 'int_ask_matiere':
        collected_data['matiere'] = user_message
        state['currentStep'] = 'int_ask_lecons'
        response_text = "Veuillez lister les leçons ou thèmes à intégrer." if lang == 'fr' else "Please list the lessons or themes to integrate."
        options = []
    elif current_step == 'int_ask_lecons':
        collected_data['liste_lecons'] = user_message
        state['currentStep'] = 'int_ask_objectifs'
        response_text = "Quels sont les objectifs ou concepts clés à évaluer ?" if lang == 'fr' else "What are the key objectives or concepts to assess?"
        options = []
    elif current_step == 'int_ask_objectifs':
        collected_data['objectifs_lecons'] = user_message
        state['currentStep'] = 'int_ask_langue_contenu'
        response_text = "En quelle langue l'activité doit-elle être rédigée ?" if lang == 'fr' else "In which language should the activity be written?"
        options = LANGUES_CONTENU_SIMPLIFIE if lang == 'en' else LANGUES_CONTENU_COMPLET
    elif current_step == 'int_ask_langue_contenu':
        collected_data['langue_contenu'] = user_message
        state['collectedData'] = collected_data
        state['currentStep'] = 'pending_generation'
        response_text = "⏳ Préparation du contenu... Veuillez patienter."
        options = []
        return jsonify({'response': response_text, 'options': options, 'state': state})
    

 

    # ==========================================================
    # FLUX "ÉVALUATION" - VERSION FINALE SIMPLIFIÉE
    # ==========================================================
    elif current_step.startswith('eval_'):
        if current_step == 'eval_ask_subsystem':
            subsystem_code = 'esg' if 'général' in user_message.lower() or 'general' in user_message.lower() else 'est'
            collected_data['subsystem'] = subsystem_code
            state['currentStep'] = 'eval_ask_classe'
            response_text = "Veuillez choisir une classe :" if lang == 'fr' else "Please choose a class:"
            options = CLASSES[lang][subsystem_code]
        elif current_step == 'eval_ask_classe':
            collected_data['classe'] = user_message
            state['currentStep'] = 'eval_ask_matiere'
            response_text = "Choisissez une matière :" if lang == 'fr' else "Choose a subject:"
            options = MATIERES[lang][collected_data.get('subsystem', 'esg')]
        elif current_step == 'eval_ask_matiere':
            collected_data['matiere'] = user_message
            state['currentStep'] = 'eval_ask_module'
            response_text = "Quel est le titre du module ?" if lang == 'fr' else "What is the module title?"
            options = []
        elif current_step == 'eval_ask_module':
            collected_data['module'] = user_message
            state['currentStep'] = 'eval_ask_lecons'
            response_text = "Sur quelles leçons portera l'évaluation ?" if lang == 'fr' else "Which lessons will the assessment cover?"
            options = []
        elif current_step == 'eval_ask_lecons':
            collected_data['liste_lecons'] = user_message
            state['currentStep'] = 'eval_ask_syllabus_method'
            response_text = "Parfait. Comment obtenir les informations du programme (syllabus) ?" if lang == 'fr' else "Perfect. How should I get the curriculum (syllabus) information?"
            options = ["🤖 Recherche Automatique (RAG)", "✍️ Fournir Manuellement"] if lang == 'fr' else ["🤖 Automatic Search (RAG)", "✍️ Provide Manually"]
        
        elif current_step == 'eval_ask_syllabus_method':
            if 'Manuellement' in user_message or 'Manually' in user_message:
                state['currentStep'] = 'eval_get_manual_syllabus'
                response_text = "D'accord. Veuillez copier-coller l'extrait du syllabus." if lang == 'fr' else "Alright. Please copy and paste the syllabus extract."
                options = []
            else: # Recherche Automatique
                syllabus_context = "Extrait du syllabus trouvé par RAG : ..."
                collected_data['syllabus'] = syllabus_context
                state['currentStep'] = 'eval_ask_duree_coeff'
                response_text = "Quelle est la durée (ex: 1h30) et le coefficient (ex: 2) ? Séparez par une virgule." if lang == 'fr' else "What is the duration (e.g., 1h 30min) and coefficient (e.g., 2)? Separate with a comma."
                options = []
                
        elif current_step == 'eval_get_manual_syllabus':
            collected_data['syllabus'] = user_message
            state['currentStep'] = 'eval_ask_duree_coeff'
            response_text = "Quelle est la durée (ex: 1h30) et le coefficient (ex: 2) ? Séparez par une virgule." if lang == 'fr' else "What is the duration (e.g., 1h 30min) and coefficient (e.g., 2)? Separate with a comma."
            options = []

        elif current_step == 'eval_ask_duree_coeff':
            parts = user_message.split(',')
            collected_data['duree'] = parts[0].strip() if len(parts) > 0 else "N/A"
            collected_data['coeff'] = parts[1].strip() if len(parts) > 1 else "N/A"
            state['currentStep'] = 'eval_ask_type'
            response_text = "Quel type d'épreuve souhaitez-vous ?" if lang == 'fr' else "Which type of test would you like?"
            options = ["Ressources + Compétences", "QCM Uniquement"] if lang == 'fr' else ["Resources + Competencies", "MCQ Only"]
        
        elif current_step == 'eval_ask_type':
            collected_data['type_epreuve'] = user_message
            state['currentStep'] = 'eval_ask_langue_contenu'
            response_text = "En quelle langue l'épreuve doit-elle être rédigée ?" if lang == 'fr' else "In which language should the assessment be written?"
            options = LANGUES_CONTENU_SIMPLIFIE if lang == 'en' else LANGUES_CONTENU_COMPLET

        elif current_step == 'eval_ask_langue_contenu':
            collected_data['langue_contenu'] = user_message
            # On a maintenant TOUTES les informations. On peut passer à la génération.
            user_choice_type = collected_data.get('type_epreuve', '')
            if 'QCM' in user_choice_type or 'MCQ' in user_choice_type:
                type_key = "MCQ Only" if lang == 'en' else "junior_mcq"
            else:
                type_key = "Resources + Competencies" if lang == 'en' else "junior_resources_competencies"
                collected_data['langue_contenu'] = user_message
                state['collectedData'] = collected_data
                state['currentStep'] = 'pending_generation'
                response_text = "⏳ Préparation du contenu... Veuillez patienter."
                options = []
                return jsonify({'response': response_text, 'options': options, 'state': state})
        
    # ==========================================================
    # ÉTAPE FINALE DE GÉNÉRATION (COMMUNE À TOUS LES FLUX)
    # ==========================================================
# le bloc 'generation_step'

    elif current_step == 'generation_step':
        # On vérifie quel type de document on doit générer
        flow_type = state.get('flow_type')
        
        try:
           
            if flow_type == 'lecon':
                generated_text, lang_code = generate_lesson_logic(
                    classe=collected_data.get('classe'),
                    matiere=collected_data.get('matiere'), 
                    module=collected_data.get('module'),
                    lecon=collected_data.get('lecon'),
                    syllabus=collected_data.get('syllabus'),
                    langue_contenu=collected_data.get('langue_contenu')
                )
                increment_stat('lessons_generated') 
                # integratuin:

            elif flow_type == 'integration':
                # On s'assure que 'matiere' et 'module' ont bien été collectés
                matiere_ou_module = collected_data.get('module') or collected_data.get('matiere')
                
                generated_text, lang_code = generate_integration_logic(
                    classe=collected_data.get('classe'),
                    # On passe la variable qu'on vient de vérifier
                    matiere=matiere_ou_module, 
                    liste_lecons=collected_data.get('liste_lecons'),
                    objectifs_lecons=collected_data.get('objectifs_lecons'),
                    langue_contenu=collected_data.get('langue_contenu')
                )
                increment_stat('integrations_generated')
                # --- evaluation ---

            elif flow_type == 'evaluation':
                matiere_ou_module = collected_data.get('module') or collected_data.get('matiere')
                generated_text, lang_code = generate_evaluation_logic(
                    classe=collected_data.get('classe'),
                    matiere=matiere_ou_module,
                    liste_lecons=collected_data.get('liste_lecons'),
                    duree=collected_data.get('duree'),
                    coeff=collected_data.get('coeff'),
                    langue_contenu=collected_data.get('langue_contenu'),
                    type_epreuve_key=collected_data.get('type_epreuve_key'),
                    # On ajoute la clé manquante
                    contexte_syllabus=collected_data.get('syllabus', "L'enseignant n'a pas fourni de contexte.")
                )
                increment_stat('evaluations_generated') 
            else:
                # Si le type de flux est inconnu, on renvoie une erreur
                raise ValueError("Type de flux inconnu ou non spécifié.")
                # On peut aussi ajouter un compteur pour le nombre total de documents générés
            increment_stat('total_documents')

            response_text = generated_text
            options = ["Recommencer", "Télécharger en PDF"] if lang == 'fr' else ["Restart", "Download PDF"]
            
        # NOUVELLE VERSION AMÉLIORÉE
        except Exception as e:
            logging.error(f"ERREUR LORS DE L'APPEL A CORE_LOGIC (flow: {flow_type}): {e}")
            
            # On crée un message plus convivial et on propose de recommencer
            if lang == 'fr':
                response_text = "Je suis sincèrement désolé, une erreur inattendue est survenue lors de la préparation de votre document. L'équipe technique a été informée. Souhaitez-vous recommencer depuis le début ?"
                options = ["Recommencer"]
            else:
                response_text = "I am sincerely sorry, an unexpected error occurred while preparing your document. The technical team has been notified. Would you like to start over?"
                options = ["Restart"]
            
            # Important : On réinitialise l'état pour que la conversation puisse repartir proprement.
            state['currentStep'] = 'select_option'
            state['collectedData'] = {}

#=============spinner===========================
    elif current_step == 'pending_generation':
        return handle_chat_recursive(state, "internal_trigger_generation")
#============================================================
    else:
        # Bloc final par défaut
        response_text = "Désolé, je suis perdu. Recommençons." if lang == 'fr' else "Sorry, I'm lost. Let's start over."
        options = ["Recommencer"] if lang == 'fr' else ["Restart"]
        state['currentStep'] = 'select_option'

    state['collectedData'] = collected_data
    return jsonify({'response': response_text, 'options': options, 'state': state})


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
    stats = get_all_stats()
    
    # On s'assure que les clés existent pour éviter les erreurs côté client
    # On initialise à 0 si la clé n'est pas encore dans la base de données
    response_data = {
        "lessons": stats.get('lessons_generated', 0),
        "integrations": stats.get('integrations_generated', 0),
        "evaluations": stats.get('evaluations_generated', 0),
        "total_documents": stats.get('total_documents', 0)
    }
    return jsonify(response_data)
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