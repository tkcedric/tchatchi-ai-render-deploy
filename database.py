# database.py - Updated for Supabase
import os
from supabase import create_client, Client
import logging
from datetime import datetime, timedelta  # NOUVEAU : déplacé ici depuis plus bas dans le fichier (import mal placé)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Get Supabase credentials from environment variables
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

# Initialize Supabase client
supabase: Client = None
if SUPABASE_URL and SUPABASE_KEY:
    try:
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
        logger.info("Supabase client initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize Supabase client: {e}")
        supabase = None
else:
    logger.warning("Supabase credentials not found. Statistics will not be saved.")

def init_db():
    """Initialize the database - For Supabase, tables should be created manually"""
    if not supabase:
        logger.warning("Supabase not configured. Skipping database initialization.")
        return
    
    try:
        # Check if table exists, create if it doesn't
        result = supabase.table("stats").select("count", count="exact").execute()
        logger.info("Stats table verified successfully")
    except Exception as e:
        logger.error(f"Error initializing database: {e}")

# Dans database.py
def increment_stat(key):
    """Increment a statistic counter using an RPC call."""
    if not supabase:
        return
    
    try:
        # On appelle la fonction 'increment_stat_value' directement dans la base de données.
        supabase.rpc('increment_stat_value', {'key_to_increment': key}).execute()
    except Exception as e:
        logger.error(f"Error calling RPC to increment stat '{key}': {e}")

# la fonction get_all_stats
def get_all_stats():
    if not supabase: return {"lessons": 0, "integrations": 0, "evaluations": 0, "total_documents": 0, "digital_lessons": 0}
    try:
        result = supabase.table("stats").select("*").execute()
        stats = {item["stat_key"]: item["stat_value"] for item in result.data}
        return {
            "lessons": stats.get("lessons_generated", 0),
            "integrations": stats.get("integrations_generated", 0),
            "evaluations": stats.get("evaluations_generated", 0),
            "total_documents": stats.get("total_documents", 0),
            "digital_lessons": stats.get("digital_lessons_generated", 0) # <-- AJOUT
        }
    except Exception as e:
        logger.error(f"Error fetching stats: {e}")
        return {"lessons": 0, "integrations": 0, "evaluations": 0, "total_documents": 0, "digital_lessons": 0}
    


# Configuration des plans
PLANS_CONFIG = {
    "weekly": {"price": 500, "days": 7, "generations": 35, "name": "Pass Semaine"},
    "monthly": {"price": 1500, "days": 30, "generations": 140, "name": "Pass Mensuel"},
    "annual": {"price": 5000, "days": 365, "generations": 750, "name": "Pass Annuel"}
}

def record_transaction(user_email, reference, amount, plan_type, phone_number):
    """Enregistre une nouvelle transaction en attente."""
    if not supabase: return False
    try:
        supabase.table("transactions").insert({
            "user_email": user_email,
            "reference": reference,
            "amount": amount,
            "plan_type": plan_type,
            "phone_number": phone_number,
            "status": "PENDING"
        }).execute()
        return True
    except Exception as e:
        logger.error(f"Erreur enregistrement transaction : {e}")
        return False

def activate_subscription(reference):
    """Active le plan dès que la transaction est confirmée avec succès."""
    if not supabase: return False
    try:
        # 1. Récupérer la transaction
        txn_res = supabase.table("transactions").select("*").eq("reference", reference).execute()
        if not txn_res.data:
            return False
        
        txn = txn_res.data[0]
        if txn.get("status") == "SUCCESSFUL":
            return True # Déjà activée

        user_email = txn["user_email"]
        plan_type = txn["plan_type"]
        plan_info = PLANS_CONFIG.get(plan_type, PLANS_CONFIG["monthly"])

        expiration_date = datetime.now() + timedelta(days=plan_info["days"])

                # 2. Mettre à jour l'utilisateur
        supabase.table("users").update({
            "plan_type": f"premium_{plan_type}",
            "subscription_expires_at": expiration_date.isoformat(),
            "generations_limit": plan_info["generations"],
            "generation_count": 0  # NOUVEAU : on repart à zéro pour ce nouveau forfait
        }).eq("email", user_email).execute()

        # 3. Marquer la transaction comme réussie
        supabase.table("transactions").update({
            "status": "SUCCESSFUL",
            "updated_at": datetime.now().isoformat()
        }).eq("reference", reference).execute()

        logger.info(f"✅ Abonnement {plan_type} activé avec succès pour {user_email}")
        return True

    except Exception as e:
        logger.error(f"Erreur lors de l'activation de l'abonnement : {e}")
        return False
    

def reinitialiser_quota_gratuit_si_necessaire(user):
    """
    Vérifie si 7 jours se sont écoulés depuis la dernière réinitialisation du
    quota gratuit de cet utilisateur. Si oui, remet generation_count à 0 et
    met à jour last_reset_date. Modifie aussi user.generation_count en mémoire
    pour que la vérification de quota qui suit juste après soit à jour.
    """
    try:
        maintenant = datetime.now()

        if user.last_reset_date:
            derniere_reinit = datetime.fromisoformat(str(user.last_reset_date).replace('Z', '+00:00'))
            if derniere_reinit.tzinfo:
                derniere_reinit = derniere_reinit.replace(tzinfo=None)
            jours_ecoules = (maintenant - derniere_reinit).days
        else:
            # Aucune date de réinitialisation enregistrée : on considère que
            # c'est la première fois, donc on initialise sans reset immédiat.
            jours_ecoules = 0

        if jours_ecoules >= 7 or not user.last_reset_date:
            supabase.table("users").update({
                "generation_count": 0,
                "last_reset_date": maintenant.isoformat()
            }).eq("id", user.id).execute()
            user.generation_count = 0  # mise à jour en mémoire pour cette requête
            logger.info(f"Quota gratuit réinitialisé pour l'utilisateur {user.id}")
    except Exception as e:
        logger.error(f"Erreur lors de la réinitialisation du quota gratuit : {e}")
        # En cas d'erreur, on ne bloque pas l'utilisateur — on continue simplement
        # sans réinitialiser, plutôt que de faire planter la génération.