-- phpMyAdmin SQL Dump
-- version 5.1.2
-- https://www.phpmyadmin.net/
--
-- Host: localhost:4240
-- Generation Time: Dec 13, 2025 at 06:13 PM
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
  `date_modification` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

--
-- Dumping data for table `classifications`
--

INSERT INTO `classifications` (`id`, `user_id`, `description_produit`, `valeur_produit`, `origine_produit`, `code_tarifaire`, `section`, `chapitre`, `confidence_score`, `taux_dd`, `taux_rs`, `taux_tva`, `unite_mesure`, `justification`, `date_classification`, `date_modification`) VALUES
(1, 1, 'Voiture (véhicule automobile pour le transport de personnes)', 'Non renseigné', 'Non renseigné', '8703.23.00.00', 'XVII', '87', '92.00', NULL, NULL, NULL, NULL, NULL, '2025-12-13 16:13:02', '2025-12-13 16:20:36'),
(2, 1, 'Téléphone intelligent (smartphone)', 'Non renseigné', 'Non renseigné', '8517.13.00.00', 'XVI', '85', '90.00', NULL, NULL, NULL, NULL, NULL, '2025-12-13 16:13:02', '2025-12-13 16:20:36'),
(3, 1, 'Cheval vivant (équidé)', 'Non renseigné', 'Non renseigné', '0101.10.00.00', 'I', '01', '75.00', NULL, NULL, NULL, NULL, NULL, '2025-12-13 16:24:36', '2025-12-13 16:24:36'),
(12, 1, 'Produit de test', '1000', 'France', '1234.56.78.90', 'I', '12', '95.00', '5 %', '1 %', '18 %', 'PIÈCE', 'Test d\'insertion', '2025-12-13 17:12:07', '2025-12-13 17:12:07'),
(13, 1, 'Lait non concentré (entier ou écrémé)', 'Non renseigné', 'Non renseigné', '0401.10.00.00', 'I', '04', '85.00', 'Non renseigné', 'Non renseigné', 'Non renseigné', 'LITRE', 'RGI 1 et notes du Chapitre 04: lait et produits de la laiterie; lait entier ou écrémé non concentré.', '2025-12-13 17:13:42', '2025-12-13 17:13:42');

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

--
-- Dumping data for table `historique`
--

INSERT INTO `historique` (`id_historique`, `classification_id`, `user_id`, `action`, `ancien_code_tarifaire`, `nouveau_code_tarifaire`, `ancien_statut`, `nouveau_statut`, `commentaire`, `date_action`) VALUES
(1, 1, 1, 'creation', NULL, '8703.23.00.00', NULL, 'en_attente', NULL, '2025-12-13 16:13:02'),
(2, 2, 1, 'creation', NULL, '8517.13.00.00', NULL, 'en_attente', NULL, '2025-12-13 16:13:02'),
(3, 3, 1, 'creation', NULL, '0101.10.00.00', NULL, 'en_attente', NULL, '2025-12-13 16:24:36');

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
  `derniere_connexion` timestamp NULL DEFAULT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

--
-- Dumping data for table `users`
--

INSERT INTO `users` (`user_id`, `nom_user`, `identifiant_user`, `email`, `password_hash`, `statut`, `is_admin`, `date_creation`, `derniere_connexion`) VALUES
(1, 'Administrateur Système', 'admin', 'admin@douane.ci', '$2y$10$vMJTyG/p853epmwAVWXtB.IuW9m1edNeb3KCG3KyAKcYUU9.8WK02', 'actif', 1, '2025-12-13 13:58:38', '2025-12-13 18:08:09'),
(2, 'Test User', 'test.user', 'test.user@douane.ci', '$2b$12$aA0Im/GKA/.mgV/zxAS.2.ZaPCNcolGOiv59OhPuQPr75DcKMzXBO', 'actif', 0, '2025-12-13 17:16:49', NULL),
(3, 'Test Admin', 'test.admin', 'test.admin@douane.ci', '$2b$12$h3y17UksjNqfhLXyEv93NOn5xkHc4ymqobOOyhhlXILVE1GjBbq5a', 'actif', 1, '2025-12-13 17:16:50', NULL),
(4, 'samuel', '1234567X', 'samuel@douanier.ci', '$2b$12$ZEEO9LRynrdVx/bBXSO5E.hrEYpnHw3ns5pjA2ilMhVJPdHH9trPW', 'actif', 1, '2025-12-13 17:18:05', NULL);

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
  ADD KEY `idx_section` (`section`);

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
-- AUTO_INCREMENT for dumped tables
--

--
-- AUTO_INCREMENT for table `classifications`
--
ALTER TABLE `classifications`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=14;

--
-- AUTO_INCREMENT for table `historique`
--
ALTER TABLE `historique`
  MODIFY `id_historique` int(11) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=4;

--
-- AUTO_INCREMENT for table `users`
--
ALTER TABLE `users`
  MODIFY `user_id` int(11) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=5;

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
COMMIT;

/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
