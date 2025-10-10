# app.py - Version finale avec une machine à états robuste pour la fonctionnalité "Retour"

import logging
from flask import Flask, request, jsonify, send_file, Response, render_template,send_from_directory,after_this_request, url_for, redirect, session
import requests
from flask_cors import CORS
from core_logic import generate_lesson_logic, generate_integration_logic, generate_evaluation_logic, generate_digital_lesson_logic
import os
import uuid
import re
import shutil # Importé pour le nettoyage des dossiers
import secrets
from utils import create_pdf_with_pandoc
from functools import wraps
from database import increment_stat, get_all_stats, init_db , supabase 
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from authlib.integrations.flask_client import OAuth
from config import GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, APP_SECRET_KEY

# On importe les dictionnaires de menus de notre code original
from bot_data import CLASSES, MATIERES, SUBSYSTEME_FR, SUBSYSTEME_EN, LANGUES_CONTENU_COMPLET, LANGUES_CONTENU_SIMPLIFIE,  REGENERATE_OPTION_FR, REGENERATE_OPTION_EN

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
app = Flask(__name__)
CORS(app)

# initialisation de la bd
init_db()

# --- Configuration de l'Authentification ---
app.secret_key = APP_SECRET_KEY
login_manager = LoginManager()
login_manager.init_app(app)
oauth = OAuth(app)

# URL de découverte automatique de Google. C'est la seule URL dont nous avons besoin.
CONF_URL = 'https://accounts.google.com/.well-known/openid-configuration'

google = oauth.register(
    name='google',
    client_id=GOOGLE_CLIENT_ID,
    client_secret=GOOGLE_CLIENT_SECRET,
    
    # On ne fournit QUE l'URL des métadonnées.
    # Authlib découvrira toutes les autres URL (token, auth, userinfo, jwks) tout seul.
    # CELA CORRIGE LES ERREURS "invalid_claim" ET "mismatching_state".
    server_metadata_url=CONF_URL,
    
    # On définit juste le 'scope' que l'on demande à l'utilisateur.
    client_kwargs={
        'scope': 'openid email profile'
    }
)


# --- Modèle Utilisateur pour Flask-Login ---
class User(UserMixin):
    def __init__(self, user_data):
        self.id = user_data['id']
        self.email = user_data['email']
        self.full_name = user_data['full_name']
        self.plan_type = user_data.get('plan_type', 'free')
        self.generation_count = user_data.get('generation_count', 0)
        # On ajoute le rôle
        self.role = user_data.get('role', 'user')



@login_manager.user_loader
def load_user(user_id):
    # Charge l'utilisateur depuis la base de données
    response = supabase.table('users').select('*').eq('id', user_id).single().execute()
    if response.data:
        return User(response.data)
    return None


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

    


#========================================================================
# DÉCORATEUR DE VÉRIFICATION DE SESSION
# =======================================================================
def check_session(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # S'assure que l'utilisateur est bien connecté
        if not current_user.is_authenticated:
            return jsonify({'error': 'Authentication required'}), 401

        # Récupère le jeton de la session du navigateur
        session_token = session.get('session_token')
        
        # Récupère le jeton actuel depuis la base de données
        response = supabase.table('users').select('session_token').eq('id', current_user.id).single().execute()
        
        if not response.data or session_token != response.data.get('session_token'):
            # Si les jetons ne correspondent pas, on déconnecte l'utilisateur
            logout_user()
            return jsonify({'error': 'Session invalide. Vous avez été déconnecté car une nouvelle session a été ouverte ailleurs.'}), 401 # Unauthorized
        
        # Si tout est bon, on exécute la fonction demandée
        return f(*args, **kwargs)
    return decorated_function
# --- Application du décorateur ---
# On l'ajoute à la route du chat


# HANDLE CHAT FUNCTION :

@app.route('/api/chat', methods=['POST'])
@login_required
@check_session
def handle_chat():
    """
    Gère toute la logique de conversation du chatbot.
    Cette version est refactorisée pour un flux linéaire SANS récursion,
    ce qui résout les bugs de perte de session (erreur 401).
    """
    # --- PHASE 0 : INITIALISATION ---
    data = request.get_json()
    user_message = data.get('message')
    state = data.get('state', {})
    
    current_step = state.get('currentStep', 'start')
    lang = state.get('lang', 'fr')
    collected_data = state.get('collectedData', {})
    step_history = state.get('step_history', [])

    # --- PHASE 1 : GESTION DES ACTIONS SPÉCIALES (PRIORITAIRES) ---
    if user_message in [REGENERATE_OPTION_FR, REGENERATE_OPTION_EN]:
        current_step = 'generation_step'
    elif user_message == "internal_pdf_generation_failed":
        response_text = "Désolé, la conversion en PDF a échoué. Vous pouvez essayer de régénérer le contenu." if lang == 'fr' else "Sorry, the PDF conversion failed. You can try regenerating the content."
        options = [REGENERATE_OPTION_FR, "Recommencer"] if lang == 'fr' else [REGENERATE_OPTION_EN, "Restart"]
        return jsonify({'response': response_text, 'options': options, 'state': state})
    elif user_message in [BACK_OPTION_FR, BACK_OPTION_EN]:
        if not step_history:
            current_step = 'select_option'
            collected_data = {}
        else:
            current_step = step_history.pop()
            data_key_to_remove = DATA_KEY_FOR_STEP.get(current_step)
            if data_key_to_remove:
                if isinstance(data_key_to_remove, list):
                    for key in data_key_to_remove: collected_data.pop(key, None)
                else:
                    collected_data.pop(data_key_to_remove, None)
    elif user_message in ["Recommencer", "Restart", "internal_pdf_download_complete"]:
        current_step = 'select_option'
        collected_data = {}
        step_history = []
    # --- PHASE 2 : TRAITEMENT DU MESSAGE UTILISATEUR (FLUX NORMAL) ---
    else:
        if current_step == 'start':
            lang = 'fr' if 'Français' in user_message else 'en'
            current_step = 'select_option'
            collected_data = {}
            step_history = []
        else:
            step_definition = CONVERSATION_FLOW.get(current_step)
            if not step_definition:
                current_step = 'select_option'
                collected_data = {}
                step_history = []
            else:
                if current_step == 'select_option':
                    if 'digital' in user_message.lower(): collected_data['flow_type'] = 'digital'
                    elif 'leçon' in user_message.lower() or 'lesson' in user_message.lower(): collected_data['flow_type'] = 'lecon'
                    elif 'intégration' in user_message.lower() or 'integration' in user_message.lower(): collected_data['flow_type'] = 'integration'
                    elif 'évaluation' in user_message.lower() or 'assessment' in user_message.lower(): collected_data['flow_type'] = 'evaluation'
                else:
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
                next_step_func = step_definition.get('get_next_step')
                next_step = next_step_func(user_message) if next_step_func else None
                if not next_step:
                    response_text = "Je n'ai pas compris, veuillez réessayer." if lang == 'fr' else "I didn't understand, please try again."
                    options = step_definition['get_options'](lang, collected_data)
                    if step_history:
                        options.insert(0, BACK_OPTION_FR if lang == 'fr' else BACK_OPTION_EN)
                    state.update({'currentStep': current_step, 'collectedData': collected_data, 'step_history': step_history, 'lang': lang})
                    return jsonify({'response': response_text, 'options': options, 'is_text_input': step_definition.get('is_text_input', False), 'state': state})
                step_history.append(current_step)
                current_step = next_step

    # --- PHASE 3 : LE BLOC DE GÉNÉRATION (SI NÉCESSAIRE) ---
    if current_step == 'pending_generation':
        current_step = 'generation_step'

    if current_step == 'generation_step':
        is_admin = hasattr(current_user, 'role') and current_user.role == 'admin'
        if current_user.plan_type == 'free':
            GENERATION_LIMIT = 5 
            if current_user.generation_count >= GENERATION_LIMIT:
                return jsonify({
                'response': "Vous avez atteint votre limite de générations gratuites.",
                'options': ["Passer au plan Premium"],
                'state': state
            }), 403

        flow_type = collected_data.get('flow_type')
        try:
            if not flow_type:
                raise ValueError("flow_type est manquant dans collected_data. Impossible de générer.")
            
            generated_text = ""
            lesson_args = {k: v for k, v in collected_data.items() if k in ['classe', 'matiere', 'module', 'lecon', 'syllabus', 'langue_contenu']}
            integration_args = {k: v for k, v in collected_data.items() if k in ['classe', 'matiere', 'liste_lecons', 'objectifs_lecons', 'langue_contenu']}
            evaluation_args = {k: v for k, v in collected_data.items() if k in ['classe', 'matiere', 'liste_lecons', 'duree', 'coeff', 'langue_contenu', 'type_epreuve_key', 'contexte_syllabus']}
            digital_args = {k: v for k, v in collected_data.items() if k in ['classe', 'matiere', 'module', 'lecon', 'langue_contenu']}

            if flow_type == 'lecon':
                generated_text, _ = generate_lesson_logic(**lesson_args)
                if not is_admin and current_user.plan_type == 'free':
                    new_count = current_user.generation_count + 1
                    supabase.table('users').update({'generation_count': new_count}).eq('id', current_user.id).execute()
                increment_stat('lessons_generated')
            elif flow_type == 'digital':
                generated_text, _ = generate_digital_lesson_logic(**digital_args)
                if not is_admin and current_user.plan_type == 'free':
                    new_count = current_user.generation_count + 1
                    supabase.table('users').update({'generation_count': new_count}).eq('id', current_user.id).execute()
                increment_stat('digital_lessons_generated')
            elif flow_type == 'integration':
                 generated_text, _ = generate_integration_logic(**integration_args)
                 if not is_admin and current_user.plan_type == 'free':
                    new_count = current_user.generation_count + 1
                    supabase.table('users').update({'generation_count': new_count}).eq('id', current_user.id).execute()
                 increment_stat('integrations_generated')
            elif flow_type == 'evaluation':
                user_choice = collected_data.get('type_epreuve', '')
                collected_data['type_epreuve_key'] = "junior_mcq" if 'QCM' in user_choice else "junior_resources_competencies"
                collected_data['contexte_syllabus'] = collected_data.get('syllabus', "Non fourni.")
                evaluation_args['type_epreuve_key'] = collected_data['type_epreuve_key']
                evaluation_args['contexte_syllabus'] = collected_data['contexte_syllabus']
                args_to_send = {k: v for k, v in collected_data.items() if k in evaluation_args}
                generated_text, _ = generate_evaluation_logic(**args_to_send)
                if not is_admin and current_user.plan_type == 'free':
                    new_count = current_user.generation_count + 1
                    supabase.table('users').update({'generation_count': new_count}).eq('id', current_user.id).execute()
                increment_stat('evaluations_generated')
            
            increment_stat('total_documents')
            response_text = generated_text
            
            options_fr = ["Recommencer", REGENERATE_OPTION_FR, "Télécharger en PDF"]
            options_en = ["Restart", REGENERATE_OPTION_EN, "Download PDF"]
            if flow_type == 'digital':
                 options_fr = ["Recommencer", REGENERATE_OPTION_FR, "Télécharger en Présentation (PDF)"]
                 options_en = ["Restart", REGENERATE_OPTION_EN, "Download as Presentation (PDF)"]
            
            options = options_fr if lang == 'fr' else options_en
            
            state['generated_text'] = generated_text
            state['step_history'] = []

            title_prefix = collected_data.get('flow_type', 'Document')
            title_main = collected_data.get('lecon') or collected_data.get('liste_lecons') or "Sans titre"
            history_title = f"{title_prefix.capitalize()} - {title_main[:30]}"
            
            supabase.table('generations').insert({
                'user_id': current_user.id,
                'title': history_title,
                'flow_type': flow_type,
                'content': generated_text
            }).execute()
            
        except Exception as e:
            logging.error(f"ERREUR LORS DE LA GÉNÉRATION (flow: {flow_type}): {e}")
            response_text = "Désolé, une erreur est survenue." if lang == 'fr' else "Sorry, an error occurred."
            options = ["Recommencer"] if lang == 'fr' else ["Restart"]
            state = {'lang': lang, 'currentStep': 'select_option', 'collectedData': {}, 'step_history': []}
        
        return jsonify({'response': response_text, 'options': options, 'state': state})

    # --- PHASE 4 : AFFICHAGE DE LA QUESTION POUR L'ÉTAPE EN COURS ---
    step_definition = CONVERSATION_FLOW.get(current_step)
    if not step_definition:
        current_step = 'select_option'
        collected_data = {}
        step_history = []
        step_definition = CONVERSATION_FLOW['select_option']

    response_text = step_definition['question_fr'] if lang == 'fr' else step_definition['question_en']
    options = list(step_definition['get_options'](lang, collected_data))
    is_text_input = step_definition.get('is_text_input', False)
    
    if step_history:
        options.insert(0, BACK_OPTION_FR if lang == 'fr' else BACK_OPTION_EN)

    state.update({
        'currentStep': current_step,
        'collectedData': collected_data,
        'step_history': step_history,
        'lang': lang
    })
    
    return jsonify({'response': response_text, 'options': options, 'is_text_input': is_text_input, 'state': state})
    
    

    # =======================================================================
    # --- PHASE 4 : GESTION DU FLUX DE CONVERSATION NORMAL ---
    # Si aucune des conditions ci-dessus n'est remplie, on suit la carte de conversation.
    # =======================================================================

     # EXPLICATION: Ce bloc est le point de sortie final pour toutes les étapes non terminales.
    step_definition = CONVERSATION_FLOW.get(current_step)
    if not step_definition:
        # Sécurité : si l'étape est toujours inconnue, on recommence proprement.
        current_step = 'select_option'
        collected_data = {}
        step_history = []
        step_definition = CONVERSATION_FLOW['select_option']

    response_text = step_definition['question_fr'] if lang == 'fr' else step_definition['question_en']
    options = list(step_definition['get_options'](lang, collected_data))
    is_text_input = step_definition.get('is_text_input', False)
    
    # On ajoute l'option "Retour" seulement s'il y a un historique.
    if step_history:
        options.insert(0, BACK_OPTION_FR if lang == 'fr' else BACK_OPTION_EN)

    # Mise à jour finale de l'état avant de renvoyer la réponse.
    state.update({
        'currentStep': current_step,
        'collectedData': collected_data,
        'step_history': step_history,
        'lang': lang
    })
    
    return jsonify({'response': response_text, 'options': options, 'is_text_input': is_text_input, 'state': state})
        
        # C. On met à jour les variables pour la prochaine étape.
    step_history.append(current_step)
    current_step = next_step  # EXPLICATION : On met à jour la variable locale 'current_step'.
        
        # EXPLICATION : La fonction va maintenant continuer son exécution et utiliser
        # la nouvelle valeur de 'current_step' pour afficher la question suivante.
        # Il n'y a plus de "return" ni d'appel récursif ici.

    # =======================================================================
    # PHASE 5 : AFFICHAGE DE LA QUESTION POUR L'ÉTAPE ACTUELLE
    # =======================================================================
    # EXPLICATION : Ce bloc s'exécute maintenant à chaque fois, que ce soit pour
    # la première question ou pour les suivantes.
    
    step_definition = CONVERSATION_FLOW.get(current_step)
    if not step_definition: # Sécurité si l'étape est inconnue
        state = {'lang': lang, 'currentStep': 'select_option', 'collectedData': {}, 'step_history': []}
        step_definition = CONVERSATION_FLOW['select_option']

    response_text = step_definition['question_fr'] if lang == 'fr' else step_definition['question_en']
    options = list(step_definition['get_options'](lang, collected_data))
    is_text_input = step_definition.get('is_text_input', False)
    if step_history:
        options.insert(0, BACK_OPTION_FR if lang == 'fr' else BACK_OPTION_EN)
    
    # On met à jour l'état final avant de l'envoyer au client.
    state['currentStep'] = current_step
    state['collectedData'] = collected_data
    state['step_history'] = step_history

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
    
    # --- DÉBUT DE LA CORRECTION DE SÉCURITÉ ---
    # EXPLICATION : On récupère la langue de manière sécurisée, avec une valeur
    # par défaut ('fr') si la clé 'lang' n'est pas présente dans l'état.
    lang = state.get('lang', 'fr') 
    if lang is None: # Double sécurité si 'lang' est explicitement envoyé comme 'null'.
        lang = 'fr'
    # --- FIN DE LA CORRECTION DE SÉCURITÉ ---
    
    collected_data = state.get('collectedData', {})
    # On s'assure de récupérer le 'flow_type' depuis 'collectedData' où il est stocké.
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
        # EXPLICATION : On utilise la variable 'lang' maintenant sécurisée pour créer lang_code.
        lang_code = lang.lower()
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
        # EXPLICATION : On log l'erreur spécifique pour faciliter le débogage futur.
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
# ROUTE POUR L'HISTORIQUE
# =======================================================================
@app.route('/api/history', methods=['GET'])
@login_required
@check_session
def get_history():
    """Récupère la liste des générations passées pour l'utilisateur connecté."""
    try:
        response = supabase.table('generations').select('id, title, created_at').eq('user_id', current_user.id).order('created_at', desc=True).limit(50).execute()
        return jsonify(response.data), 200
    except Exception as e:
        logging.error(f"Erreur lors de la récupération de l'historique: {e}")
        return jsonify({'error': 'Impossible de charger l''historique'}), 500

# =======================================================================
# ROUTE POUR RÉCUPÉRER UNE GÉNÉRATION SPÉCIFIQUE
# =======================================================================
@app.route('/api/history/<generation_id>', methods=['GET'])
@login_required
@check_session
def get_generation(generation_id):
    """Récupère le contenu d'une génération spécifique."""
    try:
        response = supabase.table('generations').select('content, flow_type').eq('id', generation_id).eq('user_id', current_user.id).single().execute()
        if response.data:
            return jsonify(response.data), 200
        else:
            return jsonify({'error': 'Génération non trouvée ou non autorisée'}), 404
    except Exception as e:
        logging.error(f"Erreur lors de la récupération d'une génération: {e}")
        return jsonify({'error': 'Erreur interne'}), 500

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
# ROUTES FOR AUTHENTICATION
# =======================================================================

@app.route('/login')
def login():
    redirect_uri = url_for('authorize', _external=True)
    return google.authorize_redirect(redirect_uri)


# =======================================================================
# ROUTE DE CALLBACK /auth/callback (VERSION FINALE CORRIGÉE POUR SUPABASE)
# =======================================================================
@app.route('/auth/callback')
def authorize():
    try:
        token = google.authorize_access_token()
        user_info = token.get('userinfo')
        if not user_info:
             user_info = google.parse_id_token(token)

        google_id = user_info['sub']
         
        # Étape 3 (Modifiée) : On cherche l'utilisateur sans exiger un résultat unique.
        # On utilise .execute() directement, qui retourne une liste.
        response = supabase.table('users').select('*').eq('google_id', google_id).execute()
        
        # On vérifie si la liste de données est vide.
        if not response.data:
            # L'utilisateur n'existe pas, on le crée.
            logging.info(f"Nouvel utilisateur détecté : {user_info.get('email')}. Création du compte...")
            insert_response = supabase.table('users').insert({
                'google_id': google_id,
                'email': user_info.get('email'),
                'full_name': user_info.get('name')
            }).execute()
            
            if not insert_response.data:
                raise Exception("La création de l'utilisateur a échoué dans la base de données.")
            
            user_data = insert_response.data[0]
        else:
            # L'utilisateur existe déjà, on prend la première (et seule) ligne.
            logging.info(f"Utilisateur existant détecté : {user_info.get('email')}.")
            user_data = response.data[0]
            
        # --- DÉBUT DE LA NOUVELLE LOGIQUE DE SESSION UNIQUE ---

        # 1. Générer un nouveau jeton de session unique
        new_session_token = str(uuid.uuid4())
        
        # 2. Mettre à jour ce jeton dans la base de données pour cet utilisateur
        supabase.table('users').update({
            'session_token': new_session_token
        }).eq('id', user_data['id']).execute()
        
        # 3. Sauvegarder ce même jeton dans la session du navigateur
        session['session_token'] = new_session_token

        # --- FIN DE LA NOUVELLE LOGIQUE ---
            
        user = User(user_data)
        login_user(user)
        
        return redirect(url_for('chat_page'))

    except Exception as e:
        logging.error(f"Erreur DÉFINITIVE lors de l'autorisation OAuth: {e}")
        return "Une erreur critique est survenue lors de la connexion. Veuillez contacter le support.", 500


#

# =======================================================================
# ROUTES FOR logout
# =======================================================================

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))


# =======================================================================
# ROUTE POUR METTRE À JOUR UNE GÉNÉRATION
# =======================================================================
@app.route('/api/history/update', methods=['POST'])
@login_required
@check_session
def update_generation():
    """Met à jour le contenu d'une génération existante."""
    try:
        data = request.get_json()
        generation_id = data.get('generation_id')
        content = data.get('content')
        flow_type = data.get('flow_type')
        
        if not generation_id or not content:
            return jsonify({'error': 'Données manquantes'}), 400
        
        # Vérifier que l'utilisateur possède cette génération
        response = supabase.table('generations').select('id').eq('id', generation_id).eq('user_id', current_user.id).single().execute()
        
        if not response.data:
            return jsonify({'error': 'Génération non trouvée ou non autorisée'}), 404
        
        # Mettre à jour la génération
        update_response = supabase.table('generations').update({
            'content': content,
            'flow_type': flow_type,
            'updated_at': 'now()'
        }).eq('id', generation_id).execute()
        
        if update_response.data:
            return jsonify({'success': True, 'message': 'Contenu mis à jour avec succès'}), 200
        else:
            return jsonify({'error': 'Erreur lors de la mise à jour'}), 500
            
    except Exception as e:
        logging.error(f"Erreur lors de la mise à jour de la génération: {e}")
        return jsonify({'error': 'Erreur interne'}), 500


# =======================================================================
# ROUTES FOR STATIC PAGES
# =======================================================================

# --- Modification des Routes Existantes ---
@app.route('/')
def index():
    """Rend la page d'accueil (Landing Page)."""
    # On passe 'current_user' au template. S'il n'est pas connecté,
    # current_user.is_authenticated sera False.
    return render_template('landing.html', user=current_user)

@app.route('/app')
@login_required
def chat_page():
    """Rend la page principale de l'application (le chatbot)."""
    return render_template('index.html', user=current_user)

@app.route('/about')
def about_page():
    """Rend la page 'À Propos'."""
    return render_template('about.html', user=current_user)

@app.route('/donate')
def donate_page():
    """Rend la page 'Soutenir'."""
    return render_template('donate.html', user=current_user)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)