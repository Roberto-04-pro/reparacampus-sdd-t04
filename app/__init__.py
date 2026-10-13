import os
from flask import Flask, render_template
from app.db import close_db, init_db
from app.routes import bp

def create_app(test_config=None) -> Flask:
    app = Flask(__name__, template_folder="templates", static_folder="static")
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "reparacampus-usb-t04-infracore-2026")
    app.config["DATABASE"] = os.path.join(os.getcwd(), "reparacampus.db")

    if test_config:
        app.config.update(test_config)

    app.teardown_appcontext(close_db)
    app.register_blueprint(bp)

    @app.errorhandler(403)
    def error_403(e):
        return render_template("error.html", codigo=403, titulo="Acceso Denegado (403)", mensaje=getattr(e, "description", str(e))), 403

    @app.errorhandler(404)
    def error_404(e):
        return render_template("error.html", codigo=404, titulo="No Encontrado (404)", mensaje=getattr(e, "description", str(e))), 404

    with app.app_context():
        init_db(seed_users=True)

    return app
