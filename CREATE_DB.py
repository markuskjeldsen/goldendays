# Reset database

import app
import os
try:
    os.remove('database.db')
except:
    pass
app.init_db()
