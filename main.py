import functions_framework
from app import app

@functions_framework.http
def handle_request(request):
    return app(request.environ, lambda x, y: []) 