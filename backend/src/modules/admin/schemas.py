from pydantic import BaseModel

class AdminCreateUser(BaseModel):
    username: str
    email: str
    password: str
    role: str = "user"

class AdminUpdateRole(BaseModel):
    role: str
