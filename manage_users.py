# manage_users.py

import os
from supabase import create_client, Client
from dotenv import load_dotenv
import argparse
from datetime import datetime, timedelta

# Charger les variables d'environnement
load_dotenv()

# Configuration de Supabase
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY") # Important: Utiliser la clé de service "service_role"

if not SUPABASE_URL or not SUPABASE_KEY:
    print("❌ Erreur : Les variables d'environnement SUPABASE_URL et SUPABASE_KEY sont requises.")
    exit(1)

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
print("✅ Connecté à Supabase.")

def grant_premium(email, duration_days=30):
    """Accorde le statut premium à un utilisateur pour une durée donnée."""
    try:
        # Calcule la date d'expiration
        expiration_date = datetime.now() + timedelta(days=duration_days)
        
        # Met à jour l'utilisateur dans la base de données
        response = supabase.table("users").update({
            "plan_type": "premium",
            "subscription_expires_at": expiration_date.isoformat()
        }).eq("email", email).execute()
        
        if not response.data:
            print(f"⚠️  Aucun utilisateur trouvé avec l'email : {email}")
        else:
            print(f"✅ Succès ! L'utilisateur {email} est maintenant Premium jusqu'au {expiration_date.strftime('%Y-%m-%d')}.")

    except Exception as e:
        print(f"❌ Erreur lors de la mise à jour de l'utilisateur : {e}")

def revoke_premium(email):
    """Révoque le statut premium d'un utilisateur."""
    try:
        response = supabase.table("users").update({
            "plan_type": "free",
            "subscription_expires_at": None # On supprime la date d'expiration
        }).eq("email", email).execute()

        if not response.data:
            print(f"⚠️  Aucun utilisateur trouvé avec l'email : {email}")
        else:
            print(f"✅ Succès ! Le statut Premium de l'utilisateur {email} a été révoqué.")
            
    except Exception as e:
        print(f"❌ Erreur lors de la mise à jour de l'utilisateur : {e}")

def main():
    parser = argparse.ArgumentParser(description="Outil de gestion des utilisateurs TCHATCHI AI.")
    parser.add_argument("action", choices=["grant", "revoke"], help="L'action à effectuer : 'grant' ou 'revoke'.")
    parser.add_argument("email", type=str, help="L'adresse email de l'utilisateur à gérer.")
    parser.add_argument("--days", type=int, default=30, help="Durée de l'abonnement en jours (pour l'action 'grant').")
    
    args = parser.parse_args()
    
    if args.action == "grant":
        grant_premium(args.email, args.days)
    elif args.action == "revoke":
        revoke_premium(args.email)

if __name__ == "__main__":
    # Avant d'exécuter, ajoutez une colonne 'subscription_expires_at' (de type 'timestamptz') à votre table 'users'.
    main()