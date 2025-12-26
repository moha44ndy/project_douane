-- Mettre à jour le mot de passe admin avec un hash bcrypt Python compatible
-- Mot de passe: admin
-- Hash généré avec Python bcrypt (format $2b$)

UPDATE users 
SET password_hash = '$2b$12$0Ods7Z63K0n1TtOPzUxbgesOZqf5F8rXPIwiyVIRvLY8UJEXu09V2'
WHERE identifiant_user = 'admin';

-- Vérifier que la mise à jour a réussi
SELECT user_id, identifiant_user, email, statut, is_admin 
FROM users 
WHERE identifiant_user = 'admin';

