# ijaTaalem

Plateforme web d'entraide entre étudiants : un apprenant trouve un tuteur disponible sur son créneau, demande une séance, puis note l'aide reçue. Les tuteurs cumulent des points et des badges.

![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB)
![Flask](https://img.shields.io/badge/Flask-3.x-000000)
![Tests](https://img.shields.io/badge/tests-pytest-0A9EDC)

Projet de L2-CS, ISI, Université Tunis El Manar (2026/2027), réalisé par **Lina Chihi** pour la matière *Outils de travail collaboratif*.

## Fonctionnalités

| Rôle | Fonctionnalités |
|---|---|
| Visiteur | Consulter l'accueil, rechercher des tuteurs, aide rapide, s'inscrire, se connecter |
| Apprenant | Demander, suivre et annuler une séance, noter un tuteur |
| Tuteur | Déclarer ses matières et disponibilités, accepter ou refuser, terminer une séance, consulter ses points et son badge |
| Administrateur | Gérer les matières, supprimer un compte |


## Technologies

Python 3.10+, Flask 3, SQLite (Flask-SQLAlchemy), Jinja2, Bootstrap 5, pytest.

## Installation

```bash
git clone https://github.com/<utilisateur>/ijaTaalem.git
cd ijaTaalem
python -m venv venv
source venv/bin/activate        # Windows : venv\Scripts\activate
pip install -r requirements.txt
flask --app app seed            # données de démonstration
flask --app app run --debug     # http://127.0.0.1:5000
```

## Configuration

| Variable | Rôle | Défaut |
|---|---|---|
| `SECRET_KEY` | Clé de signature des sessions (à définir en production) | Valeur de développement |
| `DATABASE_URL` | Base de données | `sqlite:///ijataalem.db` |

## Utilisation

Comptes créés par `seed` (développement uniquement, mots de passe publics) :

| Rôle | E-mail | Mot de passe |
|---|---|---|
| Administrateur | `admin@isi.tn` | `admin123` |
| Tuteurs | `tuteur1@isi.tn` à `tuteur3@isi.tn` | `motdepasse` |

Créer un administrateur sans données de démonstration :

```bash
flask --app app create-admin --email admin@exemple.tn
```

## Tests

```bash
pytest -v
```

26 tests sur une base SQLite en mémoire : règles de gestion (`tests/test_regles.py`), routes, accès et formulaires (`tests/test_routes.py`).

## Structure

```text
ijaTaalem/
├── app.py          routes, commandes seed et create-admin
├── models.py       modèles et règles de gestion
├── templates/      pages HTML (Jinja2)
├── static/         Bootstrap, styles
└── tests/          tests pytest
```

## Limites connues

- Pas de protection CSRF ni de limitation des tentatives de connexion.
- La durée des séances et les disponibilités des tuteurs ne sont pas contrôlées à la création d'une demande.
- L'appartenance à l'ISI n'est pas vérifiée à l'inscription.

## Licence

Projet académique. Licence non définie.
