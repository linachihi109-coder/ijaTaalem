"""ijaTaalem : plateforme d'entraide entre étudiants (Flask)."""
import os
import click
from datetime import date, time
from functools import wraps
from flask import (Flask, render_template, request, redirect, url_for,
                   session, flash, g, abort)
from models import (db, User, Matiere, Disponibilite, Seance, JOURS, STATUTS,
                    trouver_tuteurs, creer_demande, accepter, refuser, terminer,
                    annuler, noter)


def create_app(config=None):
    app = Flask(__name__)
    app.config.update(SECRET_KEY=os.environ.get('SECRET_KEY', 'dev-ijataalem-a-changer'),
                      SQLALCHEMY_DATABASE_URI=os.environ.get('DATABASE_URL', 'sqlite:///ijataalem.db'))
    if config:
        app.config.update(config)
    db.init_app(app)
    with app.app_context():
        db.create_all()

    @app.before_request
    def charger_utilisateur():
        g.user = db.session.get(User, session['uid']) if 'uid' in session else None

    @app.context_processor
    def globales():
        return dict(JOURS=JOURS, STATUTS=STATUTS)

    def login_required(f):
        @wraps(f)
        def w(*a, **k):
            if not g.user:
                flash("Veuillez vous connecter.", 'warning')
                return redirect(url_for('connexion'))
            return f(*a, **k)
        return w

    def admin_required(f):
        @wraps(f)
        @login_required
        def w(*a, **k):
            if not g.user.is_admin:
                abort(403)
            return f(*a, **k)
        return w

    # ----- Pages publiques -----
    @app.route('/')
    def index():
        top = sorted(User.query.filter_by(is_admin=False).all(), key=lambda u: -u.points)[:3]
        return render_template('index.html', matieres=Matiere.query.all(), top=top,
                               nb_tuteurs=sum(1 for u in User.query.all() if u.matieres),
                               nb_seances=Seance.query.filter_by(statut='terminee').count())

    @app.route('/inscription', methods=['GET', 'POST'])
    def inscription():
        if request.method == 'POST':
            nom = request.form['nom'].strip()
            email = request.form['email'].strip().lower()
            mdp = request.form['mdp']
            if not nom or '@' not in email or len(mdp) < 6:
                flash("Nom, e-mail valide et mot de passe (6 caractères min.) requis.", 'danger')
            elif User.query.filter_by(email=email).first():
                flash("Cet e-mail est déjà utilisé.", 'danger')
            else:
                u = User(nom=nom, email=email)
                u.set_password(mdp)
                db.session.add(u)
                db.session.commit()
                session['uid'] = u.id
                return redirect(url_for('tableau_de_bord'))
        return render_template('auth.html', mode='inscription')

    @app.route('/connexion', methods=['GET', 'POST'])
    def connexion():
        if request.method == 'POST':
            u = User.query.filter_by(email=request.form['email'].strip().lower()).first()
            if u and u.check_password(request.form['mdp']):
                session['uid'] = u.id
                return redirect(url_for('admin' if u.is_admin else 'tableau_de_bord'))
            flash("E-mail ou mot de passe incorrect.", 'danger')
        return render_template('auth.html', mode='connexion')

    @app.route('/deconnexion')
    def deconnexion():
        session.clear()
        return redirect(url_for('index'))

    # ----- Recherche et aide rapide -----
    @app.route('/tuteurs')
    def tuteurs():
        mid = request.args.get('matiere_id', type=int)
        matiere = db.session.get(Matiere, mid) if mid else None
        jour, debut, fin, rapide = None, None, None, False
        try:
            if request.args.get('jour') and request.args.get('debut') and request.args.get('fin'):
                jour = date.fromisoformat(request.args['jour'])
                debut = time.fromisoformat(request.args['debut'])
                fin = time.fromisoformat(request.args['fin'])
                rapide = True
        except ValueError:
            flash("Date ou heure invalide.", 'danger')
        if rapide and matiere:
            liste = trouver_tuteurs(matiere, jour, debut, fin, exclu=g.user)
        elif matiere:
            liste = sorted([t for t in matiere.tuteurs if not g.user or t.id != g.user.id],
                           key=lambda t: -t.points)
        else:
            liste = sorted([u for u in User.query.all() if u.matieres and not (g.user and u.id == g.user.id)],
                           key=lambda t: -t.points)
        return render_template('tuteurs.html', liste=liste, matieres=Matiere.query.all(),
                               matiere=matiere, rapide=rapide)

    @app.post('/demander')
    @login_required
    def demander():
        try:
            f = request.form
            creer_demande(g.user, db.get_or_404(User, int(f['tuteur_id'])),
                          db.get_or_404(Matiere, int(f['matiere_id'])),
                          date.fromisoformat(f['jour']), time.fromisoformat(f['debut']),
                          time.fromisoformat(f['fin']), f.get('message', ''))
            flash("Demande envoyée au tuteur !", 'success')
            return redirect(url_for('tableau_de_bord'))
        except (ValueError, KeyError) as e:
            flash(str(e) or "Formulaire invalide.", 'danger')
            return redirect(request.referrer or url_for('tuteurs'))

    # ----- Tableau de bord -----
    @app.route('/tableau-de-bord')
    @login_required
    def tableau_de_bord():
        return render_template('dashboard.html', matieres=Matiere.query.all())

    @app.post('/seance/<int:sid>/<action>')
    @login_required
    def action_seance(sid, action):
        actions = {'accepter': accepter, 'refuser': refuser, 'terminer': terminer, 'annuler': annuler}
        if action not in actions:
            abort(404)
        try:
            actions[action](db.get_or_404(Seance, sid), g.user)
        except ValueError as e:
            flash(str(e), 'danger')
        return redirect(url_for('tableau_de_bord'))

    @app.post('/seance/<int:sid>/avis')
    @login_required
    def avis(sid):
        try:
            noter(db.get_or_404(Seance, sid), g.user, int(request.form['note']),
                  request.form.get('commentaire', ''))
            flash("Merci pour votre avis !", 'success')
        except (ValueError, KeyError) as e:
            flash(str(e), 'danger')
        return redirect(url_for('tableau_de_bord'))

    @app.post('/profil/matieres')
    @login_required
    def profil_matieres():
        ids = request.form.getlist('matieres', type=int)
        g.user.matieres = Matiere.query.filter(Matiere.id.in_(ids)).all() if ids else []
        g.user.bio = request.form.get('bio', '')[:200]
        db.session.commit()
        flash("Profil de tuteur mis à jour.", 'success')
        return redirect(url_for('tableau_de_bord'))

    @app.post('/disponibilite')
    @login_required
    def ajouter_dispo():
        try:
            d, f = time.fromisoformat(request.form['debut']), time.fromisoformat(request.form['fin'])
            if f <= d:
                raise ValueError("L'heure de fin doit être après l'heure de début.")
            db.session.add(Disponibilite(tuteur=g.user, jour_semaine=int(request.form['jour_semaine']),
                                         debut=d, fin=f))
            db.session.commit()
        except (ValueError, KeyError) as e:
            flash(str(e) or "Créneau invalide.", 'danger')
        return redirect(url_for('tableau_de_bord'))

    @app.post('/disponibilite/<int:did>/supprimer')
    @login_required
    def supprimer_dispo(did):
        d = db.get_or_404(Disponibilite, did)
        if d.tuteur_id == g.user.id:
            db.session.delete(d)
            db.session.commit()
        return redirect(url_for('tableau_de_bord'))

    # ----- Administration -----
    @app.route('/admin')
    @admin_required
    def admin():
        return render_template('admin.html', matieres=Matiere.query.all(),
                               users=User.query.filter_by(is_admin=False).all())

    @app.post('/admin/matiere')
    @admin_required
    def admin_matiere():
        nom = request.form['nom'].strip()
        if nom and not Matiere.query.filter_by(nom=nom).first():
            db.session.add(Matiere(nom=nom, icone=request.form.get('icone') or '📘'))
            db.session.commit()
        return redirect(url_for('admin'))

    @app.post('/admin/matiere/<int:mid>/supprimer')
    @admin_required
    def admin_suppr_matiere(mid):
        m = db.get_or_404(Matiere, mid)
        if Seance.query.filter_by(matiere_id=mid).count():
            flash("Matière utilisée par des séances : suppression impossible.", 'danger')
        else:
            db.session.delete(m)
            db.session.commit()
        return redirect(url_for('admin'))

    @app.post('/admin/user/<int:uid>/supprimer')
    @admin_required
    def admin_suppr_user(uid):
        u = db.get_or_404(User, uid)
        for s in Seance.query.filter((Seance.apprenant_id == uid) | (Seance.tuteur_id == uid)).all():
            db.session.delete(s)
        db.session.delete(u)
        db.session.commit()
        return redirect(url_for('admin'))

    @app.cli.command('create-admin')
    @click.option('--nom', default='Administrateur', show_default=True)
    @click.option('--email', prompt=True)
    @click.password_option()
    def create_admin(nom, email, password):
        """Cree un compte administrateur (utilisable en production, sans donnees de demonstration)."""
        email = email.strip().lower()
        if len(password) < 8:
            raise click.ClickException('Le mot de passe doit contenir au moins 8 caracteres.')
        if User.query.filter_by(email=email).first():
            raise click.ClickException('Cet e-mail est deja utilise.')
        u = User(nom=nom, email=email, is_admin=True)
        u.set_password(password)
        db.session.add(u)
        db.session.commit()
        click.echo(f'Administrateur cree : {email}')

    @app.cli.command('seed')
    def seed():
        """Données de démonstration."""
        if User.query.count():
            return
        ms = [Matiere(nom=n, icone=i) for n, i in [('Algorithmique', '🧠'), ('Bases de données', '🗄️'),
              ('Java', '☕'), ('Mathématiques', '📐'), ('Réseaux', '🌐'), ('Génie logiciel', '🛠️')]]
        db.session.add_all(ms)
        admin_u = User(nom='Admin ISI', email='admin@isi.tn', is_admin=True)
        admin_u.set_password('admin123')
        db.session.add(admin_u)
        for i, (nom, subs) in enumerate([('Sarra Ben Ali', [0, 1]), ('Mehdi Trabelsi', [2, 5]),
                                         ('Yasmine Gharbi', [3, 4])]):
            u = User(nom=nom, email=f'tuteur{i + 1}@isi.tn', bio="Étudiant(e) L2-CS, ravi(e) d'aider !")
            u.set_password('motdepasse')
            u.matieres = [ms[j] for j in subs]
            u.disponibilites = [Disponibilite(jour_semaine=d, debut=time(14), fin=time(18)) for d in (0, 2, 4)]
            db.session.add(u)
        db.session.commit()
        print('Base initialisée : admin@isi.tn / admin123, tuteur1@isi.tn / motdepasse')

    return app


if __name__ == '__main__':
    create_app().run(debug=True)
