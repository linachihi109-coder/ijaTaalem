"""Tests des routes Flask : acces, droits, unicite de l'e-mail (R7, R8)."""
from datetime import time

from conftest import DEMAIN
from models import db, User, Seance, Matiere, creer_demande


def connecter(client, email, mdp):
    return client.post('/connexion', data={'email': email, 'mdp': mdp}, follow_redirects=True)


def test_mot_de_passe_hache(ctx):
    """Securite : le mot de passe n'est jamais stocke en clair."""
    app, *_ = ctx
    client = app.test_client()
    client.post('/inscription', data={'nom': 'Lina', 'email': 'lina@isi.tn', 'mdp': 'secret123'})
    u = User.query.filter_by(email='lina@isi.tn').first()
    assert u is not None and u.password_hash != 'secret123' and u.check_password('secret123')


def test_inscription_email_deja_utilise(ctx):
    """R7."""
    app, *_ = ctx
    client = app.test_client()
    data = {'nom': 'Lina', 'email': 'lina@isi.tn', 'mdp': 'secret123'}
    client.post('/inscription', data=data)
    client.get('/deconnexion')
    reponse = client.post('/inscription', data=data)
    assert 'déjà utilisé' in reponse.get_data(as_text=True)
    assert User.query.filter_by(email='lina@isi.tn').count() == 1


def test_tableau_de_bord_exige_connexion(ctx):
    app, *_ = ctx
    reponse = app.test_client().get('/tableau-de-bord')
    assert reponse.status_code == 302 and '/connexion' in reponse.headers['Location']


def test_admin_interdit_aux_etudiants(ctx):
    app, *_ = ctx
    client = app.test_client()
    client.post('/inscription', data={'nom': 'Lina', 'email': 'lina@isi.tn', 'mdp': 'secret123'})
    assert client.get('/admin').status_code == 403


def test_matiere_utilisee_non_supprimable(ctx):
    """R8 : une matiere liee a une seance reste en base."""
    app, m, a, _, t = ctx
    creer_demande(a, t, m, DEMAIN, time(14), time(15))
    admin = User(nom='Admin', email='admin@x.tn', is_admin=True)
    admin.set_password('admin123')
    db.session.add(admin)
    db.session.commit()
    client = app.test_client()
    connecter(client, 'admin@x.tn', 'admin123')
    client.post(f'/admin/matiere/{m.id}/supprimer')
    assert db.session.get(Matiere, m.id) is not None


import pytest


@pytest.mark.parametrize('nom,email,mdp', [('', 'a@b.tn', 'secret123'),
                                           ('Lina', 'sans-arobase', 'secret123'),
                                           ('Lina', 'a@b.tn', '12345')])
def test_inscription_champs_invalides(ctx, nom, email, mdp):
    """Validation serveur : nom vide, e-mail sans arobase, mot de passe de 5 caracteres."""
    app, *_ = ctx
    reponse = app.test_client().post('/inscription', data={'nom': nom, 'email': email, 'mdp': mdp})
    assert 'requis' in reponse.get_data(as_text=True)
    assert User.query.filter_by(email=email).count() == 0


def test_connexion_refusee(ctx):
    """Authentification : mauvais mot de passe, pas de session ouverte."""
    app, *_ = ctx
    client = app.test_client()
    client.post('/inscription', data={'nom': 'Lina', 'email': 'lina@isi.tn', 'mdp': 'secret123'})
    client.get('/deconnexion')
    reponse = client.post('/connexion', data={'email': 'lina@isi.tn', 'mdp': 'faux'})
    assert 'incorrect' in reponse.get_data(as_text=True)
    assert client.get('/tableau-de-bord').status_code == 302


def test_commande_create_admin(ctx):
    """Exploitation : creation d'un administrateur en ligne de commande."""
    app, *_ = ctx
    r = app.test_cli_runner().invoke(args=['create-admin', '--email', 'Chef@isi.tn',
                                           '--password', 'motdepasse1'])
    assert r.exit_code == 0
    u = User.query.filter_by(email='chef@isi.tn').first()
    assert u.is_admin and u.check_password('motdepasse1')
    court = app.test_cli_runner().invoke(args=['create-admin', '--email', 'x@isi.tn', '--password', 'court'])
    assert court.exit_code != 0
