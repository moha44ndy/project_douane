-- ============================================================
-- BASE DE DONNÉES SIMPLIFIÉE - SYSTÈME DE CLASSIFICATION DOUANIÈRE CEDEAO
-- Version: 1.0
-- Date: 2025
-- Description: Base de données minimaliste et adaptée au projet réel
-- ============================================================

SET SQL_MODE = "NO_AUTO_VALUE_ON_ZERO";
START TRANSACTION;
SET time_zone = "+00:00";

/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!40101 SET NAMES utf8mb4 */;

-- --------------------------------------------------------
-- Création de la base de données
-- --------------------------------------------------------

DROP DATABASE IF EXISTS `douane_simple`;
CREATE DATABASE `douane_simple` DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE `douane_simple`;

-- ============================================================
-- TABLE: UTILISATEURS
-- Description: Remplace users.json
-- ============================================================

CREATE TABLE `users` (
  `user_id` INT(11) NOT NULL AUTO_INCREMENT,
  `nom_user` VARCHAR(100) NOT NULL,
  `identifiant_user` VARCHAR(50) NOT NULL,
  `email` VARCHAR(150) NOT NULL,
  `password_hash` VARCHAR(255) NOT NULL COMMENT 'Hash bcrypt',
  `statut` ENUM('actif','inactif','suspendu') DEFAULT 'actif',
  `is_admin` TINYINT(1) DEFAULT 0,
  `date_creation` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `derniere_connexion` TIMESTAMP NULL DEFAULT NULL,
  PRIMARY KEY (`user_id`),
  UNIQUE KEY `uk_identifiant` (`identifiant_user`),
  UNIQUE KEY `uk_email` (`email`),
  KEY `idx_statut` (`statut`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================
-- TABLE: CLASSIFICATIONS
-- Description: Remplace table_data.json - Stocke les produits classifiés
-- Structure alignée avec le JSON actuel
-- ============================================================

CREATE TABLE `classifications` (
  `id` INT(11) NOT NULL AUTO_INCREMENT,
  `user_id` INT(11) NOT NULL COMMENT 'Utilisateur qui a créé la classification',
  
  -- Données produit (correspond à product dans JSON)
  `description_produit` TEXT NOT NULL,
  `valeur_produit` VARCHAR(100) DEFAULT NULL COMMENT 'Valeur ou "Non renseigné"',
  `origine_produit` VARCHAR(100) DEFAULT NULL COMMENT 'Pays d''origine ou "Non renseigné"',
  
  -- Données classification (correspond à classification dans JSON)
  `code_tarifaire` VARCHAR(20) DEFAULT NULL COMMENT 'HS code (ex: 8517.13.00.00)',
  `section` VARCHAR(10) DEFAULT NULL COMMENT 'Section (ex: XVI)',
  `chapitre` VARCHAR(10) DEFAULT NULL COMMENT 'Chapitre extrait du code',
  `confidence_score` DECIMAL(5,2) DEFAULT NULL COMMENT 'Score de confiance 0-100',
  
  -- Informations supplémentaires de l'IA (optionnel)
  `taux_dd` VARCHAR(50) DEFAULT NULL COMMENT 'Taux droits de douane',
  `taux_rs` VARCHAR(50) DEFAULT NULL COMMENT 'Taux redevance statistique',
  `taux_tva` VARCHAR(50) DEFAULT NULL COMMENT 'Taux TVA',
  `unite_mesure` VARCHAR(50) DEFAULT NULL COMMENT 'Unité de mesure',
  `justification` TEXT COMMENT 'Justification de la classification',
  
  -- Statut et validation
  `statut_validation` ENUM('en_attente','valide','rejete') DEFAULT 'en_attente',
  `id_validateur` INT(11) DEFAULT NULL COMMENT 'Utilisateur qui a validé',
  `date_validation` TIMESTAMP NULL DEFAULT NULL,
  `commentaire_validation` TEXT COMMENT 'Commentaire du validateur',
  
  -- Métadonnées
  `date_classification` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `date_modification` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  
  PRIMARY KEY (`id`),
  KEY `idx_user` (`user_id`),
  KEY `idx_statut` (`statut_validation`),
  KEY `idx_date` (`date_classification`),
  KEY `idx_code_tarifaire` (`code_tarifaire`),
  KEY `idx_section` (`section`),
  CONSTRAINT `fk_classifications_user` FOREIGN KEY (`user_id`) 
    REFERENCES `users` (`user_id`) 
    ON DELETE RESTRICT ON UPDATE CASCADE,
  CONSTRAINT `fk_classifications_validateur` FOREIGN KEY (`id_validateur`) 
    REFERENCES `users` (`user_id`) 
    ON DELETE SET NULL ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================
-- TABLE: HISTORIQUE (Optionnel mais recommandé)
-- Description: Trace les modifications des classifications
-- ============================================================

CREATE TABLE `historique` (
  `id_historique` INT(11) NOT NULL AUTO_INCREMENT,
  `classification_id` INT(11) NOT NULL,
  `user_id` INT(11) NOT NULL,
  `action` ENUM('creation','modification','validation','rejet') NOT NULL,
  `ancien_code_tarifaire` VARCHAR(20) DEFAULT NULL,
  `nouveau_code_tarifaire` VARCHAR(20) DEFAULT NULL,
  `ancien_statut` VARCHAR(20) DEFAULT NULL,
  `nouveau_statut` VARCHAR(20) DEFAULT NULL,
  `commentaire` TEXT,
  `date_action` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id_historique`),
  KEY `idx_classification` (`classification_id`),
  KEY `idx_user` (`user_id`),
  KEY `idx_date` (`date_action`),
  CONSTRAINT `fk_historique_classification` FOREIGN KEY (`classification_id`) 
    REFERENCES `classifications` (`id`) 
    ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT `fk_historique_user` FOREIGN KEY (`user_id`) 
    REFERENCES `users` (`user_id`) 
    ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================
-- TRIGGERS
-- ============================================================

DELIMITER $$

-- Trigger: Logger automatiquement les créations
CREATE TRIGGER `trg_log_creation` 
AFTER INSERT ON `classifications` 
FOR EACH ROW 
BEGIN
    INSERT INTO `historique` (
        `classification_id`, `user_id`, `action`,
        `nouveau_code_tarifaire`, `nouveau_statut`
    ) VALUES (
        NEW.`id`, NEW.`user_id`, 'creation',
        NEW.`code_tarifaire`, NEW.`statut_validation`
    );
END$$

-- Trigger: Logger les modifications importantes
CREATE TRIGGER `trg_log_modification`
AFTER UPDATE ON `classifications`
FOR EACH ROW
BEGIN
    IF OLD.`code_tarifaire` != NEW.`code_tarifaire` OR
       OLD.`statut_validation` != NEW.`statut_validation` OR
       OLD.`section` != NEW.`section` THEN
        INSERT INTO `historique` (
            `classification_id`, `user_id`, `action`,
            `ancien_code_tarifaire`, `nouveau_code_tarifaire`,
            `ancien_statut`, `nouveau_statut`
        ) VALUES (
            NEW.`id`, NEW.`user_id`, 'modification',
            OLD.`code_tarifaire`, NEW.`code_tarifaire`,
            OLD.`statut_validation`, NEW.`statut_validation`
        );
    END IF;
END$$

DELIMITER ;

-- ============================================================
-- VUES UTILES
-- ============================================================

-- Vue: Classifications complètes avec infos utilisateur
CREATE OR REPLACE VIEW `vue_classifications_completes` AS
SELECT 
    c.`id`,
    c.`description_produit`,
    c.`valeur_produit`,
    c.`origine_produit`,
    c.`code_tarifaire`,
    c.`section`,
    c.`chapitre`,
    c.`confidence_score`,
    c.`taux_dd`,
    c.`taux_rs`,
    c.`taux_tva`,
    c.`unite_mesure`,
    c.`justification`,
    c.`statut_validation`,
    c.`date_classification`,
    c.`date_modification`,
    u.`nom_user` AS `nom_classificateur`,
    u.`identifiant_user` AS `identifiant_classificateur`,
    uv.`nom_user` AS `nom_validateur`,
    uv.`identifiant_user` AS `identifiant_validateur`,
    c.`date_validation`
FROM `classifications` c
JOIN `users` u ON c.`user_id` = u.`user_id`
LEFT JOIN `users` uv ON c.`id_validateur` = uv.`user_id`;

-- ============================================================
-- DONNÉES INITIALES
-- ============================================================

-- Utilisateur administrateur par défaut
-- Mot de passe: admin123 (hash bcrypt - À CHANGER EN PRODUCTION!)
-- Ce hash correspond à "admin123" avec bcrypt
INSERT INTO `users` (`nom_user`, `identifiant_user`, `email`, `password_hash`, `is_admin`, `statut`) VALUES
('Administrateur Système', 'admin', 'admin@douane.ci', '$2y$10$qaycdapujJoiIbi.ip5g2.EaNCZYhX2fupd472YKKqRNTEUNOVz3m', 1, 'actif');

-- ============================================================
-- PROCÉDURES UTILES (Optionnel)
-- ============================================================

DELIMITER $$

-- Procédure: Statistiques utilisateur
CREATE PROCEDURE `GetUserStats`(IN `p_user_id` INT)
BEGIN
    SELECT 
        u.`nom_user`,
        u.`identifiant_user`,
        u.`email`,
        COUNT(c.`id`) AS `total_classifications`,
        SUM(CASE WHEN c.`statut_validation` = 'valide' THEN 1 ELSE 0 END) AS `validees`,
        SUM(CASE WHEN c.`statut_validation` = 'en_attente' THEN 1 ELSE 0 END) AS `en_attente`,
        SUM(CASE WHEN c.`statut_validation` = 'rejete' THEN 1 ELSE 0 END) AS `rejetees`,
        AVG(c.`confidence_score`) AS `confidence_moyenne`,
        MAX(c.`date_classification`) AS `derniere_classification`
    FROM `users` u
    LEFT JOIN `classifications` c ON u.`user_id` = c.`user_id`
    WHERE u.`user_id` = p_user_id
    GROUP BY u.`user_id`, u.`nom_user`, u.`identifiant_user`, u.`email`;
END$$

-- Procédure: Valider une classification
CREATE PROCEDURE `ValiderClassification`(
    IN `p_classification_id` INT, 
    IN `p_validateur_id` INT,
    IN `p_commentaire` TEXT
)
BEGIN
    DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
        ROLLBACK;
        RESIGNAL;
    END;
    
    START TRANSACTION;
    
    UPDATE `classifications` 
    SET `statut_validation` = 'valide',
        `id_validateur` = p_validateur_id,
        `date_validation` = CURRENT_TIMESTAMP,
        `commentaire_validation` = p_commentaire,
        `date_modification` = CURRENT_TIMESTAMP
    WHERE `id` = p_classification_id;
    
    INSERT INTO `historique` (
        `classification_id`, `user_id`, `action`, `commentaire`
    ) VALUES (
        p_classification_id, p_validateur_id, 'validation', 
        COALESCE(p_commentaire, 'Classification validée')
    );
    
    COMMIT;
END$$

DELIMITER ;

-- ============================================================
-- FIN DU SCRIPT
-- ============================================================

COMMIT;

/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;

