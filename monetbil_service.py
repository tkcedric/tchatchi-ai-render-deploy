"""
monetbil_service.py

Intégration avec Monetbil, utilisée en remplacement de CamPay (qui exige des
documents d'entreprise qu'on n'a pas en tant que particulier).

Contrairement à CamPay (paiement direct sans quitter notre site), Monetbil
fonctionne par REDIRECTION : on demande un lien de paiement, on y redirige
l'utilisateur, Monetbil gère la saisie du numéro/opérateur sur sa propre
page, puis nous notifie du résultat (notify_url) et ramène l'utilisateur
chez nous (return_url).
"""

import os
import hashlib
import logging
import requests

logger = logging.getLogger(__name__)

MONETBIL_SERVICE_KEY = os.getenv("MONETBIL_SERVICE_KEY")
MONETBIL_SERVICE_SECRET = os.getenv("MONETBIL_SERVICE_SECRET")
BASE_URL = "https://api.monetbil.com/widget/v2.1"


def demander_lien_paiement(amount, description, payment_ref, notify_url, return_url, user_email):
    """
    Demande à Monetbil un lien de paiement vers lequel rediriger l'utilisateur.
    Renvoie {"success": True, "payment_url": "..."} ou {"success": False, "message": "..."}
    """
    if not MONETBIL_SERVICE_KEY:
        logger.error("Clé Monetbil manquante dans les variables d'environnement.")
        return {"success": False, "message": "Le service de paiement n'est pas configuré correctement."}

    url = f"{BASE_URL}/{MONETBIL_SERVICE_KEY}"
    payload = {
        "amount": amount,
        "currency": "XAF",
        "locale": "fr",
        "country": "CM",
        "item_ref": "abonnement_tchatchiai",
        "payment_ref": payment_ref,
        "user": user_email,
        "email": user_email,
        "notify_url": notify_url,
        "return_url": return_url,
    }

    try:
        logger.info(f"👉 ENVOI REQUÊTE VERS MONETBIL: {url} | PAYLOAD: {payload}")
        response = requests.post(url, data=payload, timeout=25)
        logger.info(f"👈 RÉPONSE DE MONETBIL (Code HTTP: {response.status_code}) | CONTENU: {response.text}")

        data = response.json()
        if data.get("success"):
            return {"success": True, "payment_url": data.get("payment_url")}
        return {"success": False, "message": "Le paiement n'a pas pu être initié. Réessayez."}
    except Exception as e:
        logger.error(f"Erreur appel Monetbil : {e}")
        return {"success": False, "message": "Erreur de communication avec le service de paiement. Réessayez."}


def verifier_signature(params_recus):
    """
    Vérifie qu'une notification reçue provient bien de Monetbil, en
    recalculant la signature attendue (formule officielle du SDK Monetbil :
    md5(service_secret + valeurs triées par clé, concaténées)) et en la
    comparant à celle reçue dans le paramètre "sign". Protège contre les
    fausses notifications, comme on l'a fait pour le webhook CamPay.
    """
    if not MONETBIL_SERVICE_SECRET:
        logger.error("Clé secrète Monetbil manquante, impossible de vérifier la signature.")
        return False

    params = dict(params_recus)
    signature_recue = params.pop("sign", None)
    if not signature_recue:
        return False

    cles_triees = sorted(params.keys())
    valeurs_concatenees = "".join(str(params[cle]) for cle in cles_triees)
    signature_attendue = hashlib.md5((MONETBIL_SERVICE_SECRET + valeurs_concatenees).encode()).hexdigest()

    return signature_recue == signature_attendue