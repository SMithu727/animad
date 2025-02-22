# run.py
from app_factory import create_app

app = create_app()

if __name__ == '__main__':
    # Listen on all interfaces; change port if needed.
    app.run(host='0.0.0.0', port=5000, debug=True)
