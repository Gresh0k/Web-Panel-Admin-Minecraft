# create_owner.py
from app import app, db, AdminUser
from werkzeug.security import generate_password_hash

def create_first_owner():
    with app.app_context():
        # Проверяем, не создан ли уже владелец
        if AdminUser.query.filter_by(role='owner').first():
            print("❌ Владелец уже существует в базе данных!")
            return

        print("--- Создание Владельца сервера ---")
        username = input("Введите логин владельца: ")
        password = input("Введите пароль владельца: ")
        
        if not username or not password:
            print("❌ Логин и пароль не могут быть пустыми!")
            return

        hashed_pw = generate_password_hash(password)
        new_owner = AdminUser(username=username, password_hash=hashed_pw, role='owner')
        
        db.session.add(new_owner)
        db.session.commit()
        print(f"✅ Владелец '{username}' успешно создан!")

if __name__ == "__main__":
    create_first_owner()