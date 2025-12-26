-- Script SQL pour créer la base de données dans Supabase (PostgreSQL)
-- Migration depuis MySQL vers PostgreSQL

-- Créer les types ENUM
CREATE TYPE user_statut_type AS ENUM ('actif', 'inactif', 'suspendu');
CREATE TYPE historique_action_type AS ENUM ('creation', 'modification', 'validation', 'rejet');
CREATE TYPE feedback_rating_type AS ENUM ('up', 'down');

-- Table users
CREATE TABLE users (
    user_id SERIAL PRIMARY KEY,
    nom_user VARCHAR(100) NOT NULL,
    identifiant_user VARCHAR(50) NOT NULL UNIQUE,
    email VARCHAR(150) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    statut user_statut_type DEFAULT 'actif',
    is_admin BOOLEAN DEFAULT FALSE,
    date_creation TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    derniere_connexion TIMESTAMP NULL
);

-- Table classifications
CREATE TABLE classifications (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(user_id) ON UPDATE CASCADE,
    description_produit TEXT NOT NULL,
    valeur_produit VARCHAR(100) DEFAULT NULL,
    origine_produit VARCHAR(100) DEFAULT NULL,
    code_tarifaire VARCHAR(20) DEFAULT NULL,
    section VARCHAR(10) DEFAULT NULL,
    chapitre VARCHAR(10) DEFAULT NULL,
    confidence_score DECIMAL(5,2) DEFAULT NULL,
    taux_dd VARCHAR(50) DEFAULT NULL,
    taux_rs VARCHAR(50) DEFAULT NULL,
    taux_tva VARCHAR(50) DEFAULT NULL,
    unite_mesure VARCHAR(50) DEFAULT NULL,
    justification TEXT DEFAULT NULL,
    date_classification TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    date_modification TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    user_query TEXT DEFAULT NULL,
    user_query_hash VARCHAR(64) DEFAULT NULL,
    feedback_rating feedback_rating_type DEFAULT NULL,
    statut_validation VARCHAR(20) DEFAULT 'en_attente',
    id_validateur INTEGER DEFAULT NULL REFERENCES users(user_id) ON UPDATE CASCADE,
    date_validation TIMESTAMP NULL,
    commentaire_validation TEXT DEFAULT NULL
);

-- Table historique
CREATE TABLE historique (
    id_historique SERIAL PRIMARY KEY,
    classification_id INTEGER NOT NULL REFERENCES classifications(id) ON DELETE CASCADE ON UPDATE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(user_id) ON UPDATE CASCADE,
    action historique_action_type NOT NULL,
    ancien_code_tarifaire VARCHAR(20) DEFAULT NULL,
    nouveau_code_tarifaire VARCHAR(20) DEFAULT NULL,
    ancien_statut VARCHAR(20) DEFAULT NULL,
    nouveau_statut VARCHAR(20) DEFAULT NULL,
    commentaire TEXT DEFAULT NULL,
    date_action TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Index pour classifications
CREATE INDEX idx_classifications_user ON classifications(user_id);
CREATE INDEX idx_classifications_date ON classifications(date_classification);
CREATE INDEX idx_classifications_code_tarifaire ON classifications(code_tarifaire);
CREATE INDEX idx_classifications_section ON classifications(section);
CREATE INDEX idx_classifications_query_hash ON classifications(user_query_hash);
CREATE INDEX idx_classifications_feedback_rating ON classifications(feedback_rating);
CREATE INDEX idx_classifications_statut_validation ON classifications(statut_validation);

-- Index pour historique
CREATE INDEX idx_historique_classification ON historique(classification_id);
CREATE INDEX idx_historique_user ON historique(user_id);
CREATE INDEX idx_historique_date ON historique(date_action);

-- Index pour users
CREATE INDEX idx_users_statut ON users(statut);

-- Trigger pour mettre à jour date_modification automatiquement
CREATE OR REPLACE FUNCTION update_date_modification()
RETURNS TRIGGER AS $$
BEGIN
    NEW.date_modification = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_date_modification
    BEFORE UPDATE ON classifications
    FOR EACH ROW
    EXECUTE FUNCTION update_date_modification();

-- Vue pour les classifications complètes
CREATE OR REPLACE VIEW vue_classifications_completes AS
SELECT 
    c.id,
    c.description_produit,
    c.valeur_produit,
    c.origine_produit,
    c.code_tarifaire,
    c.section,
    c.chapitre,
    c.confidence_score,
    c.taux_dd,
    c.taux_rs,
    c.taux_tva,
    c.unite_mesure,
    c.justification,
    c.statut_validation,
    c.date_classification,
    c.date_modification,
    u.nom_user AS nom_classificateur,
    u.identifiant_user AS identifiant_classificateur,
    uv.nom_user AS nom_validateur,
    uv.identifiant_user AS identifiant_validateur,
    c.date_validation
FROM classifications c
JOIN users u ON c.user_id = u.user_id
LEFT JOIN users uv ON c.id_validateur = uv.user_id;

-- Fonction pour obtenir les statistiques utilisateur
CREATE OR REPLACE FUNCTION GetUserStats(p_user_id INTEGER)
RETURNS TABLE (
    nom_user VARCHAR(100),
    identifiant_user VARCHAR(50),
    email VARCHAR(150),
    total_classifications BIGINT,
    validees BIGINT,
    en_attente BIGINT,
    rejetees BIGINT,
    confidence_moyenne NUMERIC,
    derniere_classification TIMESTAMP
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        u.nom_user,
        u.identifiant_user,
        u.email,
        COUNT(c.id)::BIGINT AS total_classifications,
        SUM(CASE WHEN c.statut_validation = 'valide' THEN 1 ELSE 0 END)::BIGINT AS validees,
        SUM(CASE WHEN c.statut_validation = 'en_attente' THEN 1 ELSE 0 END)::BIGINT AS en_attente,
        SUM(CASE WHEN c.statut_validation = 'rejete' THEN 1 ELSE 0 END)::BIGINT AS rejetees,
        AVG(c.confidence_score) AS confidence_moyenne,
        MAX(c.date_classification) AS derniere_classification
    FROM users u
    LEFT JOIN classifications c ON u.user_id = c.user_id
    WHERE u.user_id = p_user_id
    GROUP BY u.user_id, u.nom_user, u.identifiant_user, u.email;
END;
$$ LANGUAGE plpgsql;

-- Fonction pour valider une classification
CREATE OR REPLACE FUNCTION ValiderClassification(
    p_classification_id INTEGER,
    p_validateur_id INTEGER,
    p_commentaire TEXT DEFAULT NULL
)
RETURNS VOID AS $$
BEGIN
    -- Mettre à jour la classification
    UPDATE classifications 
    SET statut_validation = 'valide',
        id_validateur = p_validateur_id,
        date_validation = CURRENT_TIMESTAMP,
        commentaire_validation = p_commentaire,
        date_modification = CURRENT_TIMESTAMP
    WHERE id = p_classification_id;
    
    -- Ajouter une entrée dans l'historique
    INSERT INTO historique (
        classification_id, user_id, action, commentaire
    ) VALUES (
        p_classification_id, p_validateur_id, 'validation', 
        COALESCE(p_commentaire, 'Classification validée')
    );
END;
$$ LANGUAGE plpgsql;

-- Insérer l'utilisateur administrateur par défaut
-- Mot de passe: admin (hash bcrypt)
INSERT INTO users (nom_user, identifiant_user, email, password_hash, statut, is_admin)
VALUES (
    'Administrateur Système',
    'admin',
    'admin@douane.ci',
    '$2y$10$vMJTyG/p853epmwAVWXtB.IuW9m1edNeb3KCG3KyAKcYUU9.8WK02',
    'actif',
    TRUE
) ON CONFLICT (identifiant_user) DO NOTHING;

-- Commentaires pour documentation
COMMENT ON TABLE users IS 'Table des utilisateurs du système';
COMMENT ON TABLE classifications IS 'Table des classifications de produits';
COMMENT ON TABLE historique IS 'Table d''historique des actions sur les classifications';
COMMENT ON COLUMN classifications.feedback_rating IS 'Note utilisateur: up (👍) ou down (👎)';
COMMENT ON COLUMN classifications.user_query IS 'Requête originale de l''utilisateur';
COMMENT ON COLUMN classifications.user_query_hash IS 'Hash de la requête pour recherche rapide';

