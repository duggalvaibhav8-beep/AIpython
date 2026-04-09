# from pydantic import BaseModel, EmailStr
# from typing import Optional, TypeVar
# from datetime import datetime

# # T = TypeVar('T')

# # class BaseResponse(BaseModel):
# #     success: bool
# #     message: str
# #     data: Optional[T] = None

# class UserCreate(BaseModel):
#     username: str
#     email: EmailStr
#     password: str
#     first_name: Optional[str] = None
#     last_name: Optional[str] = None
#     phone: Optional[str] = None
#     address: Optional[str] = None
#     city: Optional[str] = None
#     country: Optional[str] = None
#     postal_code: Optional[str] = None

# class UserResponse(BaseModel):
#     id: int
#     username: str
#     email: str
#     first_name: Optional[str]
#     last_name: Optional[str]
#     phone: Optional[str]
#     address: Optional[str]
#     city: Optional[str]
#     country: Optional[str]
#     postal_code: Optional[str]
#     role: str
#     created_at: Optional[datetime] = None

# class UserUpdate(BaseModel):
#     username: Optional[str] = None
#     email: Optional[EmailStr] = None
#     password: Optional[str] = None
#     first_name: Optional[str] = None
#     last_name: Optional[str] = None
#     phone: Optional[str] = None
#     address: Optional[str] = None
#     city: Optional[str] = None
#     country: Optional[str] = None
#     postal_code: Optional[str] = None

# class LoginRequest(BaseModel):
#     username: str
#     password: str

# class Token(BaseModel):
#     access_token: str
#     token_type: str
#     user: UserResponse

# # UserBaseResponse = BaseResponse[UserResponse]
# # UsersListResponse = BaseResponse[list[UserResponse]]
# # TokenResponse = BaseResponse[Token]


from pydantic import BaseModel, EmailStr
from typing import Optional, TypeVar, Generic, Any
from datetime import datetime

T = TypeVar('T')

class BaseResponse(BaseModel, Generic[T]):
    success: bool
    message: str
    data: Optional[T] = None

class UserCreate(BaseModel):
    username: str
    email: EmailStr
    password: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    country: Optional[str] = None
    postal_code: Optional[str] = None

class UserResponse(BaseModel):
    id: int
    username: str
    email: str
    first_name: Optional[str]
    last_name: Optional[str]
    phone: Optional[str]
    address: Optional[str]
    city: Optional[str]
    country: Optional[str]
    postal_code: Optional[str]
    role: str
    created_at: Optional[datetime] = None

class UserUpdate(BaseModel):
    username: Optional[str] = None
    email: Optional[EmailStr] = None
    password: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    country: Optional[str] = None
    postal_code: Optional[str] = None

class LoginRequest(BaseModel):
    username: str
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str
    user: UserResponse

# Type aliases for common responses
UserBaseResponse = BaseResponse[UserResponse]
UsersListResponse = BaseResponse[list[UserResponse]]
TokenResponse = BaseResponse[Token]