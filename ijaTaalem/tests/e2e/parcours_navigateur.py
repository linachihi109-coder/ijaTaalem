"""Scenarios fonctionnels dans un navigateur (Chromium, Playwright).

Prerequis : pip install playwright && playwright install chromium
Lancer d'abord l'application sur une base neuve :
    DATABASE_URL=sqlite:////tmp/e2e.db flask --app app seed
    DATABASE_URL=sqlite:////tmp/e2e.db flask --app app run --port 5056
Puis : python tests/e2e/parcours_navigateur.py http://127.0.0.1:5056
Ce fichier n'est pas collecte par pytest (nom sans prefixe test_).
"""
import sys
from datetime import date, timedelta

from playwright.sync_api import sync_playwright

B = sys.argv[1] if len(sys.argv) > 1 else 'http://127.0.0.1:5056'
resultats = {}


def jour(wd):
    d = date.today() + timedelta(days=1)
    while d.weekday() != wd:
        d += timedelta(days=1)
    return d.isoformat()


LUN, MER = jour(0), jour(2)


def check(nom, condition):
    resultats[nom] = bool(condition)
    print(f"{nom}: {'REUSSI' if condition else 'ECHEC'}")


with sync_playwright() as p:
    nav = p.chromium.launch()
    ctx = nav.new_context(viewport={'width': 1280, 'height': 800})
    pg = ctx.new_page()
    pg.on('dialog', lambda d: d.accept())
    html = lambda: pg.content()

    def login(email, mdp):
        pg.goto(B + '/deconnexion'); pg.goto(B + '/connexion')
        pg.fill('input[name=email]', email); pg.fill('input[name=mdp]', mdp)
        pg.click('form button.btn-p')

    def inscrire(nom, email):
        pg.goto(B + '/deconnexion'); pg.goto(B + '/inscription')
        pg.fill('input[name=nom]', nom); pg.fill('input[name=email]', email)
        pg.fill('input[name=mdp]', 'secret123'); pg.click('form button.btn-p')

    def demander(tuteur, matiere, j, d, f):
        pg.request.post(B + '/demander', form={'tuteur_id': str(tuteur), 'matiere_id': str(matiere),
                                               'jour': j, 'debut': d, 'fin': f, 'message': 'test'})

    pg.goto(B + '/')
    check('TF-01 accueil', 'Aide rapide' in html() and 'Meilleurs tuteurs' in html())
    inscrire('Lina Chihi', 'lina@isi.tn')
    check('TF-02 inscription valide', 'Bonjour Lina Chihi' in html())
    login('lina@isi.tn', 'secret123')
    check('TF-03 connexion', 'Bonjour Lina Chihi' in html())
    pg.goto(B + '/tuteurs')
    check('TF-04 recherche sans filtre', all(n in html() for n in ('Sarra', 'Mehdi', 'Yasmine')))
    pg.goto(B + f'/tuteurs?matiere_id=2&jour={LUN}&debut=14:00&fin=15:00')
    check('TF-05 aide rapide', 'Sarra' in html() and 'Mehdi' not in html())
    f = pg.locator('form[action="/demander"]').first
    f.locator('input[name=message]').fill('Je ne comprends pas les jointures SQL'); f.locator('button').click()
    check('TF-06 demande de seance', 'Demande envoyée' in html() and 'En attente' in html())
    login('tuteur1@isi.tn', 'motdepasse'); pg.goto(B + '/tableau-de-bord'); pg.click('text=Accepter')
    check('TF-07 acceptation', 'Acceptée' in html())
    pg.click('text=Marquer terminée')
    check('TF-08 fin de seance', 'Terminée' in html())
    login('lina@isi.tn', 'secret123'); pg.goto(B + '/tableau-de-bord'); pg.click('text=Noter')
    check('TF-09 avis', '⭐ 5' in html())
    login('tuteur1@isi.tn', 'motdepasse'); pg.goto(B + '/tableau-de-bord')
    check('TF-10 progression', 'Argent' in html() and '5.0' in html())
    login('admin@isi.tn', 'admin123'); pg.goto(B + '/admin')
    check('TF-11 administration', 'Comptes étudiants' in html() and 'Lina Chihi' in html())
    # refus et annulation
    login('lina@isi.tn', 'secret123'); demander(2, 1, MER, '15:00', '16:00')
    login('tuteur1@isi.tn', 'motdepasse'); pg.goto(B + '/tableau-de-bord'); pg.click('text=Refuser')
    login('lina@isi.tn', 'secret123'); pg.goto(B + '/tableau-de-bord')
    check('TF-12 refus', 'Refusée' in html())
    demander(2, 1, MER, '15:00', '16:00'); pg.goto(B + '/tableau-de-bord'); pg.click('text=Annuler'); pg.goto(B + '/tableau-de-bord')
    check('TF-13 annulation', 'Annulée' in html())
    # disponibilites et matieres du tuteur
    login('tuteur1@isi.tn', 'motdepasse'); pg.goto(B + '/tableau-de-bord')
    pg.select_option('select[name=jour_semaine]', '1')
    pg.fill('form[action="/disponibilite"] input[name=debut]', '10:00'); pg.fill('form[action="/disponibilite"] input[name=fin]', '12:00')
    pg.click('form[action="/disponibilite"] button'); ajout = 'Mardi 10:00-12:00' in html()
    pg.locator('form[action^="/disponibilite/"][action$="/supprimer"]').last.locator('button').click()
    check('TF-14 disponibilites', ajout and 'Mardi 10:00-12:00' not in html())
    pg.goto(B + '/tableau-de-bord'); pg.uncheck('#m1'); pg.check('#m5'); pg.click('form[action="/profil/matieres"] button')
    pg.goto(B + '/deconnexion')  # en visiteur : l'utilisateur connecte est exclu des listes (RG-09)
    pg.goto(B + '/tuteurs?matiere_id=5'); a = 'Sarra' in html()
    pg.goto(B + '/tuteurs?matiere_id=1')
    check('TF-15 matieres du tuteur', a and 'Sarra' not in html())
    # conflit d'horaires par l'interface
    inscrire('Etudiant Deux', 'deux@isi.tn')
    login('lina@isi.tn', 'secret123'); demander(3, 3, LUN, '14:00', '16:00')
    login('deux@isi.tn', 'secret123'); demander(3, 3, LUN, '15:00', '17:00')
    login('tuteur2@isi.tn', 'motdepasse'); pg.goto(B + '/tableau-de-bord')
    pg.locator('button:has-text("Accepter")').first.click(); pg.goto(B + '/tableau-de-bord')
    pg.locator('button:has-text("Accepter")').first.click()
    check('TF-19 conflit d\'horaires', 'déjà une séance acceptée' in html())
    # administration : matiere et compte
    login('admin@isi.tn', 'admin123'); pg.goto(B + '/admin')
    pg.fill('input[name=nom]', 'Python'); pg.click('form[action="/admin/matiere"] button'); ajout = pg.locator('text=Python').count() > 0
    pg.locator('form:has-text("Python") button').first.click()
    check('TF-16 matieres (admin)', ajout and pg.locator('text=Python').count() == 0)
    pg.goto(B + '/admin'); pg.locator('form:has-text("deux@isi.tn") button').click(); pg.goto(B + '/admin')
    check('TF-17 suppression de compte', 'deux@isi.tn' not in html())
    pg.goto(B + '/'); pg.click('text=Déconnexion')
    check('TF-18 deconnexion', 'Déconnexion' not in html() and 'Connexion' in html())
    # affichage mobile (emulation 375 px)
    mob = nav.new_context(viewport={'width': 375, 'height': 812}).new_page(); ok = True
    for u in ('/', '/tuteurs', '/connexion', '/inscription'):
        mob.goto(B + u); sw, iw = mob.evaluate('[document.documentElement.scrollWidth, window.innerWidth]'); ok &= sw <= iw + 1
    mob.goto(B + '/connexion'); mob.fill('input[name=email]', 'tuteur2@isi.tn'); mob.fill('input[name=mdp]', 'motdepasse'); mob.click('form button.btn-p')
    mob.goto(B + '/tableau-de-bord'); sw, iw = mob.evaluate('[document.documentElement.scrollWidth, window.innerWidth]'); ok &= sw <= iw + 1
    check('TC-02 affichage 375 px sans defilement horizontal', ok)
    nav.close()

echec = [k for k, v in resultats.items() if not v]
print(f"\n{len(resultats) - len(echec)}/{len(resultats)} scenarios reussis")
sys.exit(1 if echec else 0)
