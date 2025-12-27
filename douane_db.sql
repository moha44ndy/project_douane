-- phpMyAdmin SQL Dump
-- version 5.1.2
-- https://www.phpmyadmin.net/
--
-- Host: localhost:4240
-- Generation Time: Dec 27, 2025 at 03:11 PM
-- Server version: 5.7.24
-- PHP Version: 8.3.1

SET SQL_MODE = "NO_AUTO_VALUE_ON_ZERO";
START TRANSACTION;
SET time_zone = "+00:00";


/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!40101 SET NAMES utf8mb4 */;

--
-- Database: `douane_db`
--

DELIMITER $$
--
-- Procedures
--
CREATE DEFINER=`root`@`localhost` PROCEDURE `GetUserStats` (IN `p_user_id` INT)   BEGIN
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

CREATE DEFINER=`root`@`localhost` PROCEDURE `ValiderClassification` (IN `p_classification_id` INT, IN `p_validateur_id` INT, IN `p_commentaire` TEXT)   BEGIN
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

-- --------------------------------------------------------

--
-- Table structure for table `classifications`
--

CREATE TABLE `classifications` (
  `id` int(11) NOT NULL,
  `user_id` int(11) NOT NULL COMMENT 'Utilisateur qui a créé la classification',
  `description_produit` text COLLATE utf8mb4_unicode_ci NOT NULL,
  `valeur_produit` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT 'Valeur ou "Non renseigné"',
  `origine_produit` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT 'Pays d''origine ou "Non renseigné"',
  `code_tarifaire` varchar(20) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT 'HS code (ex: 8517.13.00.00)',
  `section` varchar(10) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT 'Section (ex: XVI)',
  `chapitre` varchar(10) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT 'Chapitre extrait du code',
  `confidence_score` decimal(5,2) DEFAULT NULL COMMENT 'Score de confiance 0-100',
  `taux_dd` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT 'Taux droits de douane',
  `taux_rs` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT 'Taux redevance statistique',
  `taux_tva` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT 'Taux TVA',
  `unite_mesure` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT 'Unité de mesure',
  `justification` text COLLATE utf8mb4_unicode_ci COMMENT 'Justification de la classification',
  `date_classification` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `date_modification` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  `user_query` text COLLATE utf8mb4_unicode_ci COMMENT 'Requête originale de l''utilisateur',
  `user_query_hash` varchar(64) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT 'Hash de la requête pour recherche rapide',
  `feedback_rating` enum('up','down') COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT 'Note utilisateur: up (?) ou down (?)'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

--
-- Dumping data for table `classifications`
--

INSERT INTO `classifications` (`id`, `user_id`, `description_produit`, `valeur_produit`, `origine_produit`, `code_tarifaire`, `section`, `chapitre`, `confidence_score`, `taux_dd`, `taux_rs`, `taux_tva`, `unite_mesure`, `justification`, `date_classification`, `date_modification`, `user_query`, `user_query_hash`, `feedback_rating`) VALUES
(39, 1, 'ordinateur', 'Non renseigné', 'Non renseigné', '8471.49.00.00', 'XVI', '84', '90.00', 'Non renseigné', 'Non renseigné', 'Non renseigné', 'PIÈCE', 'RGI: Le n° 8471.49 couvre les systèmes de traitement automatique de l’information et les machines correspondantes; conformément à la Note 1 de la Section XVI et à la Note 1 du Chapitre 84, les ordinateurs remplissent les critères.', '2025-12-25 23:51:09', '2025-12-25 23:51:09', NULL, NULL, NULL),
(40, 1, 'ordinateur', 'Non renseigné', 'Non renseigné', '8471.49.00.00', 'XVI', '84', '92.00', 'Non renseigné', 'Non renseigné', 'Non renseigné', 'PIÈCE', 'RGI : selon la définition du n° 8471.49 relatif aux systèmes automatiques de traitement de l\'information (note 2 et texte associé), le produit (ordinateur) est un système de traitement de l\'information et relève de 8471.49.00.00. Correspondance évoquée dans le document sous la rubrique 8471.49, avec les précisions sur les composants et caractéristiques d’un système de traitement de l’information.', '2025-12-26 00:00:58', '2025-12-26 00:00:58', NULL, NULL, NULL),
(41, 1, 'ordinateur', 'Non renseigné', 'Non renseigné', '8471.49.00.00', 'XVI', '84', '85.00', 'Non renseigné', 'Non renseigné', 'Non renseigné', 'PIÈCE', 'RGI 2 et notes de chapitre: Au sens du n° 8471.49, ce sont des systèmes de traitement de l\'information; le texte précise cette définition et indique que les machines répondent aux critères de la Note 6 C) du Chapitre 84, ce qui conduit à classer l\'ordinateur sous 8471.49.00.00.', '2025-12-26 00:04:37', '2025-12-26 00:04:37', NULL, NULL, NULL),
(42, 1, 'ordinateur', 'Non renseigné', 'Non renseigné', '8471.49.00.00', 'XVI', '84', '85.00', 'Non renseigné', 'Non renseigné', 'Non renseigné', 'PIÈCE', 'RGI 2 et notes de chapitre: Au sens du n° 8471.49, ce sont des systèmes de traitement de l\'information; le texte précise cette définition et indique que les machines répondent aux critères de la Note 6 C) du Chapitre 84, ce qui conduit à classer l\'ordinateur sous 8471.49.00.00.', '2025-12-26 00:04:51', '2025-12-26 00:04:51', NULL, NULL, NULL),
(43, 1, 'ordinateur', 'Non renseigné', 'Non renseigné', '8471.49.00.00', 'XVI', '84', '85.00', 'Non renseigné', 'Non renseigné', 'Non renseigné', 'PIÈCE', 'RGI 2 et notes de chapitre: Au sens du n° 8471.49, ce sont des systèmes de traitement de l\'information; le texte précise cette définition et indique que les machines répondent aux critères de la Note 6 C) du Chapitre 84, ce qui conduit à classer l\'ordinateur sous 8471.49.00.00.', '2025-12-26 00:05:00', '2025-12-26 00:05:00', NULL, NULL, NULL),
(44, 1, 'Ordinateur', 'Non renseigné', 'Non renseigné', '8471.49.00.00', 'XVI', '84', '92.00', 'Non renseigné', 'Non renseigné', 'Non renseigné', 'PIÈCE', 'RGI: Classification comme système automatique de traitement de l\'information (n° 8471.49) selon les notes de sous-position; le document précise les critères pour les systèmes (unité centrale, entrée, dispositifs semi-conducteurs et affichage). Pas de taux fournis dans l’extrait.', '2025-12-26 00:08:24', '2025-12-26 00:08:24', NULL, NULL, NULL),
(45, 1, 'Ordinateur', 'Non renseigné', 'Non renseigné', '8471.49.00.00', 'XVI', '84', '92.00', 'Non renseigné', 'Non renseigné', 'Non renseigné', 'PIÈCE', 'RGI: Classification comme système automatique de traitement de l\'information (n° 8471.49) selon les notes de sous-position; le document précise les critères pour les systèmes (unité centrale, entrée, dispositifs semi-conducteurs et affichage). Pas de taux fournis dans l’extrait.', '2025-12-26 00:08:44', '2025-12-26 00:08:44', NULL, NULL, NULL),
(46, 1, 'Ordinateur / ordinateur personnel', 'Non renseigné', 'Non renseigné', '8471.30.00.00', 'XVI', '84', '75.00', 'Non renseigné', 'Non renseigné', 'Non renseigné', 'PIÈCE', 'RGI: classification probable sous 8471 (automat. data processing machines); déduction fondée sur les règles RGI lorsque le document ne précise pas le code exact; correspondance avec le terme « ordi » et logique TEC CEDEAO pour équipements informatiques', '2025-12-26 00:09:13', '2025-12-26 00:09:13', NULL, NULL, NULL),
(47, 1, 'Ordinateur', 'Non renseigné', 'Non renseigné', '8471.49.00.00', 'XVI', '84', '92.00', 'Non renseigné', 'Non renseigné', 'Non renseigné', 'PIÈCE', 'RGI: Classification comme système automatique de traitement de l\'information (n° 8471.49) selon les notes de sous-position; le document précise les critères pour les systèmes (unité centrale, entrée, dispositifs semi-conducteurs et affichage). Pas de taux fournis dans l’extrait.', '2025-12-26 00:09:22', '2025-12-26 00:09:22', NULL, NULL, NULL),
(48, 1, 'Ordinateur', 'Non renseigné', 'Non renseigné', '8471.49.00.00', 'XVI', '84', '92.00', 'Non renseigné', 'Non renseigné', 'Non renseigné', 'PIÈCE', 'RGI: Classification comme système automatique de traitement de l\'information (n° 8471.49) selon les notes de sous-position; le document précise les critères pour les systèmes (unité centrale, entrée, dispositifs semi-conducteurs et affichage). Pas de taux fournis dans l’extrait.', '2025-12-26 00:09:37', '2025-12-26 00:09:37', NULL, NULL, NULL),
(49, 1, 'Ordinateur', 'Non renseigné', 'Non renseigné', '8471.49.00.00', 'XVI', '84', '92.00', 'Non renseigné', 'Non renseigné', 'Non renseigné', 'PIÈCE', 'RGI 2 et note 2 du n° 8471.49: «2.- Au sens du n° 8471.49, on entend par systèmes les machines automatiques de traitement de l\'information...»; le produit correspond à une unité de traitement automatique de l\'information et est classé dans 8471.49 (ordre général des ordinateurs). Conformité avec Note 1 de la Section XVI et Note 1 du Chapitre 84; les cas relevant des 84.86 seraient des pièces/accessoires, non l’appareil lui-même.', '2025-12-26 00:12:49', '2025-12-26 00:12:49', NULL, NULL, NULL),
(50, 1, 'Ordinateur', 'Non renseigné', 'Non renseigné', '8471.49.00.00', 'XVI', '84', '92.00', 'Non renseigné', 'Non renseigné', 'Non renseigné', 'PIÈCE', 'RGI 2 et note 2 du n° 8471.49: «2.- Au sens du n° 8471.49, on entend par systèmes les machines automatiques de traitement de l\'information...»; le produit correspond à une unité de traitement automatique de l\'information et est classé dans 8471.49 (ordre général des ordinateurs). Conformité avec Note 1 de la Section XVI et Note 1 du Chapitre 84; les cas relevant des 84.86 seraient des pièces/accessoires, non l’appareil lui-même.', '2025-12-26 00:12:54', '2025-12-26 00:12:54', NULL, NULL, NULL),
(51, 1, 'Ordinateur', 'Non renseigné', 'Non renseigné', '8471.49.00.00', 'XVI', '84', '92.00', 'Non renseigné', 'Non renseigné', 'Non renseigné', 'PIÈCE', 'RGI 2 et note 2 du n° 8471.49: «2.- Au sens du n° 8471.49, on entend par systèmes les machines automatiques de traitement de l\'information...»; le produit correspond à une unité de traitement automatique de l\'information et est classé dans 8471.49 (ordre général des ordinateurs). Conformité avec Note 1 de la Section XVI et Note 1 du Chapitre 84; les cas relevant des 84.86 seraient des pièces/accessoires, non l’appareil lui-même.', '2025-12-26 00:12:59', '2025-12-26 00:12:59', NULL, NULL, NULL),
(52, 1, 'ordinateur', 'Non renseigné', 'Non renseigné', '8471.50.00.00', 'XVI', '84', '60.00', 'Non renseigné', 'Non renseigné', 'Non renseigné', 'PIÈCE', 'Déduction fondée sur les règles RGI et la logique TEC CEDEAO; pas d’élément explicite dans le document pour un code précis d’ordinateur; classement proposé comme extrapolation topicuelle (8471.x) en l’absence de référence directe.', '2025-12-26 00:13:40', '2025-12-26 00:13:40', NULL, NULL, NULL),
(53, 1, 'Ordinateur (ordinateur personnel / unité centrale avec périphériques)', 'Non renseigné', 'Non renseigné', '8471.49.00.00', 'XVI', '84', '90.00', 'Non renseigné', 'Non renseigné', 'Non renseigné', 'PIÈCE', 'RGI / Note: 2 du n° 8471.49 qui précise que les systèmes informatiques sont des machines automatiques de traitement de l\'information répondant à des critères énoncés (au moins une unité centrale de traitement et une unité d\'entrée). Le produit « ordinateur » correspond à cette définition.', '2025-12-27 11:24:40', '2025-12-27 11:24:40', NULL, NULL, NULL),
(54, 1, 'Ordinateur (ordinateur personnel / unité centrale avec périphériques)', 'Non renseigné', 'Non renseigné', '8471.49.00.00', 'XVI', '84', '90.00', 'Non renseigné', 'Non renseigné', 'Non renseigné', 'PIÈCE', 'RGI / Note: 2 du n° 8471.49 qui précise que les systèmes informatiques sont des machines automatiques de traitement de l\'information répondant à des critères énoncés (au moins une unité centrale de traitement et une unité d\'entrée). Le produit « ordinateur » correspond à cette définition.', '2025-12-27 11:29:21', '2025-12-27 11:29:21', NULL, NULL, NULL),
(55, 1, 'Poste téléphonique d\'usager par fil à combinés sans fil', 'Non renseigné', 'Non renseigné', '8517.11.00.00', 'XVI', '85', '85.00', 'Non renseigné', 'Non renseigné', 'Non renseigné', 'PIÈCE', 'RGI 3 et  RGInécessaire: catégorie de postes téléphoniques d\'usagers par fil à combinés sans fil.', '2025-12-27 11:35:34', '2025-12-27 11:35:34', NULL, NULL, NULL),
(56, 1, 'Téléphones intelligents', 'Non renseigné', 'Non renseigné', '8517.13.00.00', 'XVI', '85', '92.00', 'Non renseigné', 'Non renseigné', 'Non renseigné', 'PIÈCE', 'RGI 1 et  RGInécessaire: téléphones intelligents inclus sous 8517.13.00.00.', '2025-12-27 11:35:34', '2025-12-27 11:35:34', NULL, NULL, NULL),
(57, 1, 'Autres téléphones pour réseaux cellulaires ou autres réseaux sans fil', 'Non renseigné', 'Non renseigné', '8517.14.00.00', 'XVI', '85', '85.00', 'Non renseigné', 'Non renseigné', 'Non renseigné', 'PIÈCE', 'RGI 1 et  RGInécessaire: catégorie « Autres téléphones pour réseaux cellulaires ou autres réseaux sans fil ».', '2025-12-27 11:35:34', '2025-12-27 11:35:34', NULL, NULL, NULL),
(58, 1, 'Autres', 'Non renseigné', 'Non renseigné', '8517.18.00.00', 'XVI', '85', '75.00', 'Non renseigné', 'Non renseigné', 'Non renseigné', 'PIÈCE', 'RGI 3: catégorie « Autres » sous 8517.18.00.00 pour les cas non couverts par les sous-positions spécifiques.', '2025-12-27 11:35:34', '2025-12-27 11:35:34', NULL, NULL, NULL),
(59, 1, 'Ordinateur (ordinateur personnel / unité centrale avec périphériques)', 'Non renseigné', 'Non renseigné', '8471.49.00.00', 'XVI', '84', '90.00', 'Non renseigné', 'Non renseigné', 'Non renseigné', 'PIÈCE', 'RGI / Note: 2 du n° 8471.49 qui précise que les systèmes informatiques sont des machines automatiques de traitement de l\'information répondant à des critères énoncés (au moins une unité centrale de traitement et une unité d\'entrée). Le produit « ordinateur » correspond à cette définition.', '2025-12-27 12:14:40', '2025-12-27 12:14:40', NULL, NULL, NULL),
(60, 1, 'Ordinateur (ordinateur personnel / unité centrale avec périphériques)', 'Non renseigné', 'Non renseigné', '8471.49.00.00', 'XVI', '84', '90.00', 'Non renseigné', 'Non renseigné', 'Non renseigné', 'PIÈCE', 'RGI / Note: 2 du n° 8471.49 qui précise que les systèmes informatiques sont des machines automatiques de traitement de l\'information répondant à des critères énoncés (au moins une unité centrale de traitement et une unité d\'entrée). Le produit « ordinateur » correspond à cette définition.', '2025-12-27 12:15:34', '2025-12-27 12:15:34', NULL, NULL, NULL),
(61, 1, 'Ordinateur (ordinateur personnel / unité centrale avec périphériques)', 'Non renseigné', 'Non renseigné', '8471.49.00.00', 'XVI', '84', '90.00', 'Non renseigné', 'Non renseigné', 'Non renseigné', 'PIÈCE', 'RGI / Note: 2 du n° 8471.49 qui précise que les systèmes informatiques sont des machines automatiques de traitement de l\'information répondant à des critères énoncés (au moins une unité centrale de traitement et une unité d\'entrée). Le produit « ordinateur » correspond à cette définition.', '2025-12-27 12:20:31', '2025-12-27 12:20:31', NULL, NULL, NULL),
(62, 1, 'Ordinateur (ordinateur personnel / unité informatique)', 'Non renseigné', 'Non renseigné', '8471.50.00.00', 'XVI', '84', '65.00', 'Non renseigné', 'Non renseigné', 'Non renseigné', 'PIÈCE', 'RGI: catégorie ordinateurs; TEC CEDEAO: machines de traitement de l\'information; déduction fondée sur les règles RGI et sur la logique tarifaire lorsque le terme exact n’apparaît pas dans le document.', '2025-12-27 12:23:58', '2025-12-27 12:23:58', NULL, NULL, NULL),
(63, 1, 'Ordinateur (ordinateur personnel / unité centrale avec périphériques)', 'Non renseigné', 'Non renseigné', '8471.49.00.00', 'XVI', '84', '90.00', 'Non renseigné', 'Non renseigné', 'Non renseigné', 'PIÈCE', 'RGI / Note: 2 du n° 8471.49 qui précise que les systèmes informatiques sont des machines automatiques de traitement de l\'information répondant à des critères énoncés (au moins une unité centrale de traitement et une unité d\'entrée). Le produit « ordinateur » correspond à cette définition.', '2025-12-27 12:34:13', '2025-12-27 12:34:13', NULL, NULL, NULL),
(64, 1, 'Tissu coton', 'Non renseigné', 'Non renseigné', '59.01.00.00', 'XI', '59', '75.00', 'Non renseigné', 'Non renseigné', 'Non renseigné', 'METRE', 'RGI – Section XI, Chapitre 59, 59.01/02; tissu coton ordinaire non spécifié comme stratifié ou enduit (voir notes 59.03, 59.07); classement par défaut dans 59.01/02', '2025-12-27 12:35:12', '2025-12-27 12:35:12', NULL, NULL, NULL),
(65, 1, 'Ordinateur (ordinateur personnel / unité centrale avec périphériques)', 'Non renseigné', 'Non renseigné', '8471.49.00.00', 'XVI', '84', '90.00', 'Non renseigné', 'Non renseigné', 'Non renseigné', 'PIÈCE', 'RGI / Note: 2 du n° 8471.49 qui précise que les systèmes informatiques sont des machines automatiques de traitement de l\'information répondant à des critères énoncés (au moins une unité centrale de traitement et une unité d\'entrée). Le produit « ordinateur » correspond à cette définition.', '2025-12-27 12:47:28', '2025-12-27 12:47:28', NULL, NULL, NULL),
(66, 1, 'Ordinateur (ordinateur personnel / unité centrale avec périphériques)', 'Non renseigné', 'Non renseigné', '8471.49.00.00', 'XVI', '84', '90.00', 'Non renseigné', 'Non renseigné', 'Non renseigné', 'PIÈCE', 'RGI / Note: 2 du n° 8471.49 qui précise que les systèmes informatiques sont des machines automatiques de traitement de l\'information répondant à des critères énoncés (au moins une unité centrale de traitement et une unité d\'entrée). Le produit « ordinateur » correspond à cette définition.', '2025-12-27 12:49:59', '2025-12-27 12:49:59', NULL, NULL, NULL),
(67, 1, 'Ordinateur (ordinateur personnel / unité centrale avec périphériques)', 'Non renseigné', 'Non renseigné', '8471.49.00.00', 'XVI', '84', '90.00', 'Non renseigné', 'Non renseigné', 'Non renseigné', 'PIÈCE', 'RGI / Note: 2 du n° 8471.49 qui précise que les systèmes informatiques sont des machines automatiques de traitement de l\'information répondant à des critères énoncés (au moins une unité centrale de traitement et une unité d\'entrée). Le produit « ordinateur » correspond à cette définition.', '2025-12-27 12:54:03', '2025-12-27 12:54:03', NULL, NULL, NULL),
(68, 1, 'Téléphone intelligent (smartphone) ou équivalent dans la catégorie 85.17', 'Non renseigné', 'Non renseigné', '8517.13.00.00', 'XVI', '85', '92.00', 'Non renseigné', 'Non renseigné', 'Non renseigné', 'PIÈCE', 'RGI 5 et note technique: sous-position 8517.13.00.00 correspond explicitement aux téléphones intelligents (smartphones) tels que définis dans le document.', '2025-12-27 13:02:21', '2025-12-27 13:02:21', NULL, NULL, NULL),
(71, 1, 'Ordinateur (ordinateur personnel / unité centrale avec périphériques)', 'Non renseigné', 'Non renseigné', '8471.49.00.00', 'XVI', '84', '90.00', 'Non renseigné', 'Non renseigné', 'Non renseigné', 'PIÈCE', 'RGI / Note: 2 du n° 8471.49 qui précise que les systèmes informatiques sont des machines automatiques de traitement de l\'information répondant à des critères énoncés (au moins une unité centrale de traitement et une unité d\'entrée). Le produit « ordinateur » correspond à cette définition.', '2025-12-27 13:11:16', '2025-12-27 13:11:16', NULL, NULL, NULL),
(72, 1, 'Ordinateur (ordinateur personnel / unité centrale avec périphériques)', 'Non renseigné', 'Non renseigné', '8471.49.00.00', 'XVI', '84', '90.00', 'Non renseigné', 'Non renseigné', 'Non renseigné', 'PIÈCE', 'RGI / Note: 2 du n° 8471.49 qui précise que les systèmes informatiques sont des machines automatiques de traitement de l\'information répondant à des critères énoncés (au moins une unité centrale de traitement et une unité d\'entrée). Le produit « ordinateur » correspond à cette définition.', '2025-12-27 13:13:56', '2025-12-27 13:13:56', NULL, NULL, NULL),
(73, 1, 'Ordinateur (ordinateur personnel / unité centrale avec périphériques)', 'Non renseigné', 'Non renseigné', '8471.49.00.00', 'XVI', '84', '90.00', 'Non renseigné', 'Non renseigné', 'Non renseigné', 'PIÈCE', 'RGI / Note: 2 du n° 8471.49 qui précise que les systèmes informatiques sont des machines automatiques de traitement de l\'information répondant à des critères énoncés (au moins une unité centrale de traitement et une unité d\'entrée). Le produit « ordinateur » correspond à cette définition.', '2025-12-27 13:23:37', '2025-12-27 13:23:37', NULL, NULL, NULL),
(74, 1, 'Ordinateur (ordinateur personnel / unité centrale avec périphériques)', 'Non renseigné', 'Non renseigné', '8471.49.00.00', 'XVI', '84', '90.00', 'Non renseigné', 'Non renseigné', 'Non renseigné', 'PIÈCE', 'RGI / Note: 2 du n° 8471.49 qui précise que les systèmes informatiques sont des machines automatiques de traitement de l\'information répondant à des critères énoncés (au moins une unité centrale de traitement et une unité d\'entrée). Le produit « ordinateur » correspond à cette définition.', '2025-12-27 13:23:57', '2025-12-27 13:23:57', NULL, NULL, NULL),
(75, 1, 'Ordinateur (ordinateur personnel / unité centrale avec périphériques)', 'Non renseigné', 'Non renseigné', '8471.49.00.00', 'XVI', '84', '90.00', 'Non renseigné', 'Non renseigné', 'Non renseigné', 'PIÈCE', 'RGI / Note: 2 du n° 8471.49 qui précise que les systèmes informatiques sont des machines automatiques de traitement de l\'information répondant à des critères énoncés (au moins une unité centrale de traitement et une unité d\'entrée). Le produit « ordinateur » correspond à cette définition.', '2025-12-27 13:24:09', '2025-12-27 13:24:09', NULL, NULL, NULL),
(76, 1, 'Ordinateur (ordinateur personnel / unité centrale avec périphériques)', 'Non renseigné', 'Non renseigné', '8471.49.00.00', 'XVI', '84', '90.00', 'Non renseigné', 'Non renseigné', 'Non renseigné', 'PIÈCE', 'RGI / Note: 2 du n° 8471.49 qui précise que les systèmes informatiques sont des machines automatiques de traitement de l\'information répondant à des critères énoncés (au moins une unité centrale de traitement et une unité d\'entrée). Le produit « ordinateur » correspond à cette définition.', '2025-12-27 13:33:41', '2025-12-27 13:33:41', NULL, NULL, NULL),
(77, 1, 'Ordinateur (ordinateur personnel / unité centrale avec périphériques)', 'Non renseigné', 'Non renseigné', '8471.49.00.00', 'XVI', '84', '90.00', 'Non renseigné', 'Non renseigné', 'Non renseigné', 'PIÈCE', 'RGI / Note: 2 du n° 8471.49 qui précise que les systèmes informatiques sont des machines automatiques de traitement de l\'information répondant à des critères énoncés (au moins une unité centrale de traitement et une unité d\'entrée). Le produit « ordinateur » correspond à cette définition.', '2025-12-27 13:34:01', '2025-12-27 13:34:01', NULL, NULL, NULL),
(78, 1, 'Ordinateur (ordinateur personnel / unité centrale avec périphériques)', 'Non renseigné', 'Non renseigné', '8471.49.00.00', 'XVI', '84', '90.00', 'Non renseigné', 'Non renseigné', 'Non renseigné', 'PIÈCE', 'RGI / Note: 2 du n° 8471.49 qui précise que les systèmes informatiques sont des machines automatiques de traitement de l\'information répondant à des critères énoncés (au moins une unité centrale de traitement et une unité d\'entrée). Le produit « ordinateur » correspond à cette définition.', '2025-12-27 13:34:12', '2025-12-27 13:34:12', NULL, NULL, NULL),
(79, 1, 'Autres téléphones pour réseaux cellulaires ou autres réseaux sans fil', 'Non renseigné', 'Non renseigné', '8517.14.00.00', 'XVI', '85', '95.00', 'Non renseigné', 'Non renseigné', 'Non renseigné', 'PIÈCE', 'Correspondance explicite dans le document: 8517.14.00.00 -- Autres téléphones pour réseaux cellulaires ou autres réseaux sans fil.', '2025-12-27 13:35:51', '2025-12-27 13:35:51', NULL, NULL, NULL),
(80, 1, 'Autres téléphones pour réseaux cellulaires ou autres réseaux sans fil', 'Non renseigné', 'Non renseigné', '8517.14.00.00', 'XVI', '85', '88.00', 'Non renseigné', 'Non renseigné', 'Non renseigné', 'PIÈCE', 'RGI 5 (catégorisation sous 85.17) et sélection de la sous-position adaptée lorsque le produit n’est pas un smartphone (8517.13.00.00) ni une autre catégorie spécifique. Extrait: 8517.14.00.00 -- Autres téléphones pour réseaux cellulaires ou autres réseaux sans fil', '2025-12-27 13:36:41', '2025-12-27 13:36:41', NULL, NULL, NULL),
(81, 1, 'Ordinateur (ordinateur personnel / unité centrale avec périphériques)', 'Non renseigné', 'Non renseigné', '8471.49.00.00', 'XVI', '84', '90.00', 'Non renseigné', 'Non renseigné', 'Non renseigné', 'PIÈCE', 'RGI / Note: 2 du n° 8471.49 qui précise que les systèmes informatiques sont des machines automatiques de traitement de l\'information répondant à des critères énoncés (au moins une unité centrale de traitement et une unité d\'entrée). Le produit « ordinateur » correspond à cette définition.', '2025-12-27 13:48:12', '2025-12-27 13:48:12', NULL, NULL, NULL),
(82, 1, 'Ordinateur (ordinateur personnel / unité centrale avec périphériques)', 'Non renseigné', 'Non renseigné', '8471.49.00.00', 'XVI', '84', '90.00', 'Non renseigné', 'Non renseigné', 'Non renseigné', 'PIÈCE', 'RGI / Note: 2 du n° 8471.49 qui précise que les systèmes informatiques sont des machines automatiques de traitement de l\'information répondant à des critères énoncés (au moins une unité centrale de traitement et une unité d\'entrée). Le produit « ordinateur » correspond à cette définition.', '2025-12-27 13:48:29', '2025-12-27 13:48:29', NULL, NULL, NULL),
(83, 1, 'Ordinateur (ordinateur personnel / unité centrale avec périphériques)', 'Non renseigné', 'Non renseigné', '8471.49.00.00', 'XVI', '84', '90.00', 'Non renseigné', 'Non renseigné', 'Non renseigné', 'PIÈCE', 'RGI / Note: 2 du n° 8471.49 qui précise que les systèmes informatiques sont des machines automatiques de traitement de l\'information répondant à des critères énoncés (au moins une unité centrale de traitement et une unité d\'entrée). Le produit « ordinateur » correspond à cette définition.', '2025-12-27 13:48:36', '2025-12-27 13:48:36', NULL, NULL, NULL),
(84, 1, 'Ordinateur (ordinateur personnel / unité centrale avec périphériques)', 'Non renseigné', 'Non renseigné', '8471.49.00.00', 'XVI', '84', '90.00', 'Non renseigné', 'Non renseigné', 'Non renseigné', 'PIÈCE', 'RGI / Note: 2 du n° 8471.49 qui précise que les systèmes informatiques sont des machines automatiques de traitement de l\'information répondant à des critères énoncés (au moins une unité centrale de traitement et une unité d\'entrée). Le produit « ordinateur » correspond à cette définition.', '2025-12-27 13:59:28', '2025-12-27 13:59:28', NULL, NULL, NULL),
(85, 1, 'Ordinateur (ordinateur personnel / unité centrale avec périphériques)', 'Non renseigné', 'Non renseigné', '8471.49.00.00', 'XVI', '84', '90.00', 'Non renseigné', 'Non renseigné', 'Non renseigné', 'PIÈCE', 'RGI / Note: 2 du n° 8471.49 qui précise que les systèmes informatiques sont des machines automatiques de traitement de l\'information répondant à des critères énoncés (au moins une unité centrale de traitement et une unité d\'entrée). Le produit « ordinateur » correspond à cette définition.', '2025-12-27 13:59:36', '2025-12-27 13:59:36', NULL, NULL, NULL),
(86, 1, 'Ordinateur (ordinateur personnel / unité centrale avec périphériques)', 'Non renseigné', 'Non renseigné', '8471.49.00.00', 'XVI', '84', '90.00', 'Non renseigné', 'Non renseigné', 'Non renseigné', 'PIÈCE', 'RGI / Note: 2 du n° 8471.49 qui précise que les systèmes informatiques sont des machines automatiques de traitement de l\'information répondant à des critères énoncés (au moins une unité centrale de traitement et une unité d\'entrée). Le produit « ordinateur » correspond à cette définition.', '2025-12-27 13:59:41', '2025-12-27 13:59:41', NULL, NULL, NULL),
(87, 1, 'Ordinateur (ordinateur personnel / unité centrale avec périphériques)', 'Non renseigné', 'Non renseigné', '8471.49.00.00', 'XVI', '84', '90.00', 'Non renseigné', 'Non renseigné', 'Non renseigné', 'PIÈCE', 'RGI / Note: 2 du n° 8471.49 qui précise que les systèmes informatiques sont des machines automatiques de traitement de l\'information répondant à des critères énoncés (au moins une unité centrale de traitement et une unité d\'entrée). Le produit « ordinateur » correspond à cette définition.', '2025-12-27 14:02:00', '2025-12-27 14:02:00', NULL, NULL, NULL),
(88, 1, 'Ordinateur (ordinateur personnel / unité centrale avec périphériques)', 'Non renseigné', 'Non renseigné', '8471.49.00.00', 'XVI', '84', '90.00', 'Non renseigné', 'Non renseigné', 'Non renseigné', 'PIÈCE', 'RGI / Note: 2 du n° 8471.49 qui précise que les systèmes informatiques sont des machines automatiques de traitement de l\'information répondant à des critères énoncés (au moins une unité centrale de traitement et une unité d\'entrée). Le produit « ordinateur » correspond à cette définition.', '2025-12-27 14:02:15', '2025-12-27 14:02:15', NULL, NULL, NULL),
(89, 1, 'Ordinateur (ordinateur personnel / unité centrale avec périphériques)', 'Non renseigné', 'Non renseigné', '8471.49.00.00', 'XVI', '84', '90.00', 'Non renseigné', 'Non renseigné', 'Non renseigné', 'PIÈCE', 'RGI / Note: 2 du n° 8471.49 qui précise que les systèmes informatiques sont des machines automatiques de traitement de l\'information répondant à des critères énoncés (au moins une unité centrale de traitement et une unité d\'entrée). Le produit « ordinateur » correspond à cette définition.', '2025-12-27 14:05:39', '2025-12-27 14:05:39', NULL, NULL, NULL),
(90, 1, 'Ordinateur (ordinateur personnel / unité centrale avec périphériques)', 'Non renseigné', 'Non renseigné', '8471.49.00.00', 'XVI', '84', '90.00', 'Non renseigné', 'Non renseigné', 'Non renseigné', 'PIÈCE', 'RGI / Note: 2 du n° 8471.49 qui précise que les systèmes informatiques sont des machines automatiques de traitement de l\'information répondant à des critères énoncés (au moins une unité centrale de traitement et une unité d\'entrée). Le produit « ordinateur » correspond à cette définition.', '2025-12-27 14:09:09', '2025-12-27 14:09:09', NULL, NULL, NULL),
(91, 1, 'Ordinateur (ordinateur personnel / unité centrale avec périphériques)', 'Non renseigné', 'Non renseigné', '8471.49.00.00', 'XVI', '84', '90.00', 'Non renseigné', 'Non renseigné', 'Non renseigné', 'PIÈCE', 'RGI / Note: 2 du n° 8471.49 qui précise que les systèmes informatiques sont des machines automatiques de traitement de l\'information répondant à des critères énoncés (au moins une unité centrale de traitement et une unité d\'entrée). Le produit « ordinateur » correspond à cette définition.', '2025-12-27 14:09:17', '2025-12-27 14:09:17', NULL, NULL, NULL),
(92, 1, 'Ordinateur (ordinateur personnel / unité centrale avec périphériques)', 'Non renseigné', 'Non renseigné', '8471.49.00.00', 'XVI', '84', '90.00', 'Non renseigné', 'Non renseigné', 'Non renseigné', 'PIÈCE', 'RGI / Note: 2 du n° 8471.49 qui précise que les systèmes informatiques sont des machines automatiques de traitement de l\'information répondant à des critères énoncés (au moins une unité centrale de traitement et une unité d\'entrée). Le produit « ordinateur » correspond à cette définition.', '2025-12-27 14:12:43', '2025-12-27 14:12:43', NULL, NULL, NULL),
(93, 1, 'Ordinateur (ordinateur personnel / unité centrale avec périphériques)', 'Non renseigné', 'Non renseigné', '8471.49.00.00', 'XVI', '84', '90.00', 'Non renseigné', 'Non renseigné', 'Non renseigné', 'PIÈCE', 'RGI / Note: 2 du n° 8471.49 qui précise que les systèmes informatiques sont des machines automatiques de traitement de l\'information répondant à des critères énoncés (au moins une unité centrale de traitement et une unité d\'entrée). Le produit « ordinateur » correspond à cette définition.', '2025-12-27 14:12:59', '2025-12-27 14:12:59', NULL, NULL, NULL),
(94, 1, 'Ordinateur (ordinateur personnel / unité centrale avec périphériques)', 'Non renseigné', 'Non renseigné', '8471.49.00.00', 'XVI', '84', '90.00', 'Non renseigné', 'Non renseigné', 'Non renseigné', 'PIÈCE', 'RGI / Note: 2 du n° 8471.49 qui précise que les systèmes informatiques sont des machines automatiques de traitement de l\'information répondant à des critères énoncés (au moins une unité centrale de traitement et une unité d\'entrée). Le produit « ordinateur » correspond à cette définition.', '2025-12-27 14:17:11', '2025-12-27 14:17:11', NULL, NULL, NULL),
(95, 1, 'Ordinateur (ordinateur personnel / unité centrale avec périphériques)', 'Non renseigné', 'Non renseigné', '8471.49.00.00', 'XVI', '84', '90.00', 'Non renseigné', 'Non renseigné', 'Non renseigné', 'PIÈCE', 'RGI / Note: 2 du n° 8471.49 qui précise que les systèmes informatiques sont des machines automatiques de traitement de l\'information répondant à des critères énoncés (au moins une unité centrale de traitement et une unité d\'entrée). Le produit « ordinateur » correspond à cette définition.', '2025-12-27 14:17:20', '2025-12-27 14:17:20', NULL, NULL, NULL),
(96, 1, 'Postes téléphoniques d\'usagers par fil à combinés sans fil', 'Non renseigné', 'Non renseigné', '8517.11.00.00', 'XVI', '85', '90.00', 'Non renseigné', 'Non renseigné', 'Non renseigné', 'PIÈCE', 'Correspond à la description fournie par le TEC/SH sous 8517.11.00.00; RGIs applicables: RGI 1 et RGI 4 pour le classement des postes téléphoniques d\'usagers.', '2025-12-27 14:18:33', '2025-12-27 14:18:33', NULL, NULL, NULL),
(97, 1, 'Ordinateur (ordinateur personnel / unité centrale avec périphériques)', 'Non renseigné', 'Non renseigné', '8471.49.00.00', 'XVI', '84', '90.00', 'Non renseigné', 'Non renseigné', 'Non renseigné', 'PIÈCE', 'RGI / Note: 2 du n° 8471.49 qui précise que les systèmes informatiques sont des machines automatiques de traitement de l\'information répondant à des critères énoncés (au moins une unité centrale de traitement et une unité d\'entrée). Le produit « ordinateur » correspond à cette définition.', '2025-12-27 14:20:38', '2025-12-27 14:20:38', NULL, NULL, NULL),
(98, 1, 'Ordinateur (ordinateur personnel / unité centrale avec périphériques)', 'Non renseigné', 'Non renseigné', '8471.49.00.00', 'XVI', '84', '90.00', 'Non renseigné', 'Non renseigné', 'Non renseigné', 'PIÈCE', 'RGI / Note: 2 du n° 8471.49 qui précise que les systèmes informatiques sont des machines automatiques de traitement de l\'information répondant à des critères énoncés (au moins une unité centrale de traitement et une unité d\'entrée). Le produit « ordinateur » correspond à cette définition.', '2025-12-27 14:28:08', '2025-12-27 14:28:08', NULL, NULL, NULL),
(99, 1, 'Ordinateur (ordinateur personnel / unité centrale avec périphériques)', 'Non renseigné', 'Non renseigné', '8471.49.00.00', 'XVI', '84', '90.00', 'Non renseigné', 'Non renseigné', 'Non renseigné', 'PIÈCE', 'RGI / Note: 2 du n° 8471.49 qui précise que les systèmes informatiques sont des machines automatiques de traitement de l\'information répondant à des critères énoncés (au moins une unité centrale de traitement et une unité d\'entrée). Le produit « ordinateur » correspond à cette définition.', '2025-12-27 14:28:15', '2025-12-27 14:28:15', NULL, NULL, NULL),
(100, 1, 'Ordinateur (ordinateur personnel / unité centrale avec périphériques)', 'Non renseigné', 'Non renseigné', '8471.49.00.00', 'XVI', '84', '90.00', 'Non renseigné', 'Non renseigné', 'Non renseigné', 'PIÈCE', 'RGI / Note: 2 du n° 8471.49 qui précise que les systèmes informatiques sont des machines automatiques de traitement de l\'information répondant à des critères énoncés (au moins une unité centrale de traitement et une unité d\'entrée). Le produit « ordinateur » correspond à cette définition.', '2025-12-27 14:29:08', '2025-12-27 14:29:08', NULL, NULL, NULL),
(101, 1, 'Ordinateur (ordinateur personnel / unité centrale avec périphériques)', 'Non renseigné', 'Non renseigné', '8471.49.00.00', 'XVI', '84', '90.00', 'Non renseigné', 'Non renseigné', 'Non renseigné', 'PIÈCE', 'RGI / Note: 2 du n° 8471.49 qui précise que les systèmes informatiques sont des machines automatiques de traitement de l\'information répondant à des critères énoncés (au moins une unité centrale de traitement et une unité d\'entrée). Le produit « ordinateur » correspond à cette définition.', '2025-12-27 14:38:05', '2025-12-27 14:38:05', NULL, NULL, NULL),
(102, 1, 'Ordinateur (ordinateur personnel / unité centrale avec périphériques)', 'Non renseigné', 'Non renseigné', '8471.49.00.00', 'XVI', '84', '90.00', 'Non renseigné', 'Non renseigné', 'Non renseigné', 'PIÈCE', 'RGI / Note: 2 du n° 8471.49 qui précise que les systèmes informatiques sont des machines automatiques de traitement de l\'information répondant à des critères énoncés (au moins une unité centrale de traitement et une unité d\'entrée). Le produit « ordinateur » correspond à cette définition.', '2025-12-27 14:38:11', '2025-12-27 14:38:11', NULL, NULL, NULL),
(103, 1, 'Ordinateur (ordinateur personnel / unité centrale avec périphériques)', 'Non renseigné', 'Non renseigné', '8471.49.00.00', 'XVI', '84', '90.00', 'Non renseigné', 'Non renseigné', 'Non renseigné', 'PIÈCE', 'RGI / Note: 2 du n° 8471.49 qui précise que les systèmes informatiques sont des machines automatiques de traitement de l\'information répondant à des critères énoncés (au moins une unité centrale de traitement et une unité d\'entrée). Le produit « ordinateur » correspond à cette définition.', '2025-12-27 14:38:16', '2025-12-27 14:38:16', NULL, NULL, NULL),
(104, 1, 'Téléphone mobile / smartphone', 'Non renseigné', 'USA', '8517.13.00.00', 'XVI', '85', '92.00', 'Non renseigné', 'Non renseigné', 'Non renseigné', 'PIÈCE', 'RGI 5 et 85.17 explicitent les postes téléphoniques et téléphones intelligents; 8517.13.00.00 correspond précisément aux téléphones intelligents (smartphones). Déduction limitée par l’absence des taux dans le document.', '2025-12-27 14:38:54', '2025-12-27 14:38:54', NULL, NULL, NULL),
(105, 1, 'Ordinateur (ordinateur personnel / unité centrale avec périphériques)', 'Non renseigné', 'Non renseigné', '8471.49.00.00', 'XVI', '84', '90.00', 'Non renseigné', 'Non renseigné', 'Non renseigné', 'PIÈCE', 'RGI / Note: 2 du n° 8471.49 qui précise que les systèmes informatiques sont des machines automatiques de traitement de l\'information répondant à des critères énoncés (au moins une unité centrale de traitement et une unité d\'entrée). Le produit « ordinateur » correspond à cette définition.', '2025-12-27 14:40:07', '2025-12-27 14:40:07', NULL, NULL, NULL),
(106, 1, 'Ordinateur (ordinateur personnel / unité centrale avec périphériques)', 'Non renseigné', 'Non renseigné', '8471.49.00.00', 'XVI', '84', '90.00', 'Non renseigné', 'Non renseigné', 'Non renseigné', 'PIÈCE', 'RGI / Note: 2 du n° 8471.49 qui précise que les systèmes informatiques sont des machines automatiques de traitement de l\'information répondant à des critères énoncés (au moins une unité centrale de traitement et une unité d\'entrée). Le produit « ordinateur » correspond à cette définition.', '2025-12-27 14:43:54', '2025-12-27 14:43:54', NULL, NULL, NULL),
(107, 1, 'Ordinateur (ordinateur personnel / unité centrale avec périphériques)', 'Non renseigné', 'Non renseigné', '8471.49.00.00', 'XVI', '84', '90.00', 'Non renseigné', 'Non renseigné', 'Non renseigné', 'PIÈCE', 'RGI / Note: 2 du n° 8471.49 qui précise que les systèmes informatiques sont des machines automatiques de traitement de l\'information répondant à des critères énoncés (au moins une unité centrale de traitement et une unité d\'entrée). Le produit « ordinateur » correspond à cette définition.', '2025-12-27 14:55:29', '2025-12-27 14:55:29', NULL, NULL, NULL),
(108, 1, 'Ordinateur (ordinateur personnel / unité centrale avec périphériques)', 'Non renseigné', 'Non renseigné', '8471.49.00.00', 'XVI', '84', '90.00', 'Non renseigné', 'Non renseigné', 'Non renseigné', 'PIÈCE', 'RGI / Note: 2 du n° 8471.49 qui précise que les systèmes informatiques sont des machines automatiques de traitement de l\'information répondant à des critères énoncés (au moins une unité centrale de traitement et une unité d\'entrée). Le produit « ordinateur » correspond à cette définition.', '2025-12-27 14:55:34', '2025-12-27 14:55:34', NULL, NULL, NULL),
(109, 1, 'Ordinateur (ordinateur personnel / unité centrale avec périphériques)', 'Non renseigné', 'Non renseigné', '8471.49.00.00', 'XVI', '84', '90.00', 'Non renseigné', 'Non renseigné', 'Non renseigné', 'PIÈCE', 'RGI / Note: 2 du n° 8471.49 qui précise que les systèmes informatiques sont des machines automatiques de traitement de l\'information répondant à des critères énoncés (au moins une unité centrale de traitement et une unité d\'entrée). Le produit « ordinateur » correspond à cette définition.', '2025-12-27 14:56:20', '2025-12-27 14:56:20', NULL, NULL, NULL),
(110, 1, 'Postes téléphoniques d\'usagers par fil à combinés sans fil', 'Non renseigné', 'Non renseigné', '8517.11.00.00', 'XVI', '85', '90.00', 'Non renseigné', 'Non renseigné', 'Non renseigné', 'PIÈCE', 'Correspond à la description fournie par le TEC/SH sous 8517.11.00.00; RGIs applicables: RGI 1 et RGI 4 pour le classement des postes téléphoniques d\'usagers.', '2025-12-27 14:56:37', '2025-12-27 14:56:37', NULL, NULL, NULL),
(111, 1, 'Postes téléphoniques d\'usagers par fil à combinés sans fil', 'Non renseigné', 'Non renseigné', '8517.11.00.00', 'XVI', '85', '90.00', 'Non renseigné', 'Non renseigné', 'Non renseigné', 'PIÈCE', 'Correspond à la description fournie par le TEC/SH sous 8517.11.00.00; RGIs applicables: RGI 1 et RGI 4 pour le classement des postes téléphoniques d\'usagers.', '2025-12-27 14:56:48', '2025-12-27 14:56:48', NULL, NULL, NULL);

-- --------------------------------------------------------

--
-- Table structure for table `historique`
--

CREATE TABLE `historique` (
  `id_historique` int(11) NOT NULL,
  `classification_id` int(11) NOT NULL,
  `user_id` int(11) NOT NULL,
  `action` enum('creation','modification','validation','rejet') COLLATE utf8mb4_unicode_ci NOT NULL,
  `ancien_code_tarifaire` varchar(20) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `nouveau_code_tarifaire` varchar(20) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `ancien_statut` varchar(20) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `nouveau_statut` varchar(20) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `commentaire` text COLLATE utf8mb4_unicode_ci,
  `date_action` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- --------------------------------------------------------

--
-- Table structure for table `users`
--

CREATE TABLE `users` (
  `user_id` int(11) NOT NULL,
  `nom_user` varchar(100) COLLATE utf8mb4_unicode_ci NOT NULL,
  `identifiant_user` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL,
  `email` varchar(150) COLLATE utf8mb4_unicode_ci NOT NULL,
  `password_hash` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT 'Hash bcrypt',
  `statut` enum('actif','inactif','suspendu') COLLATE utf8mb4_unicode_ci DEFAULT 'actif',
  `is_admin` tinyint(1) DEFAULT '0',
  `date_creation` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `derniere_connexion` timestamp NULL DEFAULT NULL,
  `table_cleared` tinyint(1) DEFAULT '0'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

--
-- Dumping data for table `users`
--

INSERT INTO `users` (`user_id`, `nom_user`, `identifiant_user`, `email`, `password_hash`, `statut`, `is_admin`, `date_creation`, `derniere_connexion`, `table_cleared`) VALUES
(1, 'Administrateur Système', 'admin', 'admin@douane.ci', '$2y$10$vMJTyG/p853epmwAVWXtB.IuW9m1edNeb3KCG3KyAKcYUU9.8WK02', 'actif', 1, '2025-12-13 13:58:38', '2025-12-27 14:59:06', 1),
(2, 'Test User', 'test.user', 'test.user@douane.ci', '$2b$12$aA0Im/GKA/.mgV/zxAS.2.ZaPCNcolGOiv59OhPuQPr75DcKMzXBO', 'actif', 0, '2025-12-13 17:16:49', NULL, 0),
(3, 'Test Admin', 'test.admin', 'test.admin@douane.ci', '$2b$12$h3y17UksjNqfhLXyEv93NOn5xkHc4ymqobOOyhhlXILVE1GjBbq5a', 'actif', 1, '2025-12-13 17:16:50', NULL, 0),
(4, 'samuel', '1234567X', 'samuel@douanier.ci', '$2b$12$ZEEO9LRynrdVx/bBXSO5E.hrEYpnHw3ns5pjA2ilMhVJPdHH9trPW', 'actif', 1, '2025-12-13 17:18:05', NULL, 0);

-- --------------------------------------------------------

--
-- Table structure for table `user_table_products`
--

CREATE TABLE `user_table_products` (
  `id` int(11) NOT NULL,
  `user_id` int(11) NOT NULL,
  `classification_id` int(11) NOT NULL,
  `display_order` int(11) DEFAULT '0',
  `created_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- --------------------------------------------------------

--
-- Stand-in structure for view `vue_classifications_completes`
-- (See below for the actual view)
--
CREATE TABLE `vue_classifications_completes` (
);

-- --------------------------------------------------------

--
-- Structure for view `vue_classifications_completes`
--
DROP TABLE IF EXISTS `vue_classifications_completes`;

CREATE ALGORITHM=UNDEFINED DEFINER=`root`@`localhost` SQL SECURITY DEFINER VIEW `vue_classifications_completes`  AS SELECT `c`.`id` AS `id`, `c`.`description_produit` AS `description_produit`, `c`.`valeur_produit` AS `valeur_produit`, `c`.`origine_produit` AS `origine_produit`, `c`.`code_tarifaire` AS `code_tarifaire`, `c`.`section` AS `section`, `c`.`chapitre` AS `chapitre`, `c`.`confidence_score` AS `confidence_score`, `c`.`taux_dd` AS `taux_dd`, `c`.`taux_rs` AS `taux_rs`, `c`.`taux_tva` AS `taux_tva`, `c`.`unite_mesure` AS `unite_mesure`, `c`.`justification` AS `justification`, `c`.`statut_validation` AS `statut_validation`, `c`.`date_classification` AS `date_classification`, `c`.`date_modification` AS `date_modification`, `u`.`nom_user` AS `nom_classificateur`, `u`.`identifiant_user` AS `identifiant_classificateur`, `uv`.`nom_user` AS `nom_validateur`, `uv`.`identifiant_user` AS `identifiant_validateur`, `c`.`date_validation` AS `date_validation` FROM ((`classifications` `c` join `users` `u` on((`c`.`user_id` = `u`.`user_id`))) left join `users` `uv` on((`c`.`id_validateur` = `uv`.`user_id`)))  ;

--
-- Indexes for dumped tables
--

--
-- Indexes for table `classifications`
--
ALTER TABLE `classifications`
  ADD PRIMARY KEY (`id`),
  ADD KEY `idx_user` (`user_id`),
  ADD KEY `idx_date` (`date_classification`),
  ADD KEY `idx_code_tarifaire` (`code_tarifaire`),
  ADD KEY `idx_section` (`section`),
  ADD KEY `idx_query_hash` (`user_query_hash`),
  ADD KEY `idx_feedback_rating` (`feedback_rating`);

--
-- Indexes for table `historique`
--
ALTER TABLE `historique`
  ADD PRIMARY KEY (`id_historique`),
  ADD KEY `idx_classification` (`classification_id`),
  ADD KEY `idx_user` (`user_id`),
  ADD KEY `idx_date` (`date_action`);

--
-- Indexes for table `users`
--
ALTER TABLE `users`
  ADD PRIMARY KEY (`user_id`),
  ADD UNIQUE KEY `uk_identifiant` (`identifiant_user`),
  ADD UNIQUE KEY `uk_email` (`email`),
  ADD KEY `idx_statut` (`statut`);

--
-- Indexes for table `user_table_products`
--
ALTER TABLE `user_table_products`
  ADD PRIMARY KEY (`id`),
  ADD UNIQUE KEY `unique_user_classification` (`user_id`,`classification_id`),
  ADD KEY `idx_user_id` (`user_id`),
  ADD KEY `idx_classification_id` (`classification_id`);

--
-- AUTO_INCREMENT for dumped tables
--

--
-- AUTO_INCREMENT for table `classifications`
--
ALTER TABLE `classifications`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=112;

--
-- AUTO_INCREMENT for table `historique`
--
ALTER TABLE `historique`
  MODIFY `id_historique` int(11) NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT for table `users`
--
ALTER TABLE `users`
  MODIFY `user_id` int(11) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=5;

--
-- AUTO_INCREMENT for table `user_table_products`
--
ALTER TABLE `user_table_products`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT;

--
-- Constraints for dumped tables
--

--
-- Constraints for table `classifications`
--
ALTER TABLE `classifications`
  ADD CONSTRAINT `fk_classifications_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`user_id`) ON UPDATE CASCADE;

--
-- Constraints for table `historique`
--
ALTER TABLE `historique`
  ADD CONSTRAINT `fk_historique_classification` FOREIGN KEY (`classification_id`) REFERENCES `classifications` (`id`) ON DELETE CASCADE ON UPDATE CASCADE,
  ADD CONSTRAINT `fk_historique_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`user_id`) ON UPDATE CASCADE;

--
-- Constraints for table `user_table_products`
--
ALTER TABLE `user_table_products`
  ADD CONSTRAINT `user_table_products_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`user_id`) ON DELETE CASCADE,
  ADD CONSTRAINT `user_table_products_ibfk_2` FOREIGN KEY (`classification_id`) REFERENCES `classifications` (`id`) ON DELETE CASCADE;
COMMIT;

/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
