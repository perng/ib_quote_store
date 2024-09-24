from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text

# Create a Flask app
app = Flask(__name__)

# Configure the SQLite database
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///options.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize SQLAlchemy
db = SQLAlchemy(app)

# List all tables in the database
with app.app_context():
    try:
        # Connect to the database
        connection = db.engine.connect()
        print("Connection to the database was successful!")

        # Query to list all tables
        result = connection.execute(text("SELECT name FROM sqlite_master WHERE type='table';"))
        tables = result.fetchall()

        # Print the table names
        print("Tables in the database:")
        for table in tables:
            print(table[0])

        # Close the connection
        connection.close()
    except Exception as e:
        print(f"Error: {e}")
