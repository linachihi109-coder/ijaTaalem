"""Tests unitaires des regles de gestion R1 a R6 et R9 (module models.py)."""
from datetime import date, time, timedelta

import pytest

from conftest import DEMAIN
from models import (badge_pour, creer_demande, accepter, refuser, terminer, annuler,
                    noter, trouver_tuteurs)


@pytest.mark.parametrize('points,badge', [(0, 'Bronze'), (9, 'Bronze'), (10, 'Argent'),
                                           (29, 'Argent'), (30, 'Or')])
def test_badge_valeurs_limites(points, badge):
    """R4 : seuils des badges, testes de part et d'autre de chaque limite."""
    assert badge_pour(points) == badge


def test_pas_de_demande_a_soi_meme(ctx):
    """R2."""
    _, m, a, _, _ = ctx
    a.matieres = [m]
    with pytest.raises(ValueError):
        creer_demande(a, a, m, DEMAIN, time(14), time(15))


def test_demande_invalide(ctx):
    """R5 : fin avant debut, date passee, matiere non enseignee."""
    _, m, a, _, t = ctx
    with pytest.raises(ValueError):
        creer_demande(a, t, m, DEMAIN, time(15), time(14))
    with pytest.raises(ValueError):
        creer_demande(a, t, m, date.today() - timedelta(days=1), time(14), time(15))
    from models import Matiere, db
    autre = Matiere(nom='Java')
    db.session.add(autre)
    db.session.commit()
    with pytest.raises(ValueError):
        creer_demande(a, t, autre, DEMAIN, time(14), time(15))


def test_chevauchement_refuse(ctx):
    """R1 : 14h-16h acceptee, donc 15h-17h refusee."""
    _, m, a, b, t = ctx
    s1 = creer_demande(a, t, m, DEMAIN, time(14), time(16))
    s2 = creer_demande(b, t, m, DEMAIN, time(15), time(17))
    accepter(s1, t)
    with pytest.raises(ValueError):
        accepter(s2, t)


def test_creneaux_adjacents_acceptes(ctx):
    """R1, valeur limite : 14h-16h puis 16h-17h ne se chevauchent pas."""
    _, m, a, b, t = ctx
    s1 = creer_demande(a, t, m, DEMAIN, time(14), time(16))
    s2 = creer_demande(b, t, m, DEMAIN, time(16), time(17))
    accepter(s1, t)
    accepter(s2, t)
    assert s2.statut == 'acceptee'


def test_un_seul_avis_apres_terminee(ctx):
    """R3 et R4 : pas de note avant la fin, un seul avis, 10 points apres un 5."""
    _, m, a, _, t = ctx
    s = creer_demande(a, t, m, DEMAIN, time(14), time(15))
    with pytest.raises(ValueError):
        noter(s, a, 5)
    accepter(s, t)
    terminer(s, t)
    noter(s, a, 5)
    with pytest.raises(ValueError):
        noter(s, a, 4)
    assert t.points == 10 and t.badge == 'Argent'


@pytest.mark.parametrize('note', [0, 6])
def test_note_hors_bornes(ctx, note):
    """R3 : la note doit etre comprise entre 1 et 5."""
    _, m, a, _, t = ctx
    s = creer_demande(a, t, m, DEMAIN, time(14), time(15))
    accepter(s, t)
    terminer(s, t)
    with pytest.raises(ValueError):
        noter(s, a, note)


def test_points_sans_avis(ctx):
    """R4 : une seance terminee et non notee rapporte 5 points."""
    _, m, a, _, t = ctx
    s = creer_demande(a, t, m, DEMAIN, time(14), time(15))
    accepter(s, t)
    terminer(s, t)
    assert t.points == 5 and t.badge == 'Bronze'


def test_seul_le_bon_acteur(ctx):
    """R6 : l'apprenant ne peut pas accepter, le tuteur ne peut pas annuler."""
    _, m, a, _, t = ctx
    s = creer_demande(a, t, m, DEMAIN, time(14), time(15))
    with pytest.raises(ValueError):
        accepter(s, a)
    with pytest.raises(ValueError):
        refuser(s, a)
    with pytest.raises(ValueError):
        annuler(s, t)
    annuler(s, a)
    assert s.statut == 'annulee'


def test_aide_rapide(ctx):
    """R9 : tuteur propose si disponible et libre, sinon exclu."""
    _, m, a, _, t = ctx
    assert trouver_tuteurs(m, DEMAIN, time(14), time(15), exclu=a) == [t]
    assert trouver_tuteurs(m, DEMAIN, time(19), time(20)) == []
    assert trouver_tuteurs(m, DEMAIN, time(14), time(15), exclu=t) == []
    accepter(creer_demande(a, t, m, DEMAIN, time(14), time(16)), t)
    assert trouver_tuteurs(m, DEMAIN, time(15), time(16)) == []


def test_transition_invalide(ctx):
    """RG-10 : une transition n'est possible que depuis les statuts prevus."""
    _, m, a, _, t = ctx
    s = creer_demande(a, t, m, DEMAIN, time(14), time(15))
    with pytest.raises(ValueError):
        terminer(s, t)            # impossible depuis « en attente »
    accepter(s, t)
    with pytest.raises(ValueError):
        accepter(s, t)            # deja acceptee
    terminer(s, t)
    with pytest.raises(ValueError):
        annuler(s, a)             # impossible apres la fin
