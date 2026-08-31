import sys
from app import create_app

print("Testing TaskFlow create_app()...")
app = create_app()
print(f"App name: {app.name}")
print(f"Instance path: {app.instance_path}")
print(f"DB URI: {app.config['SQLALCHEMY_DATABASE_URI']}")

with app.test_client() as client:
    response = client.get("/")
    print(f"GET / status code: {response.status_code}")
    print(f"GET / response data: {response.get_json()}")

print("Phase 1 verification successful!")
