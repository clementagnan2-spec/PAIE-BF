# Reprise de conversation — Paie Burkina

Ce document résume tout le contexte du projet pour continuer le travail
dans une nouvelle conversation Claude. Collez ce fichier (ou uploadez-le
avec le zip du projet) au tout début de la nouvelle discussion, avec un
message du type : *"Voici le contexte complet de mon projet, on continue
à partir de là"*.

## 1. Le projet

**Paie Burkina** : logiciel de bureau (Windows, `.exe`) de traitement de la
paie mensuelle pour le Burkina Faso — écrit en Python/Tkinter, compilé en
`.exe` via PyInstaller, avec compilation automatique par **GitHub Actions**.

- Dépôt GitHub : `clementagnan2-spec/PAIE-BF` (public)
- Workflow de compilation : `.github/workflows/main.yml` (renommé ainsi
  sur GitHub ; dans ce zip il s'appelle encore `build-windows-exe.yml`,
  même contenu)
- C'est un **logiciel payant**, destiné à être vendu/distribué à
  **plusieurs clients différents**, tous avec le même `.exe`.
- Message affiché dans le logiciel : *"Ce logiciel de paie est payant :
  consultanter280@gmail.com"*

## 2. Comment compiler / publier une nouvelle version

1. Remplacer les fichiers modifiés dans le dépôt GitHub (voir liste des
   fichiers ci-dessous — **toujours vérifier lesquels ont changé**, une
   confusion passée a cassé l'appli car `payroll_engine.py` n'avait pas
   été mis à jour en même temps que `main.py`)
2. Aller dans l'onglet **Actions** du dépôt → workflow **"Compiler
   PaieBurkina.exe"** → bouton **"Run workflow"** (branche `main`)
3. Attendre 3-6 minutes que le run devienne vert ✅
4. Cliquer sur le run → **Summary** → section **Artifacts** →
   télécharger **PaieBurkina-exe** (fichier `.zip` contenant le `.exe`)

Un tag Git (`git tag v1.0.0 && git push origin v1.0.0`) déclenche en plus
la publication automatique dans une Release GitHub (pas juste un artefact
de run).

## 3. Fichiers du projet (tous inclus dans le zip joint)

| Fichier | Rôle |
|---|---|
| `main.py` | Toute l'interface Tkinter (écrans, onglets) |
| `payroll_engine.py` | Moteur de calcul de paie (formules CNSS/IUTS...) + `Employee` (dataclass) |
| `auth.py` | Authentification : mot de passe Admin fixe + génération du mot de passe Utilisateur mensuel |
| `storage.py` | Sauvegarde locale JSON (`donnees.json`) |
| `expiration.py` | Verrou de date d'expiration du logiciel |
| `requirements.txt` | Dépendances Python (`openpyxl`, `reportlab`, `pyinstaller`) |
| `build_exe.bat` | Script de compilation locale Windows |
| `.github/workflows/*.yml` | Compilation automatique GitHub Actions |
| `README.md` | Documentation utilisateur complète |

**Règle importante** : quand une modification touche la structure de
`Employee` (dans `payroll_engine.py`) ET son utilisation (dans `main.py`),
**toujours renvoyer les deux fichiers ensemble**, jamais un seul.

## 4. État actuel du système de sécurité / licence (le plus important à retenir)

C'est le sujet le plus travaillé dans la conversation précédente, à bien
comprendre avant de continuer :

### Mot de passe Administrateur
- **Fixe, intégré dans le code** (`auth.py`, constante `ADMIN_PASSWORD`)
- Valeur actuelle : **`ouaga2001@@@`**
- **Identique sur toutes les installations** de tous les clients (choix
  assumé : seul le développeur/consultant utilise le rôle Admin, les
  clients n'utilisent que le rôle Utilisateur)
- Non modifiable depuis l'application (le bouton a été retiré exprès)
- Pour le changer : modifier `ADMIN_PASSWORD` dans `auth.py`, recompiler,
  redistribuer un nouveau `.exe` à tous les clients

### Mot de passe Utilisateur
- Change **automatiquement chaque mois**
- Généré par HMAC-SHA256(clé secrète propre à l'installation + mois en
  cours) — imprévisible sans connaître la clé
- La **clé secrète est aléatoire et propre à chaque installation** (donc
  un mot de passe valable chez un client ne marche pas chez un autre)
- **Premier mois d'utilisation** : mot de passe par défaut connu
  `user123`
- L'admin peut voir/forcer le mot de passe du mois dans l'onglet
  **Sécurité**
- ⚠️ **PROBLÈME CONNU, PAS ENCORE RÉSOLU** : si quelqu'un supprime le
  fichier `donnees.json`, `user123` redevient valable pour le mois en
  cours (recomptage non désiré). Il a été demandé au moins deux fois à
  l'utilisateur s'il veut que je corrige ça, **sans réponse claire à ce
  jour** — c'est la première chose à trancher si le sujet ressort.

### Date d'expiration du logiciel
- Date figée dans le code (`expiration.py`, constante
  `BUILD_EXPIRATION_DATE`), actuellement **30/09/2026**
- Passé cette date : écran de blocage total, avant même l'écran de
  connexion (`ExpiredScreen` dans `main.py`)
- L'admin peut **prolonger** depuis l'onglet Sécurité (champ "Prolonger
  jusqu'au JJ/MM/AAAA") → enregistré dans `donnees.json`
  (`access_extended_until`)
- La date effective = la **plus tardive** entre la date figée et la
  prolongation → supprimer `donnees.json` ne peut **jamais avantager**
  quelqu'un, seulement faire perdre la prolongation accordée
- **Pour renouveler un client** (ex: reconduction mensuelle) : changer
  `BUILD_EXPIRATION_DATE` dans `expiration.py`, recompiler, renvoyer le
  `.exe`

### Stockage des données
- Fichier JSON local : `C:\Users\<nom>\PaieBurkinaData\donnees.json`
- **Dossier visible** (pas caché) — une version "dossier caché dans
  AppData + écran de configuration initiale sans mot de passe par
  défaut" avait été développée puis **explicitement annulée** par
  l'utilisateur ("retourne à la précédente version"). Ne pas la
  réintroduire sans redemander confirmation.

## 5. Fonctionnalités du logiciel (toutes développées et testées)

- **Saisie des employés** : formulaire + tableau, avec import en masse
  depuis Excel (`.xlsx`) ou CSV (détection auto de la bonne feuille,
  tolère les encodages Windows-1252/Latin-1, montants avec "FCFA"/espaces)
- **Moteur de calcul** : reproduit fidèlement le classeur Excel d'origine
  du client (CNSS, IUTS à 9 tranches, abattements CADRE/AUTRE,
  exonérations d'indemnités, réduction IUTS selon personnes à charge) —
  vérifié cellule par cellule contre le fichier Excel fourni au début,
  zéro écart
- **État de paie** : tableau + export Excel, filtrable par période
  (mois/année) ou "toutes périodes confondues"
- **Bulletins de paie PDF** : individuels ou en masse, avec détail ligne
  par ligne des gains, en-tête/pied de page personnalisables (Paramètres
  → section 5), **logo d'entreprise uploadable** (PNG/JPG, stocké en
  base64 dans le JSON — ⚠️ ne se transmet PAS automatiquement à un
  nouveau client, il faut soit le reconfigurer sur chaque poste, soit
  l'intégrer par défaut dans le code — **question posée à l'utilisateur,
  réponse en attente**)
- **Écritures comptables** : génère une écriture de paie en partie double
  (Débit/Crédit) équilibrée, avec son propre filtre de période, export Excel
- **Simulateur de bulletin** : on entre un **net souhaité**, le logiciel
  retrouve le salaire de base par dichotomie (fonction
  `find_base_for_target_net` dans `payroll_engine.py`), avec option
  d'indemnités "optimisées" aux plafonds fiscaux exonérés ; bouton pour
  créer directement l'employé à partir du résultat
- **Formatage** : tous les montants affichés avec séparateur de milliers
  (espace) et sans décimales inutiles dans tous les tableaux/menus

## 6. Bugs corrigés au cours du développement (pour référence, déjà réglés)

- Le panneau de saisie était poussé hors écran par un tableau trop large
  → corrigé (ordre d'empilement Tkinter + `pack_propagate(False)`)
- Export Excel plantait (`'MergedCell' object has no attribute
  'column_letter'`) à cause d'un titre fusionné → corrigé avec
  `get_column_letter(i)` au lieu de `col[0].column_letter`
- Toute erreur imprévue est maintenant affichée dans une boîte de dialogue
  (`App.report_callback_exception`) plutôt que silencieuse (important car
  le `.exe` est compilé en mode `--windowed`, sans console visible)

## 7. Pistes évoquées mais PAS développées (juste discutées)

- **Architecture client/serveur avec Tailscale** : séparer `core.py` en
  serveur (données centralisées) + client (interface actuelle), relié via
  Tailscale (VPN privé, pas besoin d'exposer de port). Idée mise de côté
  ("on garde ça en tête"), pas commencée.
- **Faux positifs antivirus** sur le `.exe` PyInstaller : solutions
  évoquées (exclusion Windows Defender, soumission à Microsoft pour
  whitelist, éventuellement passer en mode `--onedir` au lieu de
  `--onefile`) — pas implémenté, question restée ouverte côté utilisateur.

## 8. Style de travail attendu (observé sur toute la conversation)

- L'utilisateur communique en français, teste sur Windows via des
  captures d'écran, compile via GitHub Actions (pas de Windows local pour
  moi)
- Toujours **tester la logique en Python pur avant de livrer** (le
  sandbox n'a pas Tkinter installé, mais tout le reste — `openpyxl`,
  `reportlab`, calculs — fonctionne et doit être vérifié par des scripts
  de test avant chaque livraison)
- Toujours préciser **exactement quels fichiers ont changé** à chaque
  livraison (l'utilisateur ne remplace que ce qu'on lui indique)
- L'utilisateur pose parfois des **questions pures sans vouloir de code**
  ("je veux poser une question mais tu ne code pas") — bien distinguer
  question et demande d'implémentation avant d'agir
