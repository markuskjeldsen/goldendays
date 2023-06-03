# Flask-Assets (minifies and packs JS & LESS/CSS files)
from flask_assets import Environment, Bundle

assets = Environment()

js = Bundle(
    'js/scripts.js',
    filters='jsmin',
    output='gen/packed.js'
)
assets.register('js_all', js)

css = Bundle(
    'css/style.less',
    filters='less',
    output='gen/packed.css'
)
assets.register('css', css)

bootstrapcss = Bundle(
    '../bootstrap/less/bootstrap.less',
    filters='less',
    output='gen/bootstrap.css'
)
assets.register('bootstrapcss', bootstrapcss)
