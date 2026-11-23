"""Modèles et règles métier de ijaTaalem."""
from datetime import date, time
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

JOURS = ['Lundi', 'Mardi', 'Mercredi', 'Jeudi', 'Vendredi', 'Samedi', 'Dimanche']
STATUTS = {'en_attente': 'En attente', 'acceptee': 'Acceptée', 'refusee': 'Refusée',
           'terminee': 'Terminée', 'annulee': 'Annulée'}

tuteur_matiere = db.Table(
    'tuteur_matiere',
    db.Column('user_id', db.ForeignKey('user.id'), primary_key=True),
    db.Column('matiere_id', db.ForeignKey('matiere.id'), primary_key=True))


def badge_pour(points):
    """Bronze 0-9, Argent 10-29, Or 30+."""
    if points >= 30:
        return 'Or'
    if points >= 10:
        return 'Argent'
    return 'Bronze'


def chevauche(d1, f1, d2, f2):
    return d1 < f2 and d2 < f1


class Matiere(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nom = db.Column(db.String(80), unique=True, nullable=False)
    icone = db.Column(db.String(8), default='📘')


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nom = db.Column(db.String(80), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    bio = db.Column(db.String(200), default='')
    matieres = db.relationship('Matiere', secondary=tuteur_matiere, backref='tuteurs')
    disponibilites = db.relationship('Disponibilite', backref='tuteur', cascade='all, delete-orphan')

    def set_password(self, mdp):
        self.password_hash = generate_password_hash(mdp)

    def check_password(self, mdp):
        return check_password_hash(self.password_hash, mdp)

    @property
    def points(self):
        return sum(5 + (s.avis.note if s.avis else 0)
                   for s in self.seances_donnees if s.statut == 'terminee')

    @property
    def badge(self):
        return badge_pour(self.points)

    @property
    def note_moyenne(self):
        notes = [s.avis.note for s in self.seances_donnees if s.avis]
        return round(sum(notes) / len(notes), 1) if notes else None


class Disponibilite(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    tuteur_id = db.Column(db.ForeignKey('user.id'), nullable=False)
    jour_semaine = db.Column(db.Integer, nullable=False)  # 0 = lundi
    debut = db.Column(db.Time, nullable=False)
    fin = db.Column(db.Time, nullable=False)


class Seance(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    apprenant_id = db.Column(db.ForeignKey('user.id'), nullable=False)
    tuteur_id = db.Column(db.ForeignKey('user.id'), nullable=False)
    matiere_id = db.Column(db.ForeignKey('matiere.id'), nullable=False)
    jour = db.Column(db.Date, nullable=False)
    debut = db.Column(db.Time, nullable=False)
    fin = db.Column(db.Time, nullable=False)
    message = db.Column(db.String(300), default='')
    statut = db.Column(db.String(20), default='en_attente')
    apprenant = db.relationship('User', foreign_keys=[apprenant_id], backref='seances_demandees')
    tuteur = db.relationship('User', foreign_keys=[tuteur_id], backref='seances_donnees')
    matiere = db.relationship('Matiere')
    avis = db.relationship('Avis', uselist=False, backref='seance', cascade='all, delete-orphan')


class Avis(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    seance_id = db.Column(db.ForeignKey('seance.id'), unique=True, nullable=False)
    note = db.Column(db.Integer, nullable=False)
    commentaire = db.Column(db.String(300), default='')


# ---------- Règles métier ----------
def tuteur_libre(tuteur, jour, debut, fin, exclure_id=None):
    """Aucune séance acceptée ne chevauche le créneau."""
    return not any(s.statut == 'acceptee' and s.jour == jour and s.id != exclure_id
                   and chevauche(debut, fin, s.debut, s.fin) for s in tuteur.seances_donnees)


def tuteur_disponible(tuteur, jour, debut, fin):
    return any(d.jour_semaine == jour.weekday() and d.debut <= debut and fin <= d.fin
               for d in tuteur.disponibilites)


def trouver_tuteurs(matiere, jour, debut, fin, exclu=None):
    """Aide rapide : tuteurs de la matière disponibles et libres, triés par points."""
    res = [t for t in matiere.tuteurs
           if (exclu is None or t.id != exclu.id)
           and tuteur_disponible(t, jour, debut, fin) and tuteur_libre(t, jour, debut, fin)]
    return sorted(res, key=lambda t: -t.points)


def creer_demande(apprenant, tuteur, matiere, jour, debut, fin, message=''):
    if apprenant.id == tuteur.id:
        raise ValueError("Vous ne pouvez pas demander une séance à vous-même.")
    if matiere not in tuteur.matieres:
        raise ValueError("Ce tuteur n'enseigne pas cette matière.")
    if fin <= debut:
        raise ValueError("L'heure de fin doit être après l'heure de début.")
    if jour < date.today():
        raise ValueError("La date ne peut pas être dans le passé.")
    s = Seance(apprenant=apprenant, tuteur=tuteur, matiere=matiere, jour=jour,
               debut=debut, fin=fin, message=message[:300])
    db.session.add(s)
    db.session.commit()
    return s


def _verifier(s, user_id, attendu, statuts):
    if user_id != attendu:
        raise ValueError("Action non autorisée.")
    if s.statut not in statuts:
        raise ValueError("Action impossible pour l'état actuel de la séance.")


def accepter(s, u):
    _verifier(s, u.id, s.tuteur_id, ('en_attente',))
    if not tuteur_libre(s.tuteur, s.jour, s.debut, s.fin, exclure_id=s.id):
        raise ValueError("Vous avez déjà une séance acceptée sur ce créneau.")
    s.statut = 'acceptee'
    db.session.commit()


def refuser(s, u):
    _verifier(s, u.id, s.tuteur_id, ('en_attente',))
    s.statut = 'refusee'
    db.session.commit()


def terminer(s, u):
    _verifier(s, u.id, s.tuteur_id, ('acceptee',))
    s.statut = 'terminee'
    db.session.commit()


def annuler(s, u):
    _verifier(s, u.id, s.apprenant_id, ('en_attente', 'acceptee'))
    s.statut = 'annulee'
    db.session.commit()


def noter(s, u, note, commentaire=''):
    _verifier(s, u.id, s.apprenant_id, ('terminee',))
    if s.avis:
        raise ValueError("Cette séance a déjà été notée.")
    if not 1 <= note <= 5:
        raise ValueError("La note doit être comprise entre 1 et 5.")
    db.session.add(Avis(seance=s, note=note, commentaire=commentaire[:300]))
    db.session.commit()
