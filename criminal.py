from flask import (
    Blueprint, flash, g, redirect, render_template, request, session, url_for
)

import face_recognition,pickle,os

from .db import get_db
from .auth import manager_required

bp = Blueprint('criminal', __name__, url_prefix='/criminal')

@bp.route('/register', methods=('GET', 'POST'))
@manager_required
def register():
    '''逃犯信息录入界面'''
    if request.method == 'POST':
        name = request.form['criminal_name']
        id = request.form['criminal_id']
        photo= request.files['criminal_photo']
        photo.save(photo.filename)
        image = face_recognition.load_image_file(photo.filename)
        encoding = face_recognition.face_encodings(image)
        encoding = pickle.dumps(encoding)
        print(encoding)
        os.remove(photo.filename)
        important = True if request.form['criminal_importance'] == "True" else False

        db = get_db()
        error = None

        if not name:
            error = 'Criminal name is required.'
        elif not encoding:
            error = 'Encoding is required.'
        elif db.execute(
                'SELECT rank FROM criminal WHERE id = ?', (id,)
        ).fetchone() is not None:
            error = 'Criminal {} whose id is {} is already registered.'.format(name, id)

        if error is None:
            db.execute(
                'INSERT INTO criminal (name, id, encoding, important) VALUES (?,?,?,?)',
                (name, id, encoding, important)
            )
            db.commit()
            return redirect(url_for('auth.manage'))

        flash(error)
    return render_template('criminal/register.html')