"""
Script de test isolé pour vérifier la connexion CamPay en mode démo.
Il n'utilise aucune donnée de l'app (pas de forfait, pas de base de données) :
il appelle juste collect_payment() avec un montant de 25 XAF, la limite max
autorisée en mode démo.

Pour lancer ce test : python test_campay.py
"""

# On charge le fichier .env pour que les variables CAMPAY_* soient disponibles,
# exactement comme le fait config.py quand l'app Flask démarre normalement.
from dotenv import load_dotenv
load_dotenv()

# On importe directement la fonction qui déclenche le paiement.
from campay_service import collect_payment, check_transaction_status
import time

# ⚠️ Remplace ce numéro par UN NUMÉRO MTN OU ORANGE CAMEROUNAIS QUE TU CONTRÔLES
# Format attendu : 9 chiffres, sans le +237 (il est ajouté automatiquement)
NUMERO_TEST = "694064655"  # <-- change ça avec ton propre numéro de test

print("=== TEST CAMPAY (mode démo, 25 XAF) ===")
print(f"Numéro utilisé : {NUMERO_TEST}")

# On lance la demande de paiement, exactement comme le ferait l'app
resultat = collect_payment(
    phone_number=NUMERO_TEST,
    amount=25,  # Montant maximum autorisé en mode démo CamPay
    description="Test démo TCHATCHI AI",
    external_reference="test-script-local"
)

print("\nRésultat de la demande initiale :")
print(resultat)

# Si la demande a été acceptée par CamPay, on va vérifier le statut
# toutes les 3 secondes, comme le fait le JS sur le site (pollPaymentStatus).
if resultat.get("success"):
    reference = resultat.get("reference")
    print(f"\n📱 Va sur ton téléphone ({NUMERO_TEST}) et valide le paiement avec ton code PIN.")
    print("Vérification du statut toutes les 3 secondes (max 60 secondes)...\n")

    for tentative in range(20):
        time.sleep(3)
        statut = check_transaction_status(reference)
        print(f"Tentative {tentative + 1}/20 — Statut : {statut}")

        if statut == "SUCCESSFUL":
            print("\n✅ PAIEMENT VALIDÉ ! Le circuit CamPay fonctionne correctement.")
            break
        elif statut == "FAILED":
            print("\n❌ Paiement échoué ou annulé côté téléphone.")
            break
    else:
        print("\n⏱️ Délai dépassé (60s), aucun statut final reçu.")
else:
    print("\n❌ La demande initiale a échoué — voir le message ci-dessus pour comprendre pourquoi.")