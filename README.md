# Paie Burkina — Traitement des salaires mensuels

Application de bureau (Windows) pour saisir les employés et calculer
automatiquement la paie mensuelle selon la réglementation du Burkina Faso
(CNSS, IUTS, exonérations d'indemnités, etc.), avec deux niveaux d'accès
protégés par mot de passe.

> ⚠️ **Ce logiciel est payant.** Le message apparaît dans l'application
> (écran de connexion, bandeau principal, et pied de page des exports Excel).

## Fonctionnalités

- **Saisie des employés** : salaire de base, prime d'ancienneté, heures
  supplémentaires, sursalaire, gratification, indemnités (caisse, logement,
  fonction, transport), personnes à charge, retenues sur prêt.
- **Calcul automatique de la paie** : reproduit fidèlement les formules du
  classeur Excel d'origine (CNSS salariale plafonnée, plafond fiscal,
  abattement CADRE/AUTRE, exonération des indemnités, barème IUTS à 9
  tranches, réduction IUTS selon les personnes à charge, charges patronales).
  → **Vérifié cellule par cellule contre le fichier Excel fourni : résultats identiques.**
- **Export Excel** de l'état de paie du mois (bouton "Exporter vers Excel").
- **Deux comptes d'accès** :
  - **Administrateur** : mot de passe fixe (modifiable), accès aux
    paramètres de paie (taux, plafonds) et au mot de passe Utilisateur.
  - **Utilisateur** : accès à la saisie et au calcul uniquement ; son mot
    de passe **change automatiquement chaque 1er du mois** (dérivé d'une
    clé secrète stockée localement — l'administrateur peut le consulter
    à tout moment dans l'onglet "Sécurité", ou en forcer un manuellement).

Mot de passe administrateur par défaut à la première utilisation : `admin123`
**→ à changer immédiatement** dans l'onglet Sécurité après la première connexion.

## Où sont stockées les données ?

Dans un dossier du profil utilisateur Windows, indépendant du `.exe` :
`C:\Users\<votre nom>\PaieBurkinaData\donnees.json`
(accessible même si l'application est installée dans "Program Files").

## 1. Utilisation directe (sans compiler)

```
pip install -r requirements.txt
python main.py
```

## 2. Compiler le fichier .exe (Windows)

Sur une machine **Windows**, avec Python 3.10+ installé :

```
build_exe.bat
```

Ce script installe les dépendances et compile l'exécutable avec PyInstaller.
Le résultat se trouve dans `dist\PaieBurkina.exe` — un seul fichier, aucune
installation de Python nécessaire pour l'utilisateur final.

> Le fichier de données (mots de passe, paramètres, employés) est créé
> automatiquement au premier lancement de l'exécutable.

## 3. Publier sur GitHub

```
git init
git add .
git commit -m "Version initiale — Paie Burkina"
git branch -M main
git remote add origin https://github.com/<votre-compte>/<votre-depot>.git
git push -u origin main
```

Un workflow GitHub Actions est déjà inclus
(`.github/workflows/build-windows-exe.yml`) : il compile automatiquement
`PaieBurkina.exe` sur les serveurs Windows de GitHub et le joint à une
Release, à chaque fois que vous créez un tag `v1.0.0` par exemple :

```
git tag v1.0.0
git push origin v1.0.0
```

L'exécutable apparaît alors dans l'onglet **Releases** de votre dépôt,
prêt à être téléchargé — sans que vous ayez besoin d'un PC Windows pour
compiler vous-même.

## Sécurité — points importants

- Le mot de passe Administrateur est stocké **haché** (PBKDF2-SHA256),
  jamais en clair.
- Le mot de passe Utilisateur mensuel est dérivé par HMAC-SHA256 d'une clé
  secrète générée aléatoirement à l'installation et stockée uniquement en
  local — il n'est donc pas prévisible sans accès au poste.
- Ce mécanisme protège l'accès à l'application sur un poste donné ; il ne
  remplace pas un chiffrement de fichier ou un contrôle d'accès réseau.
  Pour une utilisation multi-postes ou multi-utilisateurs avec traçabilité,
  une évolution vers une base de données centralisée serait recommandée.

## Personnaliser les paramètres de paie

Les taux et plafonds (CNSS, IUTS, exonérations) sont modifiables par
l'administrateur dans l'onglet **Paramètres de paie**. Le barème IUTS et
la table de réduction pour charges de famille peuvent être ajustés
directement dans `payroll_engine.py` (`DEFAULT_PARAMS`) avant compilation,
ou dans le fichier `donnees.json` (bouton "Ouvrir le dossier des données").

## Limites connues / à adapter selon vos besoins

- Le calcul reproduit exactement les formules du classeur fourni, y
  compris un léger particularité du barème d'exonération de l'indemnité
  de fonction (référence croisée au plafond "Transport" dans une des
  conditions) — c'est le comportement du fichier d'origine, reproduit à
  l'identique pour rester cohérent avec vos calculs précédents.
- Il n'y a pas de sauvegarde automatique en ligne : sauvegardez
  régulièrement le dossier `PaieBurkinaData`.
