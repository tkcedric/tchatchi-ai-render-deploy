# bot_data.py
# Ce fichier contient toutes les données statiques (listes, dictionnaires)
# utilisées pour générer les options et les menus dans la conversation.

# =======================================================================
# OPTIONS "AUTRE"
# =======================================================================
AUTRE_OPTION_FR = "✍️ Autre (préciser)"
AUTRE_OPTION_EN = "✍️ Other (specify)"

# =======================================================================
# NOUVELLES OPTIONS DE RÉGÉNÉRATION
# =======================================================================
REGENERATE_OPTION_FR = " régénérer"
REGENERATE_OPTION_EN = "Regenerate"

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

# Fichier : bot_data.py

# =======================================================================
# MATIÈRES (Structurées par langue et sous-système) - VERSION MISE À JOUR ET TRIÉE
# =======================================================================
MATIERES = {
    'fr': {
        'esg': sorted(['Allemand', 'Anglais', 'Chimie', 'Chinois', 'ECM', 'Espagnol', 'Français', 'Géographie', 'Histoire', 'Informatique', 'Italien', 'Mathématiques', 'Orientation', 'Philosophie', 'Physique', 'SVT']),
        'est': sorted([
            # Matières générales
            'Mathématiques', 'Physique', 'Chimie', 'Français', 'Histoire', 'Géographie', 'Philosophie', 'Anglais', 'ECM', 'Allemand', 'Informatique',
            # Spécialités techniques
            'Accueil et Animation Touristique', 'Action et Communication Administrative', 'Action et Communication Commerciale',
            'Affuteur Scieur', 'Agence de Voyage', 'Aide Chimique Biologiste', 'Aide Chimique Industrielle', 'Ajustage',
            'Bijouterie', 'Boulangerie Patisserie', 'Bureau d\'Études', 'Carrelage', 'Carrosserie Peinture Automobile',
            'Céramique', 'Chaudronnerie', 'Chaudronnerie et Tuyauterie Industrielle', 'Chimie Industrielle',
            'Comptabilité de Gestion', 'Construction et Ouvrage Métallique', 'Construction Mécanique', 'Couture sur Mesure',
            'Cuisine', 'Décoration', 'Dessin en Bâtiment', 'Economie Sociale et Familiale', 'Electricité Automobile',
            'Electricité d\'Équipement', 'Electricité Bâtiment', 'Electro Mécanique', 'Electronique',
            'Employé des Services Comptables', 'Employé des Services Financiers', 'Esthétique Coiffure',
            'Exploitation Forestière', 'Fabrication Mécanique', 'Fiscalité et Informatique de Gestion',
            'Froid et Climatisation', 'Génie Chimique Bioprocédés et Pétrochimie', 'Génie Chimique Cosmétique et Pharmacie',
            'Génie Chimique Mines et Pétroles', 'Génie Civil Bâtiment', 'Géomètre Topographe', 'Hébergement', 'Hôtellerie',
            'Industrie d\'Habillement', 'Industrie du Bois', 'Installation Sanitaire', 'Maçonnerie',
            'Maintenance Audiovisuelle', 'Maintenance des Equipements Agricoles', 'Maintenance des Equipements Hospitaliers',
            'Maintenance des Systèmes Electroniques', 'Maintenance Electromécanique', 'Maintenance Véhicules de Tourisme',
            'Maintenance Véhicules Poids Lourds', 'Menuiserie', 'Menuiserie Ebénisterie', 'Métaux en Feuilles',
            'Mécanique Automobile de Réparation', 'Mécanique Automobile Electricité', 'Mécanique Automobile Injection',
            'Mécanique de Fabrication', 'Peinture', 'Production Animale', 'Production Végétale', 'Restauration',
            'Réparation Carrosserie Automobile', 'Science et Technique Biologique', 'Science et Technologie de la Santé',
            'Sciences Economiques et Sociales', 'Sculpture', 'Secrétariat et Bureautique', 'Secrétariat Médical',
            'Service Hôtelier', 'Technique et Mathématique', 'Techniques et Gestion Forestières', 'Tourisme',
            'Transformation des Produits', 'Transformation et Conservation des Produits Agropastoraux', 'Travaux Publics', 'Vente'
        ])
    },
    'en': {
        'esg': sorted(['Additional Maths', 'Biology', 'Chemistry', 'Computer Science', 'Economics', 'English', 'Food and Nutrition', 'French', 'Further Maths', 'Geography', 'Geology', 'History', 'ICT', 'Logic', 'Mathematics', 'Orientation', 'Physics']),
        'est': sorted([
            # General subjects
            'Mathematics', 'Physics', 'Chemistry', 'French', 'History', 'Geography', 'Philosophy', 'English', 'Citizenship Education', 'German', 'Computer Science', 'ICT',
            # Technical specialties
            'Accommodation', 'Accounting Services Employee', 'Administrative Communication and Action',
            'Aesthetics and Hairdressing', 'Agricultural Equipment Maintenance', 'Animal Production',
            'Audiovisual Maintenance', 'Automobile Body Painting', 'Automobile Body Repair',
            'Automobile Electrical Mechanics', 'Automobile Electricity', 'Automobile Injection Mechanics',
            'Automobile Repair Mechanics', 'Bakery and Pastry', 'Biological Science and Technique', 'Boilermaking',
            'Boilermaking and Industrial Piping', 'Building Design', 'Building Electricity', 'Cabinet Making', 'Carpentry',
            'Catering', 'Ceramics', 'Chemical Biology Assistant', 'Chemical Engineering - Bioprocesses and Petrochemicals',
            'Chemical Engineering - Cosmetics and Pharmacy', 'Chemical Engineering - Mines and Petroleum',
            'Civil Engineering - Building', 'Clothing Industry', 'Commercial Communication and Action',
            'Cuisine', 'Custom Sewing', 'Decoration', 'Design Office', 'Economic and Social Sciences',
            'Electro-Mechanics', 'Electromechanical Maintenance', 'Electronic Systems Maintenance', 'Electronics',
            'Equipment Electricity', 'Financial Services Employee', 'Fitting', 'Forestry', 'Health Science and Technology',
            'Heavy Goods Vehicle Maintenance', 'Hotel Management', 'Hotel Services', 'Hospital Equipment Maintenance',
            'Industrial Chemical Assistant', 'Industrial Chemistry', 'Jewelry', 'Management Accounting',
            'Manufacturing Mechanics', 'Masonry', 'Mechanical Construction', 'Mechanical Manufacturing', 'Medical Secretariat',
            'Metal Construction and Works', 'Painting', 'Plant Production', 'Product Transformation',
            'Processing and Conservation of Agropastoral Products', 'Public Works',
            'Refrigeration and Air Conditioning', 'Sales', 'Sanitary Installation', 'Saw Sharpener',
            'Secretarial and Office Skills', 'Sheet Metal Work', 'Social and Family Economy', 'Sculpture',
            'Surveyor Topographer', 'Taxation and Management Information Systems', 'Technique and Mathematics',
            'Tiling', 'Tourism', 'Tourism Reception and Animation', 'Tourism Vehicle Maintenance', 'Travel Agency', 'Wood Industry'
        ])
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