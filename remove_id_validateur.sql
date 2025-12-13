-- Script pour supprimer la colonne id_validateur et sa contrainte de clé étrangère
-- Base de données: douane_db
-- Table: classifications

USE douane_db;

-- Étape 1: Supprimer la contrainte de clé étrangère
ALTER TABLE `classifications` 
DROP FOREIGN KEY `fk_classifications_validateur`;

-- Étape 2: Supprimer la colonne id_validateur
ALTER TABLE `classifications` 
DROP COLUMN `id_validateur`;

-- Vérification: Afficher la structure de la table pour confirmer
DESCRIBE `classifications`;

