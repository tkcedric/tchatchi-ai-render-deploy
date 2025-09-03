# bot_data.py
# Ce fichier contient toutes les données statiques (listes, dictionnaires)
# utilisées pour générer les options et les menus dans la conversation.

# =======================================================================
# OPTIONS "AUTRE"
# =======================================================================
AUTRE_OPTION_FR = "✍️ Autre (préciser)"
AUTRE_OPTION_EN = "✍️ Other (specify)"

# =======================================================================
# SOUS-SYSTÈMES
# =======================================================================
SUBSYSTEME_FR = ['Enseignement Secondaire Général (ESG)', 'Enseignement Secondaire Technique (EST)']
SUBSYSTEME_EN = ['General Education', 'Technical Education']

# =======================================================================
# CLASSES (Structurées par langue et sous-système)
# =======================================================================
CLASSES = {
    'fr': {
        'esg': ['6ème', '5ème', '4ème', '3ème', 'Seconde', 'Première', 'Terminale'],
        'est': ['1ère Année CAP', '2ème Année CAP', 'Seconde Technique', 'Première Technique', 'Terminale Technique']
    },
    'en': {
        'esg': ['Form 1', 'Form 2', 'Form 3', 'Form 4', 'Form 5', 'Lower Sixth', 'Upper Sixth'],
        'est': ['Year 1 (Technical)', 'Year 2 (Technical)', 'Form 4 (Technical)', 'Form 5 (Technical)', 'Upper Sixth (Technical)']
    }
}

# =======================================================================
# MATIÈRES (Structurées par langue et sous-système)
# =======================================================================
MATIERES = {
    'fr': {
        'esg': ['Mathématiques', 'Physique', 'Chimie', 'SVT', 'Français', 'Histoire', 'Géographie', 'Philosophie', 'Anglais', 'ECM', 'Espagnol', 'Italien', 'Chinois', 'Allemand','Informatique' ],
        'est': ['Dessin Technique', 'Mécanique', 'Électrotechnique', 'Comptabilité']
    },
    'en': {
        'esg': ['Mathematics', 'Physics', 'Chemistry', 'Biology', 'History', 'Geography', 'Economics', 'Further Maths', 'Computer Science', 'English', 'French', 'ICT', 'Additional Maths', 'Logic', 'Geology'],
        'est': ['Technical Drawing', 'Mechanics', 'Electrotechnics', 'Accounting']
    }
}

# =======================================================================
# LANGUES DU CONTENU
# =======================================================================
LANGUES_CONTENU = ['Français', 'English', 'Deutsch', 'Español', 'Italiano', '中文 (Chinois)', 'العربية (Arabe)']


# =======================================================================
# LANGUES DU CONTENU (VERSION WEB)
# =======================================================================
# On crée deux listes pour gérer le cas demandé.

LANGUES_CONTENU_COMPLET = ['Français', 'English', 'Deutsch', 'Español', 'Italiano', '中文 (Chinois)', 'العربية (Arabe)']
LANGUES_CONTENU_SIMPLIFIE = ['English', 'Français']