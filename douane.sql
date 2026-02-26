-- phpMyAdmin SQL Dump
-- version 5.1.2
-- https://www.phpmyadmin.net/
--
-- Host: localhost:4240
-- Generation Time: Aug 13, 2025 at 12:06 PM
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
-- Database: `douane`
--

DELIMITER $$
--
-- Procedures
--
CREATE DEFINER=`root`@`localhost` PROCEDURE `GetUserStatistics` (IN `p_user_id` INT)   BEGIN
    SELECT 
        u.nom_user,
        u.identifiant_user,
        u.nombre_produits_classes,
        COUNT(p.id_produit) as total_classifications,
        SUM(CASE WHEN p.statut_validation = 'valide' THEN 1 ELSE 0 END) as validees,
        SUM(CASE WHEN p.statut_validation = 'en_attente' THEN 1 ELSE 0 END) as en_attente,
        SUM(CASE WHEN p.statut_validation = 'rejete' THEN 1 ELSE 0 END) as rejetees,
        SUM(p.valeur_declaree) as valeur_totale,
        AVG(p.confidence_score) as confidence_moyenne
    FROM User u
    LEFT JOIN Produits p ON u.user_id = p.user_id
    WHERE u.user_id = p_user_id
    GROUP BY u.user_id, u.nom_user, u.identifiant_user, u.nombre_produits_classes;
END$$

CREATE DEFINER=`root`@`localhost` PROCEDURE `NettoyerCacheCEDEO` ()   BEGIN
    DELETE FROM cedeo_cache_classifications 
    WHERE date_derniere_utilisation < DATE_SUB(NOW(), INTERVAL 30 DAY)
    AND nombre_utilisations < 5;
END$$

CREATE DEFINER=`root`@`localhost` PROCEDURE `ValidateProduct` (IN `p_product_id` INT, IN `p_validator_id` INT)   BEGIN
    DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
        ROLLBACK;
        RESIGNAL;
    END;
    
    START TRANSACTION;
    
    UPDATE Produits 
    SET statut_validation = 'valide',
        date_modification = CURRENT_TIMESTAMP
    WHERE id_produit = p_product_id;
    
    INSERT INTO Historique_Classifications (
        id_produit, user_id, action_effectuee, commentaire_historique
    ) VALUES (
        p_product_id, p_validator_id, 'validation', 
        CONCAT('Produit validé par utilisateur ID: ', p_validator_id)
    );
    
    COMMIT;
END$$

DELIMITER ;

-- --------------------------------------------------------

--
-- Table structure for table `cedeo_cache_classifications`
--

CREATE TABLE `cedeo_cache_classifications` (
  `id_cache` int(11) NOT NULL,
  `produit_recherche` varchar(255) NOT NULL,
  `produit_normalise` varchar(255) NOT NULL,
  `code_tarifaire_trouve` varchar(20) NOT NULL,
  `description_trouvee` text,
  `taux_imposition` decimal(5,2) NOT NULL,
  `score_confiance` decimal(5,2) DEFAULT NULL,
  `methode_recherche` enum('exact','keyword','fuzzy') NOT NULL,
  `nombre_utilisations` int(11) DEFAULT '1',
  `date_derniere_utilisation` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  `date_creation` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- --------------------------------------------------------

--
-- Table structure for table `cedeo_chapitres`
--

CREATE TABLE `cedeo_chapitres` (
  `id_chapitre` int(11) NOT NULL,
  `code_chapitre` varchar(5) NOT NULL,
  `titre_chapitre` text NOT NULL,
  `description_chapitre` text,
  `code_section` varchar(5) NOT NULL,
  `taux_chapitre` decimal(5,2) DEFAULT NULL,
  `date_creation` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- --------------------------------------------------------

--
-- Table structure for table `cedeo_codes_tarifaires`
--

CREATE TABLE `cedeo_codes_tarifaires` (
  `id_code` int(11) NOT NULL,
  `code_tarifaire` varchar(20) NOT NULL,
  `description_produit` text NOT NULL,
  `code_chapitre` varchar(5) NOT NULL,
  `code_section` varchar(5) NOT NULL,
  `taux_imposition` decimal(5,2) NOT NULL,
  `unite_mesure` varchar(20) DEFAULT 'unité',
  `notes_specifiques` text,
  `date_creation` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- --------------------------------------------------------

--
-- Table structure for table `cedeo_mots_cles`
--

CREATE TABLE `cedeo_mots_cles` (
  `id_mot_cle` int(11) NOT NULL,
  `mot_cle` varchar(100) NOT NULL,
  `code_tarifaire` varchar(20) NOT NULL,
  `poids_recherche` int(11) DEFAULT '1',
  `date_creation` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- --------------------------------------------------------

--
-- Table structure for table `cedeo_sections`
--

CREATE TABLE `cedeo_sections` (
  `id_section` int(11) NOT NULL,
  `code_section` varchar(5) NOT NULL,
  `titre_section` text NOT NULL,
  `description_section` text,
  `taux_moyen` decimal(5,2) DEFAULT NULL,
  `date_creation` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- --------------------------------------------------------

--
-- Table structure for table `historique_classifications`
--

CREATE TABLE `historique_classifications` (
  `id_historique` int(11) NOT NULL,
  `id_produit` int(11) NOT NULL,
  `user_id` int(11) NOT NULL,
  `action_effectuee` enum('creation','modification','validation','rejet') NOT NULL,
  `ancienne_section` varchar(10) DEFAULT NULL,
  `nouvelle_section` varchar(10) DEFAULT NULL,
  `ancien_taux` decimal(5,2) DEFAULT NULL,
  `nouveau_taux` decimal(5,2) DEFAULT NULL,
  `commentaire_historique` text,
  `date_action` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- --------------------------------------------------------

--
-- Table structure for table `produits`
--

CREATE TABLE `produits` (
  `id_produit` int(11) NOT NULL,
  `origine_produit` varchar(100) DEFAULT NULL,
  `description_produit` text NOT NULL,
  `numero_serie` varchar(50) DEFAULT NULL,
  `is_groupe` tinyint(1) DEFAULT '0',
  `nombre_produits` int(11) DEFAULT '1',
  `taux_imposition` decimal(5,2) DEFAULT '0.00',
  `section_produit` varchar(5) DEFAULT NULL,
  `sous_section_produit` varchar(10) DEFAULT NULL,
  `user_id` int(11) DEFAULT '5',
  `statut_validation` enum('en_attente','valide','rejete') DEFAULT 'en_attente',
  `code_tarifaire` varchar(20) DEFAULT NULL,
  `valeur_declaree` decimal(10,2) DEFAULT '0.00',
  `poids_kg` decimal(8,2) DEFAULT '0.00',
  `unite_mesure` varchar(20) DEFAULT 'unité',
  `commentaires` text,
  `confidence_score` decimal(5,2) DEFAULT NULL,
  `methode_classification` enum('automatique','manuelle','ai') DEFAULT 'automatique',
  `date_classification` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `date_modification` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

--
-- Dumping data for table `produits`
--

INSERT INTO `produits` (`id_produit`, `origine_produit`, `description_produit`, `numero_serie`, `is_groupe`, `nombre_produits`, `taux_imposition`, `section_produit`, `sous_section_produit`, `user_id`, `statut_validation`, `code_tarifaire`, `valeur_declaree`, `poids_kg`, `unite_mesure`, `commentaires`, `confidence_score`, `methode_classification`, `date_classification`, `date_modification`) VALUES
(1, 'Test', 'Riz blanc test', NULL, 0, 1, '8.75', 'II', NULL, 5, 'valide', '1006.30.00.00', '0.00', '0.00', 'unité', 'Produit de test initial', '95.00', 'ai', '2025-08-07 11:51:01', '2025-08-07 11:51:01'),
(2, 'Test', 'Viande de bœuf test', NULL, 0, 1, '10.50', 'I', NULL, 5, 'valide', '0201.20.00.00', '0.00', '0.00', 'unité', 'Produit de test initial', '88.50', 'automatique', '2025-08-07 11:51:01', '2025-08-07 11:51:01'),
(3, 'Non spécifié', 'riz', NULL, 0, 1, '8.75', 'II', NULL, 5, 'valide', '1006.30.00.00', '0.00', '0.00', 'unité', 'Classification automatique - Confiance: 85%', NULL, 'automatique', '2025-08-07 11:51:39', '2025-08-07 11:51:39'),
(4, 'Non spécifié', 'riz', NULL, 0, 1, '8.75', 'II', NULL, 5, 'valide', '1006.30.00.00', '0.00', '0.00', 'unité', 'Classification automatique - Confiance: 85%', NULL, 'automatique', '2025-08-07 11:51:39', '2025-08-07 11:51:39'),
(5, 'Non spécifié', 'cacao', NULL, 0, 1, '15.75', 'XX', NULL, 5, 'en_attente', '9999.00.00.00', '0.00', '0.00', 'unité', 'Classification automatique - Confiance: 60%', NULL, 'automatique', '2025-08-07 14:22:50', '2025-08-07 14:22:50'),
(6, 'Non spécifié', 'cacao', NULL, 0, 1, '15.75', 'XX', NULL, 5, 'en_attente', '9999.00.00.00', '0.00', '0.00', 'unité', 'Classification automatique - Confiance: 60%', NULL, 'automatique', '2025-08-07 14:22:50', '2025-08-07 14:22:50'),
(7, 'Non spécifié', 'riz', NULL, 0, 1, '8.75', 'II', NULL, 5, 'valide', '1006.30.00.00', '0.00', '0.00', 'unité', 'Classification automatique - Confiance: 85%', NULL, 'automatique', '2025-08-07 14:46:35', '2025-08-07 14:46:35'),
(8, 'Non spécifié', 'riz', NULL, 0, 1, '8.75', 'II', NULL, 5, 'valide', '1006.30.00.00', '0.00', '0.00', 'unité', 'Classification automatique - Confiance: 85%', NULL, 'automatique', '2025-08-07 14:46:35', '2025-08-07 14:46:35'),
(9, 'Non spécifié', 'voiture', NULL, 0, 1, '20.75', 'XVII', NULL, 5, 'valide', '8703.23.00.00', '0.00', '0.00', 'unité', 'Classification automatique - Confiance: 85%', NULL, 'automatique', '2025-08-07 15:41:28', '2025-08-07 15:41:28'),
(10, 'Non spécifié', 'voiture', NULL, 0, 1, '20.75', 'XVII', NULL, 5, 'valide', '8703.23.00.00', '0.00', '0.00', 'unité', 'Classification automatique - Confiance: 85%', NULL, 'automatique', '2025-08-07 15:41:28', '2025-08-07 15:41:28'),
(11, 'Non spécifié', 'riz', NULL, 0, 1, '8.75', 'II', NULL, 5, 'valide', '1006.30.00.00', '0.00', '0.00', 'unité', 'Classification automatique - Confiance: 85%', NULL, 'automatique', '2025-08-07 18:39:02', '2025-08-07 18:39:02'),
(12, 'Non spécifié', 'riz', NULL, 0, 1, '8.75', 'II', NULL, 5, 'valide', '1006.30.00.00', '0.00', '0.00', 'unité', 'Classification automatique - Confiance: 85%', NULL, 'automatique', '2025-08-07 18:39:02', '2025-08-07 18:39:02'),
(13, 'Non spécifié', 'riz\n', NULL, 0, 1, '8.75', 'II', NULL, 5, 'valide', '1006.30.00.00', '0.00', '0.00', 'unité', 'Classification automatique - Confiance: 85%', NULL, 'automatique', '2025-08-07 18:57:51', '2025-08-07 18:57:51'),
(15, 'Non spécifié', 'riz', NULL, 0, 1, '8.75', 'II', NULL, 5, 'valide', '1006.30.00.00', '0.00', '0.00', 'unité', 'Classification automatique - Confiance: 85%', NULL, 'automatique', '2025-08-07 18:58:46', '2025-08-07 18:58:46'),
(16, 'Non spécifié', 'riz', NULL, 0, 1, '8.75', 'II', NULL, 5, 'valide', '1006.30.00.00', '0.00', '0.00', 'unité', 'Classification automatique - Confiance: 85%', NULL, 'automatique', '2025-08-07 18:58:46', '2025-08-07 18:58:46'),
(17, 'Non spécifié', 'voitures', NULL, 0, 1, '20.75', 'XVII', NULL, 5, 'valide', '8703.23.00.00', '0.00', '0.00', 'unité', 'Classification automatique - Confiance: 85%', NULL, 'automatique', '2025-08-07 18:59:21', '2025-08-07 18:59:21'),
(18, 'Non spécifié', 'voitures', NULL, 0, 1, '20.75', 'XVII', NULL, 5, 'valide', '8703.23.00.00', '0.00', '0.00', 'unité', 'Classification automatique - Confiance: 85%', NULL, 'automatique', '2025-08-07 18:59:22', '2025-08-07 18:59:22'),
(19, 'Non spécifié', 'riz', NULL, 0, 1, '8.75', 'II', NULL, 5, 'valide', '1006.30.00.00', '0.00', '0.00', 'unité', 'Classification automatique - Confiance: 85%', NULL, 'automatique', '2025-08-07 19:07:44', '2025-08-07 19:07:44'),
(20, 'Non spécifié', 'riz', NULL, 0, 1, '8.75', 'II', NULL, 5, 'valide', '1006.30.00.00', '0.00', '0.00', 'unité', 'Classification automatique - Confiance: 85%', NULL, 'automatique', '2025-08-07 19:07:44', '2025-08-07 19:07:44'),
(21, 'Non spécifié', 'riz', NULL, 0, 1, '8.75', 'II', NULL, 5, 'valide', '1006.30.00.00', '0.00', '0.00', 'unité', 'Classification automatique - Confiance: 85%', NULL, 'automatique', '2025-08-07 19:08:32', '2025-08-07 19:08:32'),
(22, 'Non spécifié', 'riz', NULL, 0, 1, '8.75', 'II', NULL, 5, 'valide', '1006.30.00.00', '0.00', '0.00', 'unité', 'Classification automatique - Confiance: 85%', NULL, 'automatique', '2025-08-07 19:08:32', '2025-08-07 19:08:32'),
(23, 'Non spécifié', 'riz', NULL, 0, 1, '8.75', 'II', NULL, 5, 'valide', '1006.30.00.00', '0.00', '0.00', 'unité', 'Classification automatique - Confiance: 85%', NULL, 'automatique', '2025-08-07 19:08:33', '2025-08-07 19:08:33'),
(24, 'Non spécifié', 'riz', NULL, 0, 1, '8.75', 'II', NULL, 5, 'valide', '1006.30.00.00', '0.00', '0.00', 'unité', 'Classification automatique - Confiance: 85%', NULL, 'automatique', '2025-08-07 19:08:33', '2025-08-07 19:08:33'),
(25, 'Non spécifié', 'riz', NULL, 0, 1, '8.75', 'II', NULL, 5, 'valide', '1006.30.00.00', '0.00', '0.00', 'unité', 'Classification automatique - Confiance: 85%', NULL, 'automatique', '2025-08-07 19:08:33', '2025-08-07 19:08:33'),
(26, 'Non spécifié', 'riz', NULL, 0, 1, '8.75', 'II', NULL, 5, 'valide', '1006.30.00.00', '0.00', '0.00', 'unité', 'Classification automatique - Confiance: 85%', NULL, 'automatique', '2025-08-07 19:08:33', '2025-08-07 19:08:33'),
(27, 'Non spécifié', 'riz', NULL, 0, 1, '8.75', 'II', NULL, 5, 'valide', '1006.30.00.00', '0.00', '0.00', 'unité', 'Classification automatique - Confiance: 85%', NULL, 'automatique', '2025-08-07 19:08:33', '2025-08-07 19:08:33'),
(28, 'Non spécifié', 'riz', NULL, 0, 1, '8.75', 'II', NULL, 5, 'valide', '1006.30.00.00', '0.00', '0.00', 'unité', 'Classification automatique - Confiance: 85%', NULL, 'automatique', '2025-08-07 19:08:33', '2025-08-07 19:08:33'),
(29, 'Non spécifié', 'riz', NULL, 0, 1, '8.75', 'II', NULL, 5, 'valide', '1006.30.00.00', '0.00', '0.00', 'unité', 'Classification automatique - Confiance: 85%', NULL, 'automatique', '2025-08-07 19:08:53', '2025-08-07 19:08:53'),
(30, 'Non spécifié', 'riz', NULL, 0, 1, '8.75', 'II', NULL, 5, 'valide', '1006.30.00.00', '0.00', '0.00', 'unité', 'Classification automatique - Confiance: 85%', NULL, 'automatique', '2025-08-07 19:08:53', '2025-08-07 19:08:53'),
(31, 'Non spécifié', 'riz', NULL, 0, 1, '8.75', 'II', NULL, 5, 'valide', '1006.30.00.00', '0.00', '0.00', 'unité', 'Classification automatique - Confiance: 85%', NULL, 'automatique', '2025-08-07 19:10:24', '2025-08-07 19:10:24'),
(32, 'Non spécifié', 'riz', NULL, 0, 1, '8.75', 'II', NULL, 5, 'valide', '1006.30.00.00', '0.00', '0.00', 'unité', 'Classification automatique - Confiance: 85%', NULL, 'automatique', '2025-08-07 19:10:24', '2025-08-07 19:10:24'),
(33, 'Non spécifié', 'riz', NULL, 0, 1, '8.75', 'II', NULL, 5, 'valide', '1006.30.00.00', '0.00', '0.00', 'unité', 'Classification automatique - Confiance: 85%', NULL, 'automatique', '2025-08-07 19:10:52', '2025-08-07 19:10:52'),
(35, 'Non spécifié', 'riz', NULL, 0, 1, '8.75', 'II', NULL, 5, 'valide', '1006.30.00.00', '0.00', '0.00', 'unité', 'Classification automatique - Confiance: 85%', NULL, 'automatique', '2025-08-07 19:12:36', '2025-08-07 19:12:36'),
(36, 'Non spécifié', 'riz', NULL, 0, 1, '8.75', 'II', NULL, 5, 'valide', '1006.30.00.00', '0.00', '0.00', 'unité', 'Classification automatique - Confiance: 85%', NULL, 'automatique', '2025-08-07 19:12:36', '2025-08-07 19:12:36'),
(37, 'Non spécifié', 'riz', NULL, 0, 1, '8.75', 'II', NULL, 5, 'valide', '1006.30.00.00', '0.00', '0.00', 'unité', 'Classification automatique - Confiance: 85%', NULL, 'automatique', '2025-08-07 19:13:38', '2025-08-07 19:13:38'),
(38, 'Non spécifié', 'riz', NULL, 0, 1, '8.75', 'II', NULL, 5, 'valide', '1006.30.00.00', '0.00', '0.00', 'unité', 'Classification automatique - Confiance: 85%', NULL, 'automatique', '2025-08-07 19:13:38', '2025-08-07 19:13:38'),
(39, 'Non spécifié', 'riz', NULL, 0, 1, '8.75', 'II', NULL, 5, 'valide', '1006.30.00.00', '0.00', '0.00', 'unité', 'Classification automatique - Confiance: 85%', NULL, 'automatique', '2025-08-07 19:22:39', '2025-08-07 19:22:39'),
(40, 'Non spécifié', 'riz', NULL, 0, 1, '8.75', 'II', NULL, 5, 'valide', '1006.30.00.00', '0.00', '0.00', 'unité', 'Classification automatique - Confiance: 85%', NULL, 'automatique', '2025-08-07 19:22:39', '2025-08-07 19:22:39'),
(41, 'Non spécifié', 'riz', NULL, 0, 1, '8.75', 'II', NULL, 5, 'valide', '1006.30.00.00', '0.00', '0.00', 'unité', 'Classification automatique - Confiance: 85%', NULL, 'automatique', '2025-08-07 19:27:28', '2025-08-07 19:27:28'),
(42, 'Non spécifié', 'riz', NULL, 0, 1, '8.75', 'II', NULL, 5, 'valide', '1006.30.00.00', '0.00', '0.00', 'unité', 'Classification automatique - Confiance: 85%', NULL, 'automatique', '2025-08-07 19:27:28', '2025-08-07 19:27:28'),
(43, 'Non spécifié', 'riz', NULL, 0, 1, '8.75', 'II', NULL, 5, 'valide', '1006.30.00.00', '0.00', '0.00', 'unité', 'Classification automatique - Confiance: 85%', NULL, 'automatique', '2025-08-07 19:31:47', '2025-08-07 19:31:47'),
(44, 'Non spécifié', 'riz', NULL, 0, 1, '8.75', 'II', NULL, 5, 'valide', '1006.30.00.00', '0.00', '0.00', 'unité', 'Classification automatique - Confiance: 85%', NULL, 'automatique', '2025-08-07 19:31:47', '2025-08-07 19:31:47'),
(45, 'Non spécifié', 'riz', NULL, 0, 1, '8.75', 'II', NULL, 5, 'valide', '1006.30.00.00', '0.00', '0.00', 'unité', 'Classification automatique - Confiance: 85%', NULL, 'automatique', '2025-08-07 19:35:38', '2025-08-07 19:35:38'),
(46, 'Non spécifié', 'riz', NULL, 0, 1, '8.75', 'II', NULL, 5, 'valide', '1006.30.00.00', '0.00', '0.00', 'unité', 'Classification automatique - Confiance: 85%', NULL, 'automatique', '2025-08-07 19:35:38', '2025-08-07 19:35:38'),
(47, 'Non spécifié', 'riz', NULL, 0, 1, '8.75', 'II', NULL, 5, 'valide', '1006.30.00.00', '0.00', '0.00', 'unité', 'Classification automatique - Confiance: 85%', NULL, 'automatique', '2025-08-08 12:12:24', '2025-08-08 12:12:24'),
(48, 'Non spécifié', 'riz', NULL, 0, 1, '8.75', 'II', NULL, 5, 'valide', '1006.30.00.00', '0.00', '0.00', 'unité', 'Classification automatique - Confiance: 85%', NULL, 'automatique', '2025-08-08 12:12:24', '2025-08-08 12:12:24'),
(49, 'Non spécifié', 'viande', NULL, 0, 1, '10.50', 'I', NULL, 5, 'en_attente', '0201.10.00.00', '0.00', '0.00', 'unité', 'Classification automatique - Confiance: 80%', NULL, 'automatique', '2025-08-08 12:12:51', '2025-08-08 12:12:51'),
(50, 'Non spécifié', 'viande', NULL, 0, 1, '10.50', 'I', NULL, 5, 'en_attente', '0201.10.00.00', '0.00', '0.00', 'unité', 'Classification automatique - Confiance: 80%', NULL, 'automatique', '2025-08-08 12:12:51', '2025-08-08 12:12:51'),
(51, 'Non spécifié', 'poissons', NULL, 0, 1, '10.50', 'I', NULL, 5, 'en_attente', '0201.10.00.00', '0.00', '0.00', 'unité', 'Classification automatique - Confiance: 80%', NULL, 'automatique', '2025-08-08 14:09:33', '2025-08-08 14:09:33'),
(52, 'Non spécifié', 'poissons', NULL, 0, 1, '10.50', 'I', NULL, 5, 'en_attente', '0201.10.00.00', '0.00', '0.00', 'unité', 'Classification automatique - Confiance: 80%', NULL, 'automatique', '2025-08-08 14:09:33', '2025-08-08 14:09:33'),
(53, 'Non spécifié', 'lait', NULL, 0, 1, '15.75', 'XX', NULL, 5, 'en_attente', '9999.00.00.00', '0.00', '0.00', 'unité', 'Classification automatique - Confiance: 60%', NULL, 'automatique', '2025-08-08 14:09:53', '2025-08-08 14:09:53'),
(54, 'Non spécifié', 'lait', NULL, 0, 1, '15.75', 'XX', NULL, 5, 'en_attente', '9999.00.00.00', '0.00', '0.00', 'unité', 'Classification automatique - Confiance: 60%', NULL, 'automatique', '2025-08-08 14:09:53', '2025-08-08 14:09:53'),
(55, 'Non spécifié', 'riz', NULL, 0, 1, '8.75', 'II', NULL, 5, 'valide', '1006.30.00.00', '0.00', '0.00', 'unité', 'Classification automatique - Confiance: 85%', NULL, 'automatique', '2025-08-08 14:10:54', '2025-08-08 14:10:54'),
(57, 'Chine', 'Smartphone Android', NULL, 0, 1, '22.50', 'XVI', NULL, 5, 'valide', '8517.12.00.00', '150000.00', '0.00', 'unité', 'Classification automatique - Confiance: 88%', NULL, 'automatique', '2025-08-08 14:13:44', '2025-08-08 14:13:44'),
(58, 'Japon', 'Véhicule automobile essence', NULL, 0, 1, '20.75', 'XVII', NULL, 5, 'valide', '8703.23.00.00', '2500000.00', '0.00', 'unité', 'Classification automatique - Confiance: 92%', NULL, 'automatique', '2025-08-08 14:13:54', '2025-08-08 14:13:54'),
(59, 'Non spécifié', 'voitures', NULL, 0, 1, '20.75', 'XVII', NULL, 5, 'valide', '8703.23.00.00', '0.00', '0.00', 'unité', 'Classification automatique - Confiance: 85%', NULL, 'automatique', '2025-08-08 14:14:26', '2025-08-08 14:14:26'),
(60, 'Non spécifié', 'voitures', NULL, 0, 1, '20.75', 'XVII', NULL, 5, 'valide', '8703.23.00.00', '0.00', '0.00', 'unité', 'Classification automatique - Confiance: 85%', NULL, 'automatique', '2025-08-08 14:14:26', '2025-08-08 14:14:26'),
(61, 'Non spécifié', 'riz', NULL, 0, 1, '8.75', 'II', NULL, 5, 'valide', '1006.30.00.00', '0.00', '0.00', 'unité', 'Classification automatique - Confiance: 85%', NULL, 'automatique', '2025-08-09 01:37:16', '2025-08-09 01:37:16'),
(62, 'Non spécifié', 'riz', NULL, 0, 1, '8.75', 'II', NULL, 5, 'valide', '1006.30.00.00', '0.00', '0.00', 'unité', 'Classification automatique - Confiance: 85%', NULL, 'automatique', '2025-08-09 01:37:16', '2025-08-09 01:37:16'),
(63, 'Japon', 'Véhicule automobile essence', NULL, 0, 1, '20.75', 'XVII', NULL, 5, 'valide', '8703.23.00.00', '2500000.00', '0.00', 'unité', 'Classification automatique - Confiance: 92%', NULL, 'automatique', '2025-08-09 15:52:03', '2025-08-09 15:52:03'),
(64, 'Côte d\'Ivoire', 'Riz blanc long grain', NULL, 0, 1, '8.75', 'II', NULL, 5, 'valide', '1006.30.00.00', '50000.00', '0.00', 'unité', 'Classification automatique - Confiance: 85%', NULL, 'automatique', '2025-08-09 15:52:05', '2025-08-09 15:52:05'),
(65, 'Non spécifié', 'graines', NULL, 0, 1, '15.75', 'XX', NULL, 5, 'en_attente', '9999.00.00.00', '0.00', '0.00', 'unité', 'Classification automatique - Confiance: 60%', NULL, 'automatique', '2025-08-09 15:52:24', '2025-08-09 15:52:24'),
(66, 'Non spécifié', 'graines', NULL, 0, 1, '15.75', 'XX', NULL, 5, 'en_attente', '9999.00.00.00', '0.00', '0.00', 'unité', 'Classification automatique - Confiance: 60%', NULL, 'automatique', '2025-08-09 15:52:24', '2025-08-09 15:52:24'),
(67, 'Non spécifié', 'riz', NULL, 0, 1, '8.75', 'II', NULL, 5, 'valide', '1006.30.00.00', '0.00', '0.00', 'unité', 'Classification automatique - Confiance: 85%', NULL, 'automatique', '2025-08-11 20:45:02', '2025-08-11 20:45:02'),
(68, 'Non spécifié', 'riz', NULL, 0, 1, '8.75', 'II', NULL, 5, 'valide', '1006.30.00.00', '0.00', '0.00', 'unité', 'Classification automatique - Confiance: 85%', NULL, 'automatique', '2025-08-11 20:45:02', '2025-08-11 20:45:02'),
(69, 'Non spécifié', 'riz', NULL, 0, 1, '8.75', 'II', NULL, 5, 'valide', '1006.30.00.00', '0.00', '0.00', 'unité', 'Classification automatique - Confiance: 85%', NULL, 'automatique', '2025-08-12 08:23:41', '2025-08-12 08:23:41'),
(70, 'Non spécifié', 'riz', NULL, 0, 1, '8.75', 'II', NULL, 5, 'valide', '1006.30.00.00', '0.00', '0.00', 'unité', 'Classification automatique - Confiance: 85%', NULL, 'automatique', '2025-08-12 08:23:41', '2025-08-12 08:23:41'),
(71, 'Non spécifié', 'riz et meubles', NULL, 0, 1, '8.75', 'II', NULL, 5, 'valide', '1006.30.00.00', '0.00', '0.00', 'unité', 'Classification automatique - Confiance: 85%', NULL, 'automatique', '2025-08-12 09:53:47', '2025-08-12 09:53:47'),
(72, 'Non spécifié', 'riz', NULL, 0, 1, '8.75', 'II', NULL, 5, 'valide', '1006.30.00.00', '0.00', '0.00', 'unité', 'Classification automatique - Confiance: 85%', NULL, 'automatique', '2025-08-12 09:56:29', '2025-08-12 09:56:29'),
(73, 'Non spécifié', 'riz', NULL, 0, 1, '8.75', 'II', NULL, 5, 'valide', '1006.30.00.00', '0.00', '0.00', 'unité', 'Classification automatique - Confiance: 85%', NULL, 'automatique', '2025-08-12 09:56:59', '2025-08-12 09:56:59'),
(74, 'Non spécifié', 'meubles', NULL, 0, 1, '15.75', 'XX', NULL, 5, 'en_attente', '9999.00.00.00', '0.00', '0.00', 'unité', 'Classification automatique - Confiance: 60%', NULL, 'automatique', '2025-08-12 10:38:06', '2025-08-12 10:38:06'),
(75, 'Non spécifié', 'jouets', NULL, 0, 1, '15.75', 'XX', NULL, 5, 'en_attente', '9999.00.00.00', '0.00', '0.00', 'unité', 'Classification automatique - Confiance: 60%', NULL, 'automatique', '2025-08-12 10:38:23', '2025-08-12 10:38:23'),
(76, 'Non spécifié', 'poisson', NULL, 0, 1, '10.50', 'I', NULL, 5, 'en_attente', '0201.10.00.00', '0.00', '0.00', 'unité', 'Classification automatique - Confiance: 80%', NULL, 'automatique', '2025-08-12 10:40:11', '2025-08-12 10:40:11'),
(77, 'Inde', 'Tissu de coton imprimé', NULL, 0, 1, '17.25', 'XI', NULL, 5, 'valide', '5208.52.00.00', '25000.00', '0.00', 'unité', 'Classification automatique - Confiance: 90%', NULL, 'automatique', '2025-08-12 11:23:15', '2025-08-12 11:23:15'),
(78, 'Japon', 'Véhicule automobile essence', NULL, 0, 1, '20.75', 'XVII', NULL, 5, 'valide', '8703.23.00.00', '2500000.00', '0.00', 'unité', 'Classification automatique - Confiance: 92%', NULL, 'automatique', '2025-08-12 11:23:21', '2025-08-12 11:23:21'),
(79, 'Japon', 'Véhicule automobile essence', NULL, 0, 1, '20.75', 'XVII', NULL, 5, 'valide', '8703.23.00.00', '2500000.00', '0.00', 'unité', 'Classification automatique - Confiance: 92%', NULL, 'automatique', '2025-08-12 11:23:31', '2025-08-12 11:23:31'),
(80, 'Japon', 'Véhicule automobile essence', NULL, 0, 1, '20.75', 'XVII', NULL, 5, 'valide', '8703.23.00.00', '2500000.00', '0.00', 'unité', 'Classification automatique - Confiance: 92%', NULL, 'automatique', '2025-08-12 11:23:33', '2025-08-12 11:23:33'),
(81, 'Japon', 'Véhicule automobile essence', NULL, 0, 1, '20.75', 'XVII', NULL, 5, 'valide', '8703.23.00.00', '2500000.00', '0.00', 'unité', 'Classification automatique - Confiance: 92%', NULL, 'automatique', '2025-08-12 11:23:37', '2025-08-12 11:23:37'),
(82, 'Inde', 'Tissu de coton imprimé', NULL, 0, 1, '17.25', 'XI', NULL, 5, 'valide', '5208.52.00.00', '25000.00', '0.00', 'unité', 'Classification automatique - Confiance: 90%', NULL, 'automatique', '2025-08-12 11:23:43', '2025-08-12 11:23:43'),
(83, 'Côte d\'Ivoire', 'Riz blanc long grain', NULL, 0, 1, '8.75', 'II', NULL, 5, 'valide', '1006.30.00.00', '50000.00', '0.00', 'unité', 'Classification automatique - Confiance: 85%', NULL, 'automatique', '2025-08-12 11:23:54', '2025-08-12 11:23:54'),
(84, 'Chine', 'Smartphone Android', NULL, 0, 1, '22.50', 'XVI', NULL, 5, 'valide', '8517.12.00.00', '150000.00', '0.00', 'unité', 'Classification automatique - Confiance: 88%', NULL, 'automatique', '2025-08-12 11:23:56', '2025-08-12 11:23:56'),
(85, 'Non spécifié', 'riz', NULL, 0, 1, '8.75', 'II', NULL, 5, 'valide', '1006.30.00.00', '0.00', '0.00', 'unité', 'Classification automatique - Confiance: 85%', NULL, 'automatique', '2025-08-12 11:29:51', '2025-08-12 11:29:51'),
(86, 'Non spécifié', 'poisson', NULL, 0, 1, '10.50', 'I', NULL, 5, 'en_attente', '0201.10.00.00', '0.00', '0.00', 'unité', 'Classification automatique - Confiance: 80%', NULL, 'automatique', '2025-08-12 11:30:13', '2025-08-12 11:30:13'),
(87, 'Non spécifié', 'graines', NULL, 0, 1, '15.75', 'XX', NULL, 5, 'en_attente', '9999.00.00.00', '0.00', '0.00', 'unité', 'Classification automatique - Confiance: 60%', NULL, 'automatique', '2025-08-12 11:30:33', '2025-08-12 11:30:33'),
(88, 'Non spécifié', 'poissons', NULL, 0, 1, '10.50', 'I', NULL, 5, 'en_attente', '0201.10.00.00', '0.00', '0.00', 'unité', 'Classification automatique - Confiance: 80%', NULL, 'automatique', '2025-08-12 11:31:09', '2025-08-12 11:31:09'),
(89, 'Non spécifié', 'telephone', NULL, 0, 1, '15.75', 'XX', NULL, 5, 'en_attente', '9999.00.00.00', '0.00', '0.00', 'unité', 'Classification automatique - Confiance: 60%', NULL, 'automatique', '2025-08-12 11:32:02', '2025-08-12 11:32:02'),
(90, 'Non spécifié', 'voiture', NULL, 0, 1, '20.75', 'XVII', NULL, 5, 'valide', '8703.23.00.00', '0.00', '0.00', 'unité', 'Classification automatique - Confiance: 85%', NULL, 'automatique', '2025-08-12 11:32:51', '2025-08-12 11:32:51'),
(91, 'Non spécifié', 'riz', NULL, 0, 1, '8.75', 'II', NULL, 5, 'valide', '1006.30.00.00', '0.00', '0.00', 'unité', 'Classification automatique - Confiance: 85%', NULL, 'automatique', '2025-08-12 12:01:02', '2025-08-12 12:01:02'),
(92, 'Non spécifié', 'poissons', NULL, 0, 1, '10.50', 'I', NULL, 5, 'valide', '0302', '0.00', '0.00', 'unité', 'Classification automatique - Confiance: 98%', NULL, 'automatique', '2025-08-12 12:01:15', '2025-08-12 12:01:15'),
(93, 'Non spécifié', 'meubles', NULL, 0, 1, '15.75', 'XX', NULL, 5, 'valide', '9401', '0.00', '0.00', 'unité', 'Classification automatique - Confiance: 96%', NULL, 'automatique', '2025-08-12 12:01:45', '2025-08-12 12:01:45'),
(94, 'Non spécifié', 'jouets', NULL, 0, 1, '15.75', 'XX', NULL, 5, 'valide', '9503', '0.00', '0.00', 'unité', 'Classification automatique - Confiance: 98%', NULL, 'automatique', '2025-08-12 12:02:00', '2025-08-12 12:02:00'),
(95, 'Non spécifié', 'armes', NULL, 0, 1, '15.75', 'XX', NULL, 5, 'en_attente', '9999.00.00.00', '0.00', '0.00', 'unité', 'Classification automatique - Confiance: 60%', NULL, 'automatique', '2025-08-12 12:02:21', '2025-08-12 12:02:21'),
(96, 'Non spécifié', 'riz', NULL, 0, 1, '8.75', 'II', NULL, 5, 'valide', 'II10.00.00.00', '0.00', '0.00', 'unité', 'Classification automatique - Confiance: 99.9%', NULL, 'automatique', '2025-08-12 12:49:16', '2025-08-12 12:49:16'),
(97, 'Non spécifié', 'riz', NULL, 0, 1, '15.75', 'XX', NULL, 5, 'valide', '9999.00.00.00', '0.00', '0.00', 'unité', 'Classification automatique - Confiance: 96.513724503369%', NULL, 'automatique', '2025-08-12 12:49:28', '2025-08-12 12:49:28'),
(98, 'Non spécifié', 'GRAINES', NULL, 0, 1, '8.75', 'II', NULL, 5, 'valide', 'II10.00.00.00', '0.00', '0.00', 'unité', 'Classification automatique - Confiance: 99.9%', NULL, 'automatique', '2025-08-12 13:11:53', '2025-08-12 13:11:53'),
(99, 'Non spécifié', 'graines', NULL, 0, 1, '8.75', 'II', NULL, 5, 'valide', 'II10.00.00.00', '0.00', '0.00', 'unité', 'Classification automatique - Confiance: 99.9%', NULL, 'automatique', '2025-08-12 13:12:51', '2025-08-12 13:12:51'),
(100, 'Non spécifié', 'Graines oléagineuses', NULL, 0, 1, '8.75', 'II', NULL, 5, 'valide', 'II10.00.00.00', '0.00', '0.00', 'unité', 'Classification automatique - Confiance: 99.9%', NULL, 'automatique', '2025-08-12 13:13:13', '2025-08-12 13:13:13'),
(101, 'Non spécifié', 'mangue', NULL, 0, 1, '8.75', 'II', NULL, 5, 'valide', 'II08.00.00.00', '0.00', '0.00', 'unité', 'Classification automatique - Confiance: 99.9%', NULL, 'automatique', '2025-08-12 13:13:34', '2025-08-12 13:13:34'),
(102, 'Non spécifié', 'fraise', NULL, 0, 1, '8.75', 'II', NULL, 5, 'valide', 'II08.00.00.00', '0.00', '0.00', 'unité', 'Classification automatique - Confiance: 99.9%', NULL, 'automatique', '2025-08-12 13:19:41', '2025-08-12 13:19:41'),
(103, 'Non spécifié', 'banane', NULL, 0, 1, '8.75', 'II', NULL, 5, 'valide', 'II08.00.00.00', '0.00', '0.00', 'unité', 'Classification automatique - Confiance: 99.9%', NULL, 'automatique', '2025-08-12 13:21:48', '2025-08-12 13:21:48'),
(104, 'Non spécifié', 'tomates', NULL, 0, 1, '8.75', 'II', NULL, 5, 'valide', 'II07.00.00.00', '0.00', '0.00', 'unité', 'Classification automatique - Confiance: 99.9%', NULL, 'automatique', '2025-08-12 13:22:09', '2025-08-12 13:22:09'),
(105, 'Non spécifié', 'canne a sucre', NULL, 0, 1, '15.25', 'IV', NULL, 5, 'valide', 'IV17.00.00.00', '0.00', '0.00', 'unité', 'Classification automatique - Confiance: 99.9%', NULL, 'automatique', '2025-08-12 13:22:37', '2025-08-12 13:22:37'),
(106, 'Non spécifié', 'kiwi', NULL, 0, 1, '8.75', 'II', NULL, 5, 'valide', 'II08.00.00.00', '0.00', '0.00', 'unité', 'Classification automatique - Confiance: 99.9%', NULL, 'automatique', '2025-08-12 13:24:29', '2025-08-12 13:24:29'),
(107, 'Non spécifié', 'apple', NULL, 0, 1, '8.75', 'II', NULL, 5, 'valide', 'II08.00.00.00', '0.00', '0.00', 'unité', 'Classification automatique - Confiance: 99.9%', NULL, 'automatique', '2025-08-12 13:26:24', '2025-08-12 13:26:24'),
(108, 'Non spécifié', 'tablette', NULL, 0, 1, '15.25', 'IV', NULL, 5, 'valide', 'IV18.00.00.00', '0.00', '0.00', 'unité', 'Classification automatique - Confiance: 99.9%', NULL, 'automatique', '2025-08-12 13:28:28', '2025-08-12 13:28:28'),
(109, 'Non spécifié', 'tablette electronique', NULL, 0, 1, '15.25', 'IV', NULL, 5, 'valide', 'IV18.00.00.00', '0.00', '0.00', 'unité', 'Classification automatique - Confiance: 99.9%', NULL, 'automatique', '2025-08-12 13:28:52', '2025-08-12 13:28:52'),
(110, 'Non spécifié', 'riz', NULL, 0, 1, '8.75', 'II', NULL, 5, 'valide', 'II10.00.00.00', '0.00', '0.00', 'unité', 'Classification automatique - Confiance: 99.9%', NULL, 'automatique', '2025-08-12 13:35:57', '2025-08-12 13:35:57'),
(111, 'Non spécifié', 'tablette', NULL, 0, 1, '15.25', 'IV', NULL, 5, 'valide', 'IV18.00.00.00', '0.00', '0.00', 'unité', 'Classification automatique - Confiance: 99.9%', NULL, 'automatique', '2025-08-12 13:36:45', '2025-08-12 13:36:45'),
(112, 'Non spécifié', 'riz', NULL, 0, 1, '8.75', 'II', NULL, 5, 'valide', 'II10.00.00.00', '0.00', '0.00', 'unité', 'Classification automatique - Confiance: 99.9%', NULL, 'automatique', '2025-08-12 14:16:12', '2025-08-12 14:16:12'),
(113, 'Non spécifié', 'textile cotoon', NULL, 0, 1, '17.25', 'XI', NULL, 5, 'valide', 'XI50.00.00.00', '0.00', '0.00', 'unité', 'Classification automatique - Confiance: 99.9%', NULL, 'automatique', '2025-08-12 14:16:35', '2025-08-12 14:16:35'),
(114, 'Non spécifié', 'textile cotoon', NULL, 0, 1, '17.25', 'XI', NULL, 5, 'valide', 'XI50.00.00.00', '0.00', '0.00', 'unité', 'Classification automatique - Confiance: 99.9%', NULL, 'automatique', '2025-08-12 14:16:38', '2025-08-12 14:16:38'),
(115, 'Non spécifié', 'textile cotoon', NULL, 0, 1, '17.25', 'XI', NULL, 5, 'valide', 'XI50.00.00.00', '0.00', '0.00', 'unité', 'Classification automatique - Confiance: 99.9%', NULL, 'automatique', '2025-08-12 14:16:44', '2025-08-12 14:16:44'),
(116, 'Non spécifié', 'coton', NULL, 0, 1, '17.25', 'XI', NULL, 5, 'valide', 'XI50.00.00.00', '0.00', '0.00', 'unité', 'Classification automatique - Confiance: 99.9%', NULL, 'automatique', '2025-08-12 14:17:23', '2025-08-12 14:17:23'),
(117, 'Non spécifié', 'coton', NULL, 0, 1, '17.25', 'XI', NULL, 5, 'valide', 'XI50.00.00.00', '0.00', '0.00', 'unité', 'Classification automatique - Confiance: 99.9%', NULL, 'automatique', '2025-08-12 14:19:39', '2025-08-12 14:19:39'),
(118, 'Non spécifié', 'coton', NULL, 0, 1, '17.25', 'XI', NULL, 5, 'valide', 'XI50.00.00.00', '0.00', '0.00', 'unité', 'Classification automatique - Confiance: 99.9%', NULL, 'automatique', '2025-08-12 14:19:53', '2025-08-12 14:19:53'),
(119, 'Non spécifié', 'coton', NULL, 0, 1, '17.25', 'XI', NULL, 5, 'valide', 'undefined', '0.00', '0.00', 'unité', 'Classification automatique - Confiance: 100%', NULL, 'automatique', '2025-08-12 14:26:31', '2025-08-12 14:26:31'),
(120, 'Non spécifié', 'coton', NULL, 0, 1, '17.25', 'XI', NULL, 5, 'valide', 'undefined', '0.00', '0.00', 'unité', 'Classification automatique - Confiance: 100%', NULL, 'automatique', '2025-08-12 14:30:19', '2025-08-12 14:30:19'),
(121, 'Non spécifié', 'ble', NULL, 0, 1, '5.50', 'V', NULL, 5, 'valide', 'undefined', '0.00', '0.00', 'unité', 'Classification automatique - Confiance: 100%', NULL, 'automatique', '2025-08-12 15:06:08', '2025-08-12 15:06:08'),
(122, 'Non spécifié', 'riz', NULL, 0, 1, '8.75', 'II', NULL, 5, 'valide', 'undefined', '0.00', '0.00', 'unité', 'Classification automatique - Confiance: 100%', NULL, 'automatique', '2025-08-12 15:07:13', '2025-08-12 15:07:13'),
(123, 'Non spécifié', 'café', NULL, 0, 1, '8.75', 'II', NULL, 5, 'valide', 'undefined', '0.00', '0.00', 'unité', 'Classification automatique - Confiance: 100%', NULL, 'automatique', '2025-08-12 15:07:46', '2025-08-12 15:07:46'),
(124, 'Non spécifié', 'riz', NULL, 0, 1, '8.75', 'II', NULL, 5, 'valide', 'undefined', '0.00', '0.00', 'unité', 'Classification automatique - Confiance: 100%', NULL, 'automatique', '2025-08-12 15:37:36', '2025-08-12 15:37:36'),
(125, 'Non spécifié', 'coton', NULL, 0, 1, '17.25', 'XI', NULL, 5, 'valide', 'undefined', '0.00', '0.00', 'unité', 'Classification automatique - Confiance: 100%', NULL, 'automatique', '2025-08-12 15:40:36', '2025-08-12 15:40:36'),
(126, 'Non spécifié', 'coton', NULL, 0, 1, '17.25', 'XI', NULL, 5, 'valide', 'XI50.00.00.00', '0.00', '0.00', 'unité', 'Classification automatique - Confiance: 99.9%', NULL, 'automatique', '2025-08-12 15:41:09', '2025-08-12 15:41:09'),
(127, 'Non spécifié', 'mangue', NULL, 0, 1, '8.75', 'II', NULL, 5, 'valide', 'II08.00.00.00', '0.00', '0.00', 'unité', 'Classification automatique - Confiance: 99.9%', NULL, 'automatique', '2025-08-12 15:41:29', '2025-08-12 15:41:29'),
(128, 'Non spécifié', 'tablette', NULL, 0, 1, '15.25', 'IV', NULL, 5, 'valide', 'IV18.00.00.00', '0.00', '0.00', 'unité', 'Classification automatique - Confiance: 99.9%', NULL, 'automatique', '2025-08-12 15:41:44', '2025-08-12 15:41:44'),
(129, 'Non spécifié', 'coton', NULL, 0, 1, '17.25', 'XI', NULL, 5, 'valide', 'XI52.00.00.00', '0.00', '0.00', 'unité', 'Classification automatique - Confiance: 99.9%', NULL, 'automatique', '2025-08-12 16:01:05', '2025-08-12 16:01:05'),
(130, 'Non spécifié', 'laine', NULL, 0, 1, '10.50', 'I', NULL, 5, 'valide', '0I05.00.00.00', '0.00', '0.00', 'unité', 'Classification automatique - Confiance: 99.9%', NULL, 'automatique', '2025-08-12 16:01:28', '2025-08-12 16:01:28'),
(131, 'Non spécifié', 'laine', NULL, 0, 1, '17.25', 'XI', NULL, 5, 'valide', 'XI51.00.00.00', '0.00', '0.00', 'unité', 'Classification automatique - Confiance: 99.9%', NULL, 'automatique', '2025-08-12 16:07:43', '2025-08-12 16:07:43'),
(132, 'Non spécifié', 'soie', NULL, 0, 1, '10.50', 'I', NULL, 5, 'valide', '0I01.00.00.00', '0.00', '0.00', 'unité', 'Classification automatique - Confiance: 99.9%', NULL, 'automatique', '2025-08-12 16:07:57', '2025-08-12 16:07:57'),
(133, 'Non spécifié', 'coton', NULL, 0, 1, '17.25', 'XI', NULL, 5, 'valide', 'XI52.00.00.00', '0.00', '0.00', 'unité', 'Classification automatique - Confiance: 99.9%', NULL, 'automatique', '2025-08-12 16:08:17', '2025-08-12 16:08:17'),
(134, 'Non spécifié', 'riz', NULL, 0, 1, '8.75', 'II', NULL, 5, 'valide', 'II10.00.00.00', '0.00', '0.00', 'unité', 'Classification automatique - Confiance: 99.9%', NULL, 'automatique', '2025-08-12 16:11:09', '2025-08-12 16:11:09'),
(135, 'Non spécifié', 'JUS', NULL, 0, 1, '15.25', 'IV', NULL, 5, 'valide', 'IV20.00.00.00', '0.00', '0.00', 'unité', 'Classification automatique - Confiance: 99.9%', NULL, 'automatique', '2025-08-12 16:46:11', '2025-08-12 16:46:11'),
(136, 'Non spécifié', 'riz', NULL, 0, 1, '8.75', 'II', NULL, 5, 'valide', 'II10.00.00.00', '0.00', '0.00', 'unité', 'Classification automatique - Confiance: 99.9%', NULL, 'automatique', '2025-08-12 17:07:00', '2025-08-12 17:07:00'),
(137, 'Non spécifié', 'bonnet', NULL, 0, 1, '15.75', 'XX', NULL, 5, 'valide', '9999.00.00.00', '0.00', '0.00', 'unité', 'Classification automatique - Confiance: 91.070906975956%', NULL, 'automatique', '2025-08-12 17:07:24', '2025-08-12 17:07:24'),
(138, 'Non spécifié', 'coton', NULL, 0, 1, '17.25', 'XI', NULL, 5, 'valide', 'XI50.00.00.00', '0.00', '0.00', 'unité', 'Classification automatique - Confiance: 99.9%', NULL, 'automatique', '2025-08-12 17:09:06', '2025-08-12 17:09:06'),
(139, 'Non spécifié', 'avion', NULL, 0, 1, '20.75', 'XVII', NULL, 5, 'valide', 'XVII88.00.00.00', '0.00', '0.00', 'unité', 'Classification automatique - Confiance: 99.9%', NULL, 'automatique', '2025-08-12 17:26:37', '2025-08-12 17:26:37'),
(140, 'Non spécifié', 'riz', NULL, 0, 1, '8.75', 'II', NULL, 5, 'valide', 'II10.00.00.00', '0.00', '0.00', 'unité', 'Classification automatique - Confiance: 99.9%', NULL, 'automatique', '2025-08-12 17:26:55', '2025-08-12 17:26:55'),
(141, 'Non spécifié', 'horloge', NULL, 0, 1, '9.25', 'XIII', NULL, 5, 'valide', 'XIII71.00.00.00', '0.00', '0.00', 'unité', 'Classification automatique - Confiance: 99.9%', NULL, 'automatique', '2025-08-12 17:27:08', '2025-08-12 17:27:08'),
(142, 'Non spécifié', 'riz', NULL, 0, 1, '8.75', 'II', NULL, 5, 'valide', 'II10.00.00.00', '0.00', '0.00', 'unité', 'Classification automatique - Confiance: 99.9%', NULL, 'automatique', '2025-08-13 00:07:49', '2025-08-13 00:07:49'),
(143, 'Non spécifié', 'je veux du riz', NULL, 0, 1, '8.75', 'II', NULL, 5, 'valide', 'II10.00.00.00', '0.00', '0.00', 'unité', 'Classification automatique - Confiance: 99.9%', NULL, 'automatique', '2025-08-13 00:08:11', '2025-08-13 00:08:11'),
(144, 'Non spécifié', 'automobile', NULL, 0, 1, '22.50', 'XVI', NULL, 5, 'valide', 'XVI87.00.00.00', '0.00', '0.00', 'unité', 'Classification automatique - Confiance: 99.9%', NULL, 'automatique', '2025-08-13 00:09:24', '2025-08-13 00:09:24'),
(145, 'Non spécifié', 'kiwi', NULL, 0, 1, '8.75', 'II', NULL, 5, 'valide', 'II08.00.00.00', '0.00', '0.00', 'unité', 'Classification automatique - Confiance: 99.9%', NULL, 'automatique', '2025-08-13 00:10:01', '2025-08-13 00:10:01'),
(146, 'Non spécifié', 'riz', NULL, 0, 1, '8.75', 'II', NULL, 5, 'valide', 'II10.00.00.00', '0.00', '0.00', 'unité', 'Classification automatique - Confiance: 99.9%', NULL, 'automatique', '2025-08-13 00:11:38', '2025-08-13 00:11:38'),
(147, 'Non spécifié', 'avion commercial', NULL, 0, 1, '20.75', 'XVII', NULL, 5, 'valide', 'undefined', '0.00', '0.00', 'unité', 'Classification automatique - Confiance: 95%', NULL, 'automatique', '2025-08-13 09:49:11', '2025-08-13 09:49:11'),
(148, 'Non spécifié', 'avion commercial', NULL, 0, 1, '20.75', 'XVII', NULL, 5, 'valide', '880100', '0.00', '0.00', 'unité', 'Classification automatique - Confiance: 95%', NULL, 'automatique', '2025-08-13 09:57:51', '2025-08-13 09:57:51'),
(149, 'Non spécifié', 'ordinateur', NULL, 0, 1, '22.50', 'XVI', NULL, 5, 'valide', '840100', '0.00', '0.00', 'unité', 'Classification automatique - Confiance: 95%', NULL, 'automatique', '2025-08-13 10:02:12', '2025-08-13 10:02:12'),
(150, 'Non spécifié', 'avion commercial', NULL, 0, 1, '20.75', 'XVII', NULL, 5, 'valide', 'XVII88.00.00.00', '0.00', '0.00', 'unité', 'Classification automatique - Confiance: 99.9%', NULL, 'automatique', '2025-08-13 10:23:01', '2025-08-13 10:23:01'),
(151, 'Non spécifié', 'avion commercial', NULL, 0, 1, '20.75', 'XVII', NULL, 5, 'valide', 'XVII88.00.00.00', '0.00', '0.00', 'unité', 'Classification automatique - Confiance: 99.9%', NULL, 'automatique', '2025-08-13 10:25:46', '2025-08-13 10:25:46');

--
-- Triggers `produits`
--
DELIMITER $$
CREATE TRIGGER `update_user_product_count` AFTER INSERT ON `produits` FOR EACH ROW BEGIN
    UPDATE User 
    SET nombre_produits_classes = (
        SELECT COUNT(*) FROM Produits WHERE user_id = NEW.user_id
    ) 
    WHERE user_id = NEW.user_id;
END
$$
DELIMITER ;

-- --------------------------------------------------------

--
-- Table structure for table `taux_imposition`
--

CREATE TABLE `taux_imposition` (
  `id_taux` int(11) NOT NULL,
  `section` varchar(5) NOT NULL,
  `chapitre` varchar(5) DEFAULT NULL,
  `sous_section` varchar(20) DEFAULT NULL,
  `taux_pourcentage` decimal(5,2) NOT NULL,
  `description_taux` text,
  `date_application` date NOT NULL,
  `date_fin` date DEFAULT NULL,
  `statut_taux` enum('actif','inactif') DEFAULT 'actif',
  `date_creation` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

--
-- Dumping data for table `taux_imposition`
--

INSERT INTO `taux_imposition` (`id_taux`, `section`, `chapitre`, `sous_section`, `taux_pourcentage`, `description_taux`, `date_application`, `date_fin`, `statut_taux`, `date_creation`) VALUES
(1, 'I', NULL, '01-05', '10.50', 'Animaux vivants et produits du règne animal', '2024-01-01', NULL, 'actif', '2025-08-07 11:51:01'),
(2, 'II', NULL, '06-14', '8.75', 'Produits du règne végétal', '2024-01-01', NULL, 'actif', '2025-08-07 11:51:01'),
(3, 'III', NULL, '15', '12.00', 'Graisses et huiles animales, végétales', '2024-01-01', NULL, 'actif', '2025-08-07 11:51:01'),
(4, 'IV', NULL, '16-24', '15.25', 'Produits des industries alimentaires', '2024-01-01', NULL, 'actif', '2025-08-07 11:51:01'),
(5, 'V', NULL, '25-27', '5.50', 'Produits minéraux', '2024-01-01', NULL, 'actif', '2025-08-07 11:51:01'),
(6, 'VI', NULL, '28-38', '18.75', 'Produits des industries chimiques', '2024-01-01', NULL, 'actif', '2025-08-07 11:51:01'),
(7, 'VII', NULL, '39-40', '14.50', 'Matières plastiques et caoutchouc', '2024-01-01', NULL, 'actif', '2025-08-07 11:51:01'),
(8, 'VIII', NULL, '41-43', '16.25', 'Peaux, cuirs et ouvrages', '2024-01-01', NULL, 'actif', '2025-08-07 11:51:01'),
(9, 'IX', NULL, '44-46', '11.75', 'Bois, charbon de bois et ouvrages', '2024-01-01', NULL, 'actif', '2025-08-07 11:51:01'),
(10, 'X', NULL, '47-49', '13.50', 'Pâtes de bois, papier et carton', '2024-01-01', NULL, 'actif', '2025-08-07 11:51:01'),
(11, 'XI', NULL, '50-63', '17.25', 'Matières textiles et ouvrages', '2024-01-01', NULL, 'actif', '2025-08-07 11:51:01'),
(12, 'XII', NULL, '64-67', '19.50', 'Chaussures, coiffures, parapluies', '2024-01-01', NULL, 'actif', '2025-08-07 11:51:01'),
(13, 'XIII', NULL, '68-70', '9.25', 'Ouvrages en pierres, céramique, verre', '2024-01-01', NULL, 'actif', '2025-08-07 11:51:01'),
(14, 'XIV', NULL, '71', '25.00', 'Perles, pierres gemmes, métaux précieux', '2024-01-01', NULL, 'actif', '2025-08-07 11:51:01'),
(15, 'XV', NULL, '72-83', '12.75', 'Métaux communs et ouvrages', '2024-01-01', NULL, 'actif', '2025-08-07 11:51:01'),
(16, 'XVI', NULL, '84-85', '22.50', 'Machines et appareils électriques', '2024-01-01', NULL, 'actif', '2025-08-07 11:51:01'),
(17, 'XVII', NULL, '86-89', '20.75', 'Matériel de transport', '2024-01-01', NULL, 'actif', '2025-08-07 11:51:01'),
(18, 'XVIII', NULL, '90-92', '16.50', 'Instruments d\'optique, de mesure, horlogerie', '2024-01-01', NULL, 'actif', '2025-08-07 11:51:01'),
(19, 'XIX', NULL, '93', '35.00', 'Armes, munitions', '2024-01-01', NULL, 'actif', '2025-08-07 11:51:01'),
(20, 'XX', NULL, '94-96', '15.75', 'Marchandises et produits divers', '2024-01-01', NULL, 'actif', '2025-08-07 11:51:01'),
(21, 'XXI', NULL, '97', '30.00', 'Objets d\'art, de collection ou d\'antiquité', '2024-01-01', NULL, 'actif', '2025-08-07 11:51:01');

-- --------------------------------------------------------

--
-- Table structure for table `user`
--

CREATE TABLE `user` (
  `user_id` int(11) NOT NULL,
  `nom_user` varchar(100) NOT NULL,
  `identifiant_user` varchar(50) NOT NULL,
  `mot_de_passe` varchar(255) NOT NULL,
  `email` varchar(150) NOT NULL,
  `nombre_produits_classes` int(11) DEFAULT '0',
  `is_admin` tinyint(1) DEFAULT '0',
  `date_creation` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `derniere_connexion` timestamp NULL DEFAULT NULL,
  `statut_compte` enum('actif','inactif','suspendu') DEFAULT 'actif'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

--
-- Dumping data for table `user`
--

INSERT INTO `user` (`user_id`, `nom_user`, `identifiant_user`, `mot_de_passe`, `email`, `nombre_produits_classes`, `is_admin`, `date_creation`, `derniere_connexion`, `statut_compte`) VALUES
(5, 'Administrateur Système', 'momo', '$2y$10$qaycdapujJoiIbi.ip5g2.EaNCZYhX2fupd472YKKqRNTEUNOVz3m', 'admin@douane.ci', 148, 1, '2025-08-07 11:51:01', '2025-08-13 09:32:25', 'actif'),
(6, 'Marie Kouassi', 'marie.douane', '$2y$10$qaycdapujJoiIbi.ip5g2.EaNCZYhX2fupd472YKKqRNTEUNOVz3m', 'marie@douane.ci', 0, 0, '2025-08-07 11:51:01', '2025-08-07 17:06:38', 'actif'),
(7, 'Ahmed Traoré', 'ahmed.class', '$2y$10$92IXUNpkjO0rOQ5byMi.Ye4oKoEa3Ro9llC/.og/at2.uheWG/igi', 'ahmed@douane.ci', 0, 0, '2025-08-07 11:51:01', NULL, 'actif'),
(8, 'Fatou Koné', 'fatou.inspect', '$2y$10$92IXUNpkjO0rOQ5byMi.Ye4oKoEa3Ro9llC/.og/at2.uheWG/igi', 'fatou@douane.ci', 0, 0, '2025-08-07 11:51:01', NULL, 'actif'),
(9, 'serigne ndiaye', 'serigne', '$2y$10$/RVc/XhlGhdb2uIjlKRbEOlc7C7uXgWmust4buY2cnvNV1nqmHkbC', 'serigne@admin.ci', 0, 0, '2025-08-07 16:13:54', NULL, 'actif'),
(10, 'momo', 'jeann', '$2y$10$id1Rm4xcm3Yl7Gm4ra6bbusTqTBsPZx19MZH/sNm2L8z8tBM6Q1Um', 'jeansamuel@douane.ci', 0, 0, '2025-08-12 16:26:44', NULL, 'actif');

-- --------------------------------------------------------

--
-- Stand-in structure for view `vue_cedeo_complete`
-- (See below for the actual view)
--
CREATE TABLE `vue_cedeo_complete` (
`id_code` int(11)
,`code_tarifaire` varchar(20)
,`description_produit` text
,`taux_imposition` decimal(5,2)
,`unite_mesure` varchar(20)
,`notes_specifiques` text
,`code_chapitre` varchar(5)
,`titre_chapitre` text
,`code_section` varchar(5)
,`titre_section` text
,`mots_cles` text
);

-- --------------------------------------------------------

--
-- Stand-in structure for view `vue_produits_complets`
-- (See below for the actual view)
--
CREATE TABLE `vue_produits_complets` (
`id_produit` int(11)
,`origine_produit` varchar(100)
,`description_produit` text
,`numero_serie` varchar(50)
,`is_groupe` tinyint(1)
,`nombre_produits` int(11)
,`taux_imposition` decimal(5,2)
,`section_produit` varchar(5)
,`sous_section_produit` varchar(10)
,`date_classification` timestamp
,`date_modification` timestamp
,`statut_validation` enum('en_attente','valide','rejete')
,`code_tarifaire` varchar(20)
,`valeur_declaree` decimal(10,2)
,`poids_kg` decimal(8,2)
,`confidence_score` decimal(5,2)
,`methode_classification` enum('automatique','manuelle','ai')
,`nom_user` varchar(100)
,`identifiant_user` varchar(50)
,`email` varchar(150)
,`description_taux` text
,`taux_officiel` decimal(5,2)
);

-- --------------------------------------------------------

--
-- Structure for view `vue_cedeo_complete`
--
DROP TABLE IF EXISTS `vue_cedeo_complete`;

CREATE ALGORITHM=UNDEFINED DEFINER=`root`@`localhost` SQL SECURITY DEFINER VIEW `vue_cedeo_complete`  AS SELECT `ct`.`id_code` AS `id_code`, `ct`.`code_tarifaire` AS `code_tarifaire`, `ct`.`description_produit` AS `description_produit`, `ct`.`taux_imposition` AS `taux_imposition`, `ct`.`unite_mesure` AS `unite_mesure`, `ct`.`notes_specifiques` AS `notes_specifiques`, `c`.`code_chapitre` AS `code_chapitre`, `c`.`titre_chapitre` AS `titre_chapitre`, `s`.`code_section` AS `code_section`, `s`.`titre_section` AS `titre_section`, group_concat(distinct `mc`.`mot_cle` order by `mc`.`poids_recherche` DESC separator '|') AS `mots_cles` FROM (((`cedeo_codes_tarifaires` `ct` join `cedeo_chapitres` `c` on((`ct`.`code_chapitre` = `c`.`code_chapitre`))) join `cedeo_sections` `s` on((`ct`.`code_section` = `s`.`code_section`))) left join `cedeo_mots_cles` `mc` on((`ct`.`code_tarifaire` = `mc`.`code_tarifaire`))) GROUP BY `ct`.`id_code`, `ct`.`code_tarifaire`, `ct`.`description_produit`, `ct`.`taux_imposition`, `ct`.`unite_mesure`, `ct`.`notes_specifiques`, `c`.`code_chapitre`, `c`.`titre_chapitre`, `s`.`code_section`, `s`.`titre_section``titre_section`  ;

-- --------------------------------------------------------

--
-- Structure for view `vue_produits_complets`
--
DROP TABLE IF EXISTS `vue_produits_complets`;

CREATE ALGORITHM=UNDEFINED DEFINER=`root`@`localhost` SQL SECURITY DEFINER VIEW `vue_produits_complets`  AS SELECT `p`.`id_produit` AS `id_produit`, `p`.`origine_produit` AS `origine_produit`, `p`.`description_produit` AS `description_produit`, `p`.`numero_serie` AS `numero_serie`, `p`.`is_groupe` AS `is_groupe`, `p`.`nombre_produits` AS `nombre_produits`, `p`.`taux_imposition` AS `taux_imposition`, `p`.`section_produit` AS `section_produit`, `p`.`sous_section_produit` AS `sous_section_produit`, `p`.`date_classification` AS `date_classification`, `p`.`date_modification` AS `date_modification`, `p`.`statut_validation` AS `statut_validation`, `p`.`code_tarifaire` AS `code_tarifaire`, `p`.`valeur_declaree` AS `valeur_declaree`, `p`.`poids_kg` AS `poids_kg`, `p`.`confidence_score` AS `confidence_score`, `p`.`methode_classification` AS `methode_classification`, `u`.`nom_user` AS `nom_user`, `u`.`identifiant_user` AS `identifiant_user`, `u`.`email` AS `email`, `ti`.`description_taux` AS `description_taux`, `ti`.`taux_pourcentage` AS `taux_officiel` FROM ((`produits` `p` join `user` `u` on((`p`.`user_id` = `u`.`user_id`))) left join `taux_imposition` `ti` on(((`p`.`section_produit` = `ti`.`section`) and (`ti`.`statut_taux` = 'actif'))))  ;

--
-- Indexes for dumped tables
--

--
-- Indexes for table `cedeo_cache_classifications`
--
ALTER TABLE `cedeo_cache_classifications`
  ADD PRIMARY KEY (`id_cache`),
  ADD UNIQUE KEY `produit_normalise` (`produit_normalise`),
  ADD KEY `idx_produit_recherche` (`produit_recherche`),
  ADD KEY `idx_produit_normalise` (`produit_normalise`),
  ADD KEY `idx_code_tarifaire` (`code_tarifaire_trouve`),
  ADD KEY `idx_utilisation` (`nombre_utilisations`,`date_derniere_utilisation`);

--
-- Indexes for table `cedeo_chapitres`
--
ALTER TABLE `cedeo_chapitres`
  ADD PRIMARY KEY (`id_chapitre`),
  ADD UNIQUE KEY `code_chapitre` (`code_chapitre`),
  ADD KEY `idx_code_chapitre` (`code_chapitre`),
  ADD KEY `idx_section` (`code_section`);

--
-- Indexes for table `cedeo_codes_tarifaires`
--
ALTER TABLE `cedeo_codes_tarifaires`
  ADD PRIMARY KEY (`id_code`),
  ADD UNIQUE KEY `code_tarifaire` (`code_tarifaire`),
  ADD KEY `idx_code_tarifaire` (`code_tarifaire`),
  ADD KEY `idx_chapitre` (`code_chapitre`),
  ADD KEY `idx_section` (`code_section`),
  ADD KEY `idx_description` (`description_produit`(255)),
  ADD KEY `idx_cedeo_recherche_complete` (`description_produit`(255),`code_tarifaire`,`taux_imposition`);

--
-- Indexes for table `cedeo_mots_cles`
--
ALTER TABLE `cedeo_mots_cles`
  ADD PRIMARY KEY (`id_mot_cle`),
  ADD KEY `idx_mot_cle` (`mot_cle`),
  ADD KEY `idx_code_tarifaire` (`code_tarifaire`),
  ADD KEY `idx_recherche` (`mot_cle`,`poids_recherche`),
  ADD KEY `idx_cedeo_mots_cles_recherche` (`mot_cle`,`poids_recherche`,`code_tarifaire`);

--
-- Indexes for table `cedeo_sections`
--
ALTER TABLE `cedeo_sections`
  ADD PRIMARY KEY (`id_section`),
  ADD UNIQUE KEY `code_section` (`code_section`),
  ADD KEY `idx_code_section` (`code_section`);

--
-- Indexes for table `historique_classifications`
--
ALTER TABLE `historique_classifications`
  ADD PRIMARY KEY (`id_historique`),
  ADD KEY `idx_produit` (`id_produit`),
  ADD KEY `idx_user` (`user_id`),
  ADD KEY `idx_date` (`date_action`);

--
-- Indexes for table `produits`
--
ALTER TABLE `produits`
  ADD PRIMARY KEY (`id_produit`),
  ADD KEY `idx_section` (`section_produit`),
  ADD KEY `idx_user` (`user_id`),
  ADD KEY `idx_statut` (`statut_validation`),
  ADD KEY `idx_date` (`date_classification`);

--
-- Indexes for table `taux_imposition`
--
ALTER TABLE `taux_imposition`
  ADD PRIMARY KEY (`id_taux`),
  ADD KEY `idx_section` (`section`),
  ADD KEY `idx_statut` (`statut_taux`);

--
-- Indexes for table `user`
--
ALTER TABLE `user`
  ADD PRIMARY KEY (`user_id`),
  ADD UNIQUE KEY `identifiant_user` (`identifiant_user`),
  ADD UNIQUE KEY `email` (`email`);

--
-- AUTO_INCREMENT for dumped tables
--

--
-- AUTO_INCREMENT for table `cedeo_cache_classifications`
--
ALTER TABLE `cedeo_cache_classifications`
  MODIFY `id_cache` int(11) NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT for table `cedeo_chapitres`
--
ALTER TABLE `cedeo_chapitres`
  MODIFY `id_chapitre` int(11) NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT for table `cedeo_codes_tarifaires`
--
ALTER TABLE `cedeo_codes_tarifaires`
  MODIFY `id_code` int(11) NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT for table `cedeo_mots_cles`
--
ALTER TABLE `cedeo_mots_cles`
  MODIFY `id_mot_cle` int(11) NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT for table `cedeo_sections`
--
ALTER TABLE `cedeo_sections`
  MODIFY `id_section` int(11) NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT for table `historique_classifications`
--
ALTER TABLE `historique_classifications`
  MODIFY `id_historique` int(11) NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT for table `produits`
--
ALTER TABLE `produits`
  MODIFY `id_produit` int(11) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=152;

--
-- AUTO_INCREMENT for table `taux_imposition`
--
ALTER TABLE `taux_imposition`
  MODIFY `id_taux` int(11) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=22;

--
-- AUTO_INCREMENT for table `user`
--
ALTER TABLE `user`
  MODIFY `user_id` int(11) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=11;

--
-- Constraints for dumped tables
--

--
-- Constraints for table `cedeo_cache_classifications`
--
ALTER TABLE `cedeo_cache_classifications`
  ADD CONSTRAINT `cedeo_cache_classifications_ibfk_1` FOREIGN KEY (`code_tarifaire_trouve`) REFERENCES `cedeo_codes_tarifaires` (`code_tarifaire`) ON DELETE CASCADE;

--
-- Constraints for table `cedeo_chapitres`
--
ALTER TABLE `cedeo_chapitres`
  ADD CONSTRAINT `cedeo_chapitres_ibfk_1` FOREIGN KEY (`code_section`) REFERENCES `cedeo_sections` (`code_section`) ON DELETE CASCADE;

--
-- Constraints for table `cedeo_codes_tarifaires`
--
ALTER TABLE `cedeo_codes_tarifaires`
  ADD CONSTRAINT `cedeo_codes_tarifaires_ibfk_1` FOREIGN KEY (`code_chapitre`) REFERENCES `cedeo_chapitres` (`code_chapitre`) ON DELETE CASCADE,
  ADD CONSTRAINT `cedeo_codes_tarifaires_ibfk_2` FOREIGN KEY (`code_section`) REFERENCES `cedeo_sections` (`code_section`) ON DELETE CASCADE;

--
-- Constraints for table `cedeo_mots_cles`
--
ALTER TABLE `cedeo_mots_cles`
  ADD CONSTRAINT `cedeo_mots_cles_ibfk_1` FOREIGN KEY (`code_tarifaire`) REFERENCES `cedeo_codes_tarifaires` (`code_tarifaire`) ON DELETE CASCADE;
COMMIT;

/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
