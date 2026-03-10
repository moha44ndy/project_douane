# MOSAM — Design Rules
## Outil de Classification Tarifaire CEDEAO / Douane Ivoirienne
### Direction : Institutionnel propre · Desktop + Tablette

---

## PALETTE

```
--color-bg:          #f8f7f4   /* fond principal — blanc cassé chaud */
--color-surface:     #ffffff   /* cartes, panneaux */
--color-surface-2:   #f1f0ec   /* fond secondaire, zebra rows */
--color-border:      #e2e0d8   /* bordures subtiles */
--color-border-strong: #c8c4b8 /* bordures actives, focus */

--color-primary:     #1a4a2e   /* vert foncé institutionnel */
--color-primary-mid: #2d6b47   /* vert moyen — hover, accents */
--color-primary-light: #e8f2ec /* vert très clair — backgrounds actifs */
--color-primary-text: #ffffff  /* texte sur fond vert */

--color-accent:      #c8a84b   /* or ivoirien — badges, highlights critiques */
--color-accent-light: #faf3e0  /* fond badge or */

--color-text-1:      #1c1917   /* texte primaire */
--color-text-2:      #57534e   /* texte secondaire */
--color-text-3:      #a8a29e   /* texte muted, placeholders */

--color-success:     #166534
--color-success-bg:  #dcfce7
--color-error:       #991b1b
--color-error-bg:    #fee2e2
--color-warning:     #92400e
--color-warning-bg:  #fef3c7
```

---

## 1. LAYOUT GLOBAL

- App shell : sidebar fixe gauche (240px) + contenu principal
- Contenu principal : `max-width: 1200px`, `margin: 0 auto`, `padding: 32px 40px`
- Sur tablette (< 1024px) : sidebar repliable en overlay
- Fond de page : `--color-bg` (#f8f7f4)
- Pas de fond blanc sur body — le blanc est réservé aux cartes

---

## 2. SIDEBAR

- Largeur : 240px, fixe
- Background : `--color-primary` (#1a4a2e)
- Logo/titre : blanc, 15px, font-weight 700
- Nav items : padding 10px 20px, color rgba(255,255,255,0.7)
- Nav item actif : background rgba(255,255,255,0.12), color #ffffff, border-left: 3px solid `--color-accent`
- Nav item hover : background rgba(255,255,255,0.08)
- Section labels : 11px uppercase, rgba(255,255,255,0.4), letter-spacing 1px, padding 16px 20px 6px
- Border-right : none — pas de bordure, la couleur suffit

---

## 3. CARTES / PANNEAUX

- Background : #ffffff
- Border : 1px solid `--color-border`
- Border-radius : 8px
- Box-shadow : 0 1px 3px rgba(0,0,0,0.06)
- Padding : 24px
- **Les cartes SONT autorisées** ici — c'est une app de bureau, pas un feed social

---

## 4. TYPOGRAPHIE

Fonts à utiliser :
- Display/Titres : `'DM Serif Display'` ou `'Playfair Display'` — caractère institutionnel
- Corps/UI : `'DM Sans'` ou `'Instrument Sans'` — lisible, neutre
- Monospace (codes SH) : `'JetBrains Mono'` ou `'Fira Code'`

Échelle :
- Page title : 22px, font-weight 700, color `--color-text-1`
- Section title : 16px, font-weight 600, color `--color-text-1`
- Card title : 14px, font-weight 600, color `--color-text-1`
- Body : 14px, font-weight 400, color `--color-text-2`, line-height 1.6
- Label/meta : 12px, font-weight 500, color `--color-text-3`
- Code SH : 13px monospace, background `--color-surface-2`, padding 2px 6px, border-radius 4px

---

## 5. BOUTONS

- **Primaire** : background `--color-primary`, color white, height 40px, border-radius 6px, font-weight 600, padding 0 20px
- **Primaire hover** : background `--color-primary-mid`
- **Secondaire** : background white, border: 1px solid `--color-border-strong`, color `--color-text-1`, height 40px, border-radius 6px
- **Ghost** : background none, border none, color `--color-primary`, padding 0
- **Destructif** : background `--color-error`, color white
- Taille minimale : height 36px (compact), 40px (normal)
- Border-radius : 6px — jamais pill, jamais 0

---

## 6. INPUTS / FORMULAIRES

- Border : 1px solid `--color-border`
- Border-radius : 6px
- Background : #ffffff
- Height : 40px (input), auto (textarea)
- Focus : border-color `--color-primary`, box-shadow 0 0 0 3px rgba(26,74,46,0.1)
- Placeholder : `--color-text-3`
- Label : 13px, font-weight 500, color `--color-text-2`, margin-bottom 6px
- **Différent de l'app sociale** : les inputs PEUVENT avoir un border complet ici

---

## 7. TABLEAUX (résultats SH)

- Header : background `--color-surface-2`, font-size 12px uppercase, font-weight 600, color `--color-text-3`, letter-spacing 0.5px
- Row : border-bottom 1px solid `--color-border`, height 48px, padding 0 16px
- Row hover : background `--color-primary-light`
- Code SH : font monospace, font-weight 700, color `--color-primary`
- Taux de droit : badge avec background selon criticité

---

## 8. BADGES / TAGS

- Base : padding 2px 10px, border-radius 4px, font-size 12px, font-weight 600
- **Vert (conforme)** : background `--color-success-bg`, color `--color-success`
- **Or (attention)** : background `--color-accent-light`, color `--color-warning`
- **Rouge (erreur)** : background `--color-error-bg`, color `--color-error`
- **Gris (neutre)** : background `--color-surface-2`, color `--color-text-2`
- Code SH : background `--color-primary-light`, color `--color-primary`, font monospace

---

## 9. HEADER DE PAGE

- Pas de top header fixe — navigation dans la sidebar
- Breadcrumb en haut du contenu : 13px, color `--color-text-3`, separator "/"
- Titre de page dessous : 22px, font-weight 700
- Sous-titre/description : 14px, color `--color-text-2`, margin-top 4px

---

## 10. RÉSULTATS DE CLASSIFICATION

Structure d'un résultat SH :
```
[Badge confiance] Code SH · Description
Taux de droit : X% · Section : XXX · Chapitre : XX
[Bouton Valider] [Bouton Voir détail]
```
- Code SH en grand : 20px, monospace, font-weight 700, color `--color-primary`
- Description : 14px, color `--color-text-1`
- Métadonnées : 13px, color `--color-text-3`
- Border-left : 4px solid `--color-primary` sur le bloc résultat principal

---

## 11. ÉTATS VIDES / LOADING

- Skeleton : background `--color-surface-2`, shimmer animation
- Empty state : icône 40px + titre 15px + sous-titre 13px, tout centré, color `--color-text-3`
- Loading spinner : color `--color-primary`

---

## 12. RESPONSIVE TABLETTE (768px–1024px)

- Sidebar : cachée par défaut, hamburger menu en haut gauche
- Contenu : padding 24px
- Cards : une colonne au lieu de deux
- Tableau : scroll horizontal si nécessaire

---

## INTERDICTIONS SPÉCIFIQUES À CE PROJET

- ❌ Pas de fond sombre (dark mode) — institutionnel = clair
- ❌ Pas d'orange — pas de lien avec l'app sociale
- ❌ Pas de bordures pill (border-radius > 8px sur les boutons)
- ❌ Pas d'animations non fonctionnelles
- ❌ Jamais de vert vif (#00ff00 style) — uniquement le vert institutionnel sombre
- ❌ Pas d'emoji dans l'UI finale (les enlever du code actuel)
