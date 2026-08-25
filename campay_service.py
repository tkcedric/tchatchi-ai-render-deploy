# campay_service.py - Version avec diagnostic complet
import os
import requests
import logging

logger = logging.getLogger(__name__)

CAMPAY_ENV = os.environ.get("CAMPAY_ENV", "live").strip().lower()
BASE_URL = "https://demo.campay.net/api" if CAMPAY_ENV == "demo" else "https://www.campay.net/api"

PERMANENT_TOKEN = os.environ.get("CAMPAY_PERMANENT_TOKEN", "").strip()
USERNAME = os.environ.get("CAMPAY_APP_USERNAME", "").strip()
PASSWORD = os.environ.get("CAMPAY_APP_PASSWORD", "").strip()

def get_auth_token():
    """Génère automatiquement un token d'accès officiel avec Username & Password."""
    # 1. On privilégie la génération automatique par Username/Password (le plus fiable)
    if USERNAME and PASSWORD:
        try:
            url = f"{BASE_URL}/token/"
            res = requests.post(url, json={"username": USERNAME, "password": PASSWORD}, timeout=15)
            if res.status_code == 200:
                token = res.json().get("token")
                if token:
                    return token
            else:
                logger.error(f"Erreur génération token CamPay ({res.status_code}): {res.text}")
        except Exception as e:
            logger.error(f"Exception connexion /token/ CamPay : {e}")

    # 2. Fallback sur le permanent token si défini
    if PERMANENT_TOKEN:
        return PERMANENT_TOKEN
        
    return None

def traduire_erreur_campay(message_brut):
    """
    NOUVEAU : transforme un message d'erreur technique de CamPay (souvent en
    anglais, parfois cryptique) en un message clair pour l'utilisateur final.
    Le message technique original reste dans les logs (via logger.error)
    pour le débogage, seul ce message traduit est montré à l'utilisateur.
    """
    msg = message_brut.lower()

    if "insufficient" in msg or "balance" in msg or "solde" in msg:
        return "Solde insuffisant sur votre compte Mobile Money. Rechargez puis réessayez."
    if "invalid" in msg and ("token" in msg or "credential" in msg or "login" in msg):
        return "Le service de paiement rencontre un problème technique de notre côté. Réessayez dans quelques minutes, ou contactez le support si ça persiste."
    if "invalid" in msg and ("phone" in msg or "number" in msg or "from" in msg):
        return "Numéro de téléphone invalide. Vérifiez le format (9 chiffres, ex: 674123456)."
    if "demo" in msg or "maximum amount" in msg:
        return "Montant trop élevé pour le mode démo actuel (limite 25 XAF). Ceci est un message de test, contactez l'équipe technique."
    if "timeout" in msg or "connection" in msg:
        return "Impossible de contacter le service de paiement (connexion trop lente ou indisponible). Réessayez dans quelques instants."

    return "Le paiement n'a pas pu être initié. Réessayez, ou contactez le support si le problème persiste."

def collect_payment(phone_number, amount, description, external_reference):
    """
    Déclenche la demande de paiement (Push USSD) sur le téléphone de l'utilisateur.
    """
    token = get_auth_token()
    if not token:
        return {"success": False, "message": "Clé d'authentification CamPay manquante ou invalide dans le .env."}

    # Nettoyage du numéro
    phone = str(phone_number).replace("+", "").replace(" ", "").strip()
    if not phone.startswith("237"):
        phone = f"237{phone}"

    url = f"{BASE_URL}/collect/"
    headers = {
        "Authorization": f"Token {token}",
        "Content-Type": "application/json"
    }
    payload = {
        "amount": str(int(amount)),
        "currency": "XAF",
        "from": phone,
        "description": description[:60], # Limite de longueur
        "external_reference": str(external_reference)[:50]
    }

    try:
        logger.info(f"👉 ENVOI REQUÊTE VERS CAMPAY: {url} | PAYLOAD: {payload}")

        response = requests.post(url, json=payload, headers=headers, timeout=25)

        logger.info(f"👈 RÉPONSE DE CAMPAY (Code HTTP: {response.status_code}) | CONTENU: {response.text}")

        data = response.json()
        
        if response.status_code in [200, 201]:
            return {
                "success": True,
                "reference": data.get("reference"),
                "ussd_code": data.get("ussd_code"),
                "operator": data.get("operator")
            }
        else:
            # Récupération du message d'erreur précis de CamPay (pour les logs uniquement)
            error_msg = data.get("message") or data.get("detail") or data.get("error") or str(data)
            logger.error(f"Erreur CamPay ({response.status_code}) : {error_msg}")
            return {"success": False, "message": traduire_erreur_campay(error_msg)}

    except Exception as e:
        logger.error(f"Erreur appel collect CamPay : {e}")
        return {"success": False, "message": traduire_erreur_campay(str(e))}

def check_transaction_status(reference):
    """Vérifie le statut d'une transaction donnée."""
    token = get_auth_token()
    if not token:
        return "FAILED"

    url = f"{BASE_URL}/transaction/{reference}/"
    headers = {"Authorization": f"Token {token}"}

    try:
        response = requests.get(url, headers=headers, timeout=10)
        # NOUVEAU : on log la réponse de CamPay pour chaque vérification de
        # statut, pour pouvoir diagnostiquer les cas comme MTN vs Orange.
        logger.info(f"🔍 VÉRIFICATION STATUT {reference} (HTTP {response.status_code}) | CONTENU: {response.text}")
        if response.status_code == 200:
            return response.json().get("status")
    except Exception as e:
        logger.error(f"Erreur vérification transaction {reference} : {e}")
    return "PENDING"