# utils.py - Avec la fonction complète de Colab

import logging
import re
import pypandoc
import datetime
import locale
import os
from config import TITLES # Assurez-vous que TITLES est bien dans config.py

logging.basicConfig(level=logging.INFO, format='%(name)s - %(levelname)s - %(message)s')

def create_pdf_with_pandoc(text, filename="document.pdf", lang_contenu_code='fr', doc_type='lecon', output_format='pdf'):
    """
    Crée un PDF (standard ou présentation Beamer) en utilisant les titres appropriés
    et en insérant un en-tête d'images personnalisé.
    """
    try:
        logging.info(f"Création du document : {filename} (type: {doc_type}, format: {output_format})")

        # --- ÉTAPE DE NETTOYAGE ET NORMALISATION ---
        # Cette partie est spécifiquement pour les présentations Beamer afin d'éviter les erreurs LaTeX.
        if output_format == 'beamer':
            # Assure que les titres de diapositive sont bien séparés.
            text = re.sub(r'\s*(##\s)', r'\n\n\1', text)
            # Aplatit les listes trop profondes qui causent l'erreur "Too deeply nested".
            text = re.sub(r'^\s{4,}[\*\-]\s', '  - ', text, flags=re.MULTILINE)
            # Échappe les underscores (_) sauf s'ils sont dans une URL.
            lines = text.split('\n')
            processed_lines = []
            for line in lines:
                if 'http' not in line:
                    line = line.replace('_', '\\_')
                processed_lines.append(line)
            text = '\n'.join(processed_lines)
            # Rétablit les `##` qui auraient pu être échappés.
            text = text.replace('\\#\\# ', '## ')

        # 1. Séparation du texte principal et des données du jeu bilingue.
        parts = re.split(r'<bilingual_data>.*?</bilingual_data>', text, flags=re.IGNORECASE | re.DOTALL)
        main_markdown_raw = parts[0]
        bilingual_data_match = re.search(r'<bilingual_data>(.*?)</bilingual_data>', text, flags=re.IGNORECASE | re.DOTALL)
        bilingual_data_raw = bilingual_data_match.group(1) if bilingual_data_match else ""

        # 2. Nettoyage du texte principal des commentaires HTML.
        main_markdown_final = re.sub(r'<!--.*?-->', '', main_markdown_raw, flags=re.DOTALL).strip().replace('bilingual_data', '')

        # 3. Construction du tableau Markdown pour le jeu bilingue.
        markdown_table = ""
        if bilingual_data_raw:
            bilingual_content = re.sub(r'<!--.*?-->', '', bilingual_data_raw, flags=re.DOTALL).strip()
            lines = [line.strip() for line in bilingual_content.split('\n') if line.strip() and ';' in line]
            if lines:
                table_title = TITLES.get(lang_contenu_code, TITLES['fr'])['JEU_BILINGUE']
                markdown_table += f"\n\n**{table_title}**\n\n"
                lang_map_display = {'fr': 'Français', 'en': 'English', 'de': 'Deutsch', 'es': 'Español', 'it': 'Italiano', 'zh': '中文', 'ar': 'العربية'}
                langue_source_nom = lang_map_display.get(lang_contenu_code, lang_contenu_code.capitalize())
                headers = ['N°', langue_source_nom, 'English'] if lang_contenu_code == 'fr' else ['N°', langue_source_nom, 'Français']
                markdown_table += f"| {headers[0]} | {headers[1]} | {headers[2]} |\n"
                markdown_table += "|:---:|:---|:---|\n"
                for i, line in enumerate(lines):
                    parts = [p.strip() for p in line.split(';')]
                    if len(parts) == 2:
                        markdown_table += f"| {i+1} | {parts[0]} | {parts[1]} |\n"

        # 4. Assemblage du document Markdown final.
        final_markdown_doc = ""
        # Cas spécial pour l'évaluation : on gère la séparation du corrigé.
        if doc_type == 'evaluation':
            corrige_title = TITLES.get(lang_contenu_code, TITLES['fr']).get('EVAL_CORRIGE_TITRE', 'CORRIGÉ DÉTAILLÉ')
            # On utilise le texte brut d'origine qui contient le séparateur.
            final_markdown_doc = re.sub(r'---\s*CORRIGE\s*---', f"\n\n---\n\n**{corrige_title}**\n\n---", text, flags=re.IGNORECASE)
        else:
            # Pour tous les autres documents (leçon), on combine le contenu et le jeu bilingue.
            final_markdown_doc = main_markdown_final + markdown_table

        # 5. Préparation de l'en-tête YAML et du code pour les images.
        selected_titles = TITLES.get(lang_contenu_code, TITLES['fr'])
        try:
            locale.setlocale(locale.LC_TIME, f'{lang_contenu_code}_{lang_contenu_code.upper()}.UTF-8' if lang_contenu_code not in ['zh', 'ar'] else 'en_US.UTF-8')
        except locale.Error:
            locale.setlocale(locale.LC_TIME, '') # Fallback sur la locale système.
        formatted_date = datetime.date.today().strftime('%d %B %Y')
        
        # Logique des titres (inchangée)
        pdf_title = selected_titles.get('PDF_TITLE', 'Document')
        pdf_author = selected_titles.get('PDF_AUTHOR', 'TCHATCHI AI')
        
        # 6. Construction de la source complète du document à convertir.
        yaml_header = ""
        document_source = ""
        if output_format == 'beamer':
            # Pour Beamer, on insère les images sur la diapositive de titre via 'titlegraphic'.
            yaml_header = f"""
---
title: "{pdf_title}"
author: "{pdf_author}"
date: "{formatted_date}"
lang: "{lang_contenu_code}"
documentclass: beamer
theme: Madrid
colortheme: beaver
header-includes:
- \\usepackage{{graphicx}}
- \\titlegraphic{{\\centering \\includegraphics[width=4cm]{{static/img/barcode.png}} \\hspace{{0.5cm}} \\includegraphics[height=1.5cm]{{static/img/camtrade_pass.png}} \\par}}
---
"""
            # Pour Beamer, on utilise le contenu SANS le jeu bilingue.
            document_source = yaml_header + main_markdown_final
        
        else: # Pour les PDF standards (leçon, évaluation, etc.)
            # Code LaTeX pour insérer les images en haut de la page dans une table invisible.
            header_images_latex = r"""
\begin{center}
\begin{tabular}{c c}
\includegraphics[width=6cm]{static/img/barcode.png} &
\includegraphics[height=2.5cm]{static/img/camtrade_pass.png} \\
\end{tabular}
\end{center}
\vspace{1cm}
"""
            # En-tête YAML pour un document standard.
            yaml_header = f"""
---
title: "{pdf_title}"
author: "{pdf_author}"
date: "{formatted_date}"
lang: "{lang_contenu_code}"
geometry: "margin=1in"
mainfont: "Liberation Serif"
header-includes:
- \\usepackage{{graphicx}}
- \\usepackage{{amsmath}}
- \\usepackage{{amssymb}}
- \\usepackage{{unicode-math}}
- \\setmainfont{{Liberation Serif}}
- \\setmathfont{{latinmodern-math.otf}}
---
"""
            # On combine : En-tête YAML + Code des images + Contenu complet du document.
            document_source = yaml_header + header_images_latex + final_markdown_doc

        # 7. Conversion avec Pandoc.
        extra_args = ['--pdf-engine=xelatex']
        pandoc_format = 'markdown'
        
        if output_format == 'beamer':
            pandoc_format = 'markdown+smart' # 'smart' est utile pour Beamer.
            extra_args.extend(['-t', 'beamer'])

        pypandoc.convert_text(document_source, 'pdf', format=pandoc_format,
                              outputfile=filename,
                              extra_args=extra_args)

        logging.info(f"PDF '{filename}' créé avec succès.")
        return True

    except Exception as e:
        logging.error(f"Erreur DÉFINITIVE lors de la création du PDF avec Pandoc: {e}")
        # Affiche le début du document source en cas d'erreur pour faciliter le débogage.
        if 'document_source' in locals():
            logging.error(f"Source Markdown problématique (extrait) : {document_source[:1500]}")
        return False