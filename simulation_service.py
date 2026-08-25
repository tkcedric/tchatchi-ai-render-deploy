"""
simulation_service.py

Base de simulations interactives VÉRIFIÉES (pas générées par l'IA) pour
enrichir les leçons digitalisées avec de vrais liens PhET/GeoGebra.

Pourquoi une base statique plutôt que de laisser l'IA proposer un lien ?
Parce que l'IA (Gemini/GPT) n'a pas de capacité de navigation web ici — elle
invente des URLs plausibles mais potentiellement fausses ou cassées. Cette
base ne contient que des liens vérifiés manuellement.

Pour ajouter une nouvelle simulation : ajoute une entrée dans SIMULATIONS_DB
avec des mots-clés représentatifs du sujet, dans la langue française.
"""

SIMULATIONS_DB = [
    # --- PHYSIQUE ---
    {"mots_cles": ["force", "mouvement", "newton", "vitesse", "accélération"],
     "nom": "Forces and Motion", "url": "https://phet.colorado.edu/en/simulations/forces-and-motion",
     "description": "Simulation interactive pour explorer les forces, le mouvement et les lois de Newton."},
    {"mots_cles": ["pendule", "oscillation", "période"],
     "nom": "Pendulum Lab", "url": "https://phet.colorado.edu/en/simulations/pendulum-lab",
     "description": "Étudier les facteurs qui influencent la période d'un pendule (longueur, masse, gravité)."},
    {"mots_cles": ["projectile", "trajectoire", "balistique"],
     "nom": "Projectile Motion", "url": "https://phet.colorado.edu/en/simulations/projectile-motion",
     "description": "Simuler des tirs de projectiles et observer l'effet de l'angle, la vitesse et la masse."},
    {"mots_cles": ["circuit", "électrique", "courant", "résistance", "ohm"],
     "nom": "Circuit Construction Kit", "url": "https://phet.colorado.edu/en/simulations/circuit-construction-kit-dc",
     "description": "Construire des circuits électriques simples et observer le courant en temps réel."},
    {"mots_cles": ["loi d'ohm", "tension", "intensité"],
     "nom": "Ohm's Law", "url": "https://phet.colorado.edu/en/simulations/ohms-law",
     "description": "Visualiser la relation entre tension, résistance et intensité du courant."},
    {"mots_cles": ["onde", "corde", "fréquence", "amplitude"],
     "nom": "Wave on a String", "url": "https://phet.colorado.edu/en/simulations/wave-on-a-string",
     "description": "Observer la propagation d'ondes sur une corde selon fréquence et amplitude."},
    {"mots_cles": ["énergie", "transformation", "conservation"],
     "nom": "Energy Forms and Changes", "url": "https://phet.colorado.edu/en/simulations/energy-forms-and-changes",
     "description": "Explorer les transformations d'énergie (thermique, mécanique, électrique)."},
    {"mots_cles": ["gravité", "orbite", "système solaire", "satellite"],
     "nom": "Gravity and Orbits", "url": "https://phet.colorado.edu/en/simulations/gravity-and-orbits",
     "description": "Simuler les orbites planétaires et l'effet de la gravité."},
    {"mots_cles": ["densité", "masse volumique", "flottaison"],
     "nom": "Density", "url": "https://phet.colorado.edu/en/simulations/density",
     "description": "Comprendre la densité en manipulant masse et volume de différents objets."},

    # --- CHIMIE ---
    {"mots_cles": ["équation chimique", "équilibrer", "réaction chimique"],
     "nom": "Balancing Chemical Equations", "url": "https://phet.colorado.edu/en/simulations/balancing-chemical-equations",
     "description": "S'entraîner à équilibrer des équations chimiques de façon interactive."},
    {"mots_cles": ["atome", "structure atomique", "proton", "électron", "neutron"],
     "nom": "Build an Atom", "url": "https://phet.colorado.edu/en/simulations/build-an-atom",
     "description": "Construire un atome et observer son numéro atomique, sa masse et sa charge."},
    {"mots_cles": ["ph", "acide", "base", "acidité"],
     "nom": "pH Scale", "url": "https://phet.colorado.edu/en/simulations/ph-scale",
     "description": "Tester le pH de différentes substances et comprendre l'échelle acide-base."},
    {"mots_cles": ["état de la matière", "solide", "liquide", "gaz", "changement d'état"],
     "nom": "States of Matter", "url": "https://phet.colorado.edu/en/simulations/states-of-matter",
     "description": "Observer le comportement des molécules dans les états solide, liquide et gazeux."},

    # --- MATHÉMATIQUES (GeoGebra, outils officiels génériques) ---
    {"mots_cles": ["géométrie", "figure géométrique", "construction", "angle", "triangle", "cercle", "polygone"],
     "nom": "GeoGebra Géométrie", "url": "https://www.geogebra.org/geometry",
     "description": "Outil de construction géométrique interactif pour illustrer et manipuler des figures."},
    {"mots_cles": ["fonction", "courbe", "graphique", "équation", "représentation graphique"],
     "nom": "GeoGebra Graphique", "url": "https://www.geogebra.org/graphing",
     "description": "Tracer et manipuler des fonctions et courbes de façon interactive."},
    {"mots_cles": ["géométrie dans l'espace", "solide", "volume", "3d"],
     "nom": "GeoGebra 3D", "url": "https://www.geogebra.org/3d",
     "description": "Explorer des figures géométriques en 3 dimensions."},
    {"mots_cles": ["probabilité", "statistique", "distribution"],
     "nom": "GeoGebra Probabilité", "url": "https://www.geogebra.org/probability",
     "description": "Visualiser des distributions de probabilité et des calculs statistiques."},
]


def normaliser(texte):
    """Minuscule + retire les accents courants, pour une comparaison plus robuste."""
    if not texte:
        return ""
    remplacements = str.maketrans("éèêëàâäùûüôöîï", "eeeeaaauuuooii")
    return texte.lower().translate(remplacements)


def trouver_simulation(matiere, lecon, module=""):
    """
    Cherche dans SIMULATIONS_DB une entrée dont un mot-clé apparaît dans le
    sujet de la leçon (matière + module + titre de la leçon combinés).
    Renvoie le premier résultat trouvé, ou None si rien de pertinent.
    """
    texte_recherche = normaliser(f"{matiere} {module} {lecon}")

    for entree in SIMULATIONS_DB:
        for mot_cle in entree["mots_cles"]:
            if normaliser(mot_cle) in texte_recherche:
                return entree
    return None