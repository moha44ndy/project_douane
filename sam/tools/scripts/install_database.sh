#!/bin/bash

# Script d'installation de la base de données optimisée
# Système de Classification Douanière CEDEAO

echo "=========================================="
echo "Installation de la Base de Données"
echo "Système de Classification Douanière CEDEAO"
echo "=========================================="
echo ""

# Configuration par défaut
DB_HOST="localhost"
DB_PORT="3306"
DB_USER="root"
DB_NAME="douane_optimized"
SQL_FILE="../../douane_optimized.sql"

# Demander les informations de connexion
read -p "Nom d'utilisateur MySQL [root]: " input_user
DB_USER=${input_user:-$DB_USER}

read -sp "Mot de passe MySQL: " DB_PASS
echo ""

read -p "Hôte MySQL [localhost]: " input_host
DB_HOST=${input_host:-$DB_HOST}

read -p "Port MySQL [3306]: " input_port
DB_PORT=${input_port:-$DB_PORT}

read -p "Nom de la base de données [douane_optimized]: " input_db
DB_NAME=${input_db:-$DB_NAME}

# Vérifier si le fichier SQL existe
if [ ! -f "$SQL_FILE" ]; then
    echo "❌ Erreur: Le fichier $SQL_FILE n'existe pas!"
    echo "Assurez-vous que le fichier est dans le répertoire racine du projet."
    exit 1
fi

echo ""
echo "Configuration:"
echo "  - Hôte: $DB_HOST"
echo "  - Port: $DB_PORT"
echo "  - Utilisateur: $DB_USER"
echo "  - Base de données: $DB_NAME"
echo "  - Fichier SQL: $SQL_FILE"
echo ""

read -p "Continuer l'installation? (o/n): " confirm
if [ "$confirm" != "o" ] && [ "$confirm" != "O" ]; then
    echo "Installation annulée."
    exit 0
fi

echo ""
echo "⏳ Installation en cours..."

# Exécuter le script SQL
mysql -h "$DB_HOST" -P "$DB_PORT" -u "$DB_USER" -p"$DB_PASS" < "$SQL_FILE"

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ Installation réussie!"
    echo ""
    echo "Informations de connexion:"
    echo "  - Base de données: $DB_NAME"
    echo "  - Utilisateur admin: admin"
    echo "  - Mot de passe admin: admin123 (⚠️ À CHANGER!)"
    echo ""
    echo "📝 N'oubliez pas de:"
    echo "  1. Changer le mot de passe de l'administrateur"
    echo "  2. Configurer les paramètres de connexion dans votre application"
    echo "  3. Faire une sauvegarde de la base de données"
    echo ""
else
    echo ""
    echo "❌ Erreur lors de l'installation!"
    echo "Vérifiez les informations de connexion et les permissions."
    exit 1
fi

