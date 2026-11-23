"""Jeu de donnees commun aux tests : base SQLite en memoire recreee pour chaque test."""
import os
import sys
from datetime import date, time, timedelta

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from models import db, User, Matiere, Disponibilite

DEMAIN = date.today() + timedelta(days=1)


@pytest.fixture
def ctx():
    """Retourne (app, matiere, apprenant a, apprenant b, tuteur t).

    Le tuteur t enseigne la matiere et est disponible demain de 14h a 18h.
    Les dates sont relatives a aujourd'hui pour que les tests restent valides.
    """
    app = create_app({'TESTING': True, 'SQLALCHEMY_DATABASE_URI': 'sqlite:///:memory:'})
    with app.app_context():
        m = Matiere(nom='SQL')
        a, b, t = (User(nom=n, email=f'{n}@x.tn', password_hash='x') for n in 'abt')
        t.matieres = [m]
        t.disponibilites = [Disponibilite(jour_semaine=DEMAIN.weekday(), debut=time(14), fin=time(18))]
        db.session.add_all([m, a, b, t])
        db.session.commit()
        yield app, m, a, b, t
