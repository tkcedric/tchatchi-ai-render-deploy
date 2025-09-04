# utils.py - Avec la fonction complète de Colab

import logging
import re
import pypandoc
import datetime
import locale
import os
from config import TITLES # Assurez-vous que TITLES est bien dans config.py

logging.basicConfig(level=logging.INFO, format='%(name)s - %(levelname)s - %(message)s')

def create_pdf_with_pandoc(text, filename="document.pdf", lang_contenu_code='fr', doc_type='lecon'):
    """
    Crée un PDF en utilisant les titres appropriés en fonction du type de document (lecon, integration, evaluation).
    """
    try:
        logging.info(f"Création du PDF (v13 - Titres dynamiques) : {filename} (type: {doc_type})")

        # 1. Séparation du texte et des données bilingues (méthode robuste) - NE CHANGE PAS
        parts = re.split(r'<bilingual_data>.*?</bilingual_data>', text, flags=re.IGNORECASE | re.DOTALL)
        main_markdown_raw = parts[0]
        bilingual_data_match = re.search(r'<bilingual_data>(.*?)</bilingual_data>', text, flags=re.IGNORECASE | re.DOTALL)
        bilingual_data_raw = bilingual_data_match.group(1) if bilingual_data_match else ""

        # 2. Nettoyage du texte principal - NE CHANGE PAS
        main_markdown_final = re.sub(r'<!--.*?-->', '', main_markdown_raw, flags=re.DOTALL).strip().replace('bilingual_data', '')

        # 3. Construction du tableau Markdown - NE CHANGE PAS
        markdown_table = ""
        if bilingual_data_raw:
            # ... (votre logique existante pour construire le tableau est correcte)
            bilingual_content = re.sub(r'<!--.*?-->', '', bilingual_data_raw, flags=re.DOTALL).strip()
            lines = [line.strip() for line in bilingual_content.split('\n') if line.strip() and ';' in line]
            if lines:
                table_title = TITLES.get(lang_contenu_code, TITLES['fr'])['JEU_BILINGUE']
                markdown_table += f"\n\n**{table_title}**\n\n"
                lang_map_display = {'fr': 'Français', 'en': 'English', 'de': 'Deutsch', 'es': 'Español', 'it': 'Italiano', 'zh': '中文', 'ar': 'العربية'}
                langue_source_nom = lang_map_display.get(lang_contenu_code, lang_contenu_code.capitalize())
                if lang_contenu_code == 'fr':
                    headers = ['N°', langue_source_nom, 'English']
                else:
                    headers = ['N°', langue_source_nom, 'Français']
                markdown_table += f"| {headers[0]} | {headers[1]} | {headers[2]} |\n"
                markdown_table += "|:---:|:---|:---|\n"
                for i, line in enumerate(lines):
                    parts = [p.strip() for p in line.split(';')]
                    if len(parts) == 2:
                        markdown_table += f"| {i+1} | {parts[0]} | {parts[1]} |\n"

        # 4. Assemblage du document final
        # *** MODIFICATION IMPORTANTE ICI ***
        # On remplace le séparateur brut par le titre du corrigé traduit, uniquement si c'est une évaluation
        selected_titles_for_corrige = TITLES.get(lang_contenu_code, TITLES['fr'])
        if doc_type == 'evaluation':
            corrige_title = selected_titles_for_corrige.get('EVAL_CORRIGE_TITRE', 'CORRIGÉ DÉTAILLÉ')
            # On cherche le séparateur de manière insensible à la casse pour plus de robustesse
            final_markdown_doc = re.sub(r'---\s*CORRIGE\s*---', f"\n\n---\n\n**{corrige_title}**\n\n---", text, flags=re.IGNORECASE)
            # On s'assure que le tableau bilingue n'est pas ajouté à une évaluation
        else:
            final_markdown_doc = main_markdown_final + markdown_table


        # 5. Création de l'en-tête YAML (cette partie est correcte)
        # *** MODIFICATION IMPORTANTE ICI ***
        selected_pdf_titles = TITLES.get(lang_contenu_code, TITLES['fr'])
        try:
            locale_str = f'{lang_contenu_code}_{lang_contenu_code.upper()}.UTF-8' if lang_contenu_code not in ['zh', 'ar'] else 'en_US.UTF-8'
            locale.setlocale(locale.LC_TIME, locale_str)
        except locale.Error:
            locale.setlocale(locale.LC_TIME, '')
        formatted_date = datetime.date.today().strftime('%d %B %Y')

        # On choisit le titre et l'auteur du document en fonction du type

        if doc_type == 'evaluation':
            pdf_title = selected_pdf_titles.get('EVAL_PDF_TITLE', 'Assessment')
            pdf_author = selected_pdf_titles.get('EVAL_PDF_AUTHOR', 'TCHATCHI AI Pedagogical Assistant')
        elif doc_type == 'integration':
            pdf_title = selected_pdf_titles.get('INT_PDF_TITLE', 'Integration Activity')
            pdf_author = selected_pdf_titles.get('INT_PDF_AUTHOR', 'TCHATCHI AI Pedagogical Assistant')
        else: # 'lecon'
            pdf_title = selected_pdf_titles.get('PDF_TITLE', 'Lesson Plan')
            pdf_author = selected_pdf_titles.get('PDF_AUTHOR', 'TCHATCHI AI Pedagogical Assistant')

        yaml_header = f"""
---
title: "{pdf_title}"
author: "{pdf_author}"
date: "{formatted_date}"
lang: "{lang_contenu_code}"
geometry: "margin=1in"
mainfont: "Liberation Serif"
header-includes:
- \\usepackage{{amsmath}}
- \\usepackage{{amssymb}}
- \\usepackage{{unicode-math}}
- \\setmainfont{{Liberation Serif}}
- \\setmathfont{{latinmodern-math.otf}}
---
"""
        # 6. Conversion avec Pandoc
        document_source = yaml_header + final_markdown_doc
        pypandoc.convert_text(document_source, 'pdf', format='markdown',
                              outputfile=filename,
                              extra_args=['--pdf-engine=xelatex'])

        logging.info(f"PDF '{filename}' créé avec succès.")
        return True

    except Exception as e:
        logging.error(f"Erreur DÉFINITIVE lors de la création du PDF avec Pandoc: {e}")
        if 'document_source' in locals():
            logging.error(f"Source Markdown problématique (extrait) : {document_source[:1000]}")
        return False