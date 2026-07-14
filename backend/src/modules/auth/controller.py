from src.modules.auth.service import AuthService

class AuthController:
    @staticmethod
    async def register(payload, db, request=None):
        return AuthService.register(payload, db, request)

    @staticmethod
    async def verify_otp(payload, db):
        return AuthService.verify_otp(payload, db)

    @staticmethod
    async def login(payload, db, request=None):
        return AuthService.login(payload, db, request)

    @staticmethod
    async def forgot_password(username, db):
        return AuthService.forgot_password(username, db)

    @staticmethod
    async def reset_password(payload, db):
        return AuthService.reset_password(payload, db)

    @staticmethod
    async def logout(user_id, db):
        return AuthService.logout(user_id, db)
