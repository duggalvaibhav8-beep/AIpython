# from fastapi import FastAPI, HTTPException, Depends
# from datetime import timedelta
# from models import UserCreate, UserResponse, UserUpdate, LoginRequest, Token
# from auth import (
#     authenticate_user, create_access_token, get_current_active_user, 
#     require_admin, ACCESS_TOKEN_EXPIRE_MINUTES
# )
# import database
# from fastapi.middleware.cors import CORSMiddleware

# app = FastAPI(
#     title="User Management Service",
#     description="Microservice for user authentication and management with JWT",
#     version="1.0.0"
# )

# # Add CORS middleware
# app.add_middleware(
#     CORSMiddleware,
#     # allow_origins=["http://localhost:3000", "http://127.0.0.1:3000", "http://localhost:8000", "http://localhost:8001", "http://localhost:8002", "http://localhost:8003"],  # Frontend URLs
#     allow_credentials=True,
#     allow_methods=["*"],  # Allow all methods
#     allow_headers=["*"],  # Allow all headers
#     allow_origins=["*"],
#     expose_headers=["*"]
# )

# # Public routes
# @app.post("/register", response_model=UserResponse)
# async def register(user: UserCreate):
#     """
#     Register a new user (default role: user)
#     """
#     try:
#         data = (
#             user.username, 
#             user.email, 
#             user.password, 
#             user.first_name, 
#             user.last_name,
#             user.phone, 
#             user.address, 
#             user.city, 
#             user.country, 
#             user.postal_code
#         )
#         success = database.reg(data)
        
#         if success:
#             # Get the newly created user
#             new_user = database.get_user_by_username(user.username)
            
#             if new_user:
#                 return UserResponse(
#                     id=new_user["id"],
#                     username=new_user["username"],
#                     email=new_user["email"],
#                     first_name=new_user["first_name"],
#                     last_name=new_user["last_name"],
#                     phone=new_user["phone"],
#                     address=new_user["address"],
#                     city=new_user["city"],
#                     country=new_user["country"],
#                     postal_code=new_user["postal_code"],
#                     role=new_user["role"],
#                     created_at=new_user.get("created_at")
#                 )
#             else:
#                 raise HTTPException(status_code=500, detail="User created but cannot retrieve details")
#         else:
#             raise HTTPException(status_code=400, detail="Username or email already exists")
            
#     except HTTPException:
#         raise
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=f"Registration failed: {str(e)}")

# @app.post("/login", response_model=Token)
# async def login(credentials: LoginRequest):
#     """
#     User login - returns JWT token
#     """
#     user = authenticate_user(credentials.username, credentials.password)
#     if not user:
#         raise HTTPException(
#             status_code=401,
#             detail="Incorrect username or password",
#             headers={"WWW-Authenticate": "Bearer"},
#         )
    
#     access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
#     access_token = create_access_token(
#         data={"sub": user["username"], "role": user["role"]},
#         expires_delta=access_token_expires
#     )
    
#     return Token(
#         access_token=access_token,
#         token_type="bearer",
#         user=UserResponse(
#             id=user["id"],
#             username=user["username"],
#             email=user["email"],
#             first_name=user["first_name"],
#             last_name=user["last_name"],
#             phone=user["phone"],
#             address=user["address"],
#             city=user["city"],
#             country=user["country"],
#             postal_code=user["postal_code"],
#             role=user["role"],
#             created_at=user.get("created_at")
#         )
#     )

# # Protected routes - require authentication
# @app.post("/users/me", response_model=UserResponse)
# async def get_current_user_info(current_user: dict = Depends(get_current_active_user)):
#     """
#     Get current user information
#     """
#     user = database.get_user_by_username(current_user["username"])
#     if user:
#         return UserResponse(
#             id=user["id"],
#             username=user["username"],
#             email=user["email"],
#             first_name=user["first_name"],
#             last_name=user["last_name"],
#             phone=user["phone"],
#             address=user["address"],
#             city=user["city"],
#             country=user["country"],
#             postal_code=user["postal_code"],
#             role=user["role"],
#             created_at=user.get("created_at")
#         )
#     raise HTTPException(status_code=404, detail="User not found")

# @app.put("/users/me", response_model=UserResponse)
# async def update_current_user(
#     user_update: UserUpdate,
#     current_user: dict = Depends(get_current_active_user)
# ):
#     """
#     Update current user information
#     """
#     try:
#         user = database.get_user_by_username(current_user["username"])
#         if not user:
#             raise HTTPException(status_code=404, detail="User not found")
        
#         # Use provided values or keep existing ones
#         username = user_update.username or user["username"]
#         email = user_update.email or user["email"]
#         password = user_update.password or ""
#         first_name = user_update.first_name or user["first_name"]
#         last_name = user_update.last_name or user["last_name"]
#         phone = user_update.phone or user["phone"]
#         address = user_update.address or user["address"]
#         city = user_update.city or user["city"]
#         country = user_update.country or user["country"]
#         postal_code = user_update.postal_code or user["postal_code"]
        
#         data = (
#             username, email, password, first_name, last_name,
#             phone, address, city, country, postal_code, user["id"]
#         )
#         success = database.update(data)
        
#         if success:
#             updated_user = database.single_user(user["id"])
#             if updated_user:
#                 return UserResponse(
#                     id=updated_user["id"],
#                     username=updated_user["username"],
#                     email=updated_user["email"],
#                     first_name=updated_user["first_name"],
#                     last_name=updated_user["last_name"],
#                     phone=updated_user["phone"],
#                     address=updated_user["address"],
#                     city=updated_user["city"],
#                     country=updated_user["country"],
#                     postal_code=updated_user["postal_code"],
#                     role=updated_user["role"],
#                     created_at=updated_user.get("created_at")
#                 )
#             else:
#                 raise HTTPException(status_code=500, detail="Failed to retrieve updated user")
#         else:
#             raise HTTPException(status_code=400, detail="Failed to update user - username or email may already exist")
            
#     except HTTPException:
#         raise
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=f"Update failed: {str(e)}")

# # Admin only routes
# @app.post("/users", response_model=list[UserResponse])
# async def get_all_users(current_user: dict = Depends(require_admin)):
#     """
#     Get all users (Admin only)
#     """
#     try:
#         users = database.show_all()
#         return [
#             UserResponse(
#                 id=user["id"],
#                 username=user["username"],
#                 email=user["email"],
#                 first_name=user["first_name"],
#                 last_name=user["last_name"],
#                 phone=user["phone"],
#                 address=user["address"],
#                 city=user["city"],
#                 country=user["country"],
#                 postal_code=user["postal_code"],
#                 role=user["role"],
#                 created_at=user.get("created_at")
#             ) for user in users
#         ]
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=f"Failed to fetch users: {str(e)}")

# @app.post("/users/{user_id}", response_model=UserResponse)
# async def get_user(user_id: int, current_user: dict = Depends(require_admin)):
#     """
#     Get specific user by ID (Admin only)
#     """
#     try:
#         user = database.single_user(user_id)
#         if user:
#             return UserResponse(
#                 id=user["id"],
#                 username=user["username"],
#                 email=user["email"],
#                 first_name=user["first_name"],
#                 last_name=user["last_name"],
#                 phone=user["phone"],
#                 address=user["address"],
#                 city=user["city"],
#                 country=user["country"],
#                 postal_code=user["postal_code"],
#                 role=user["role"],
#                 created_at=user.get("created_at")
#             )
#         else:
#             raise HTTPException(status_code=404, detail="User not found")
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=f"Failed to fetch user: {str(e)}")

# @app.put("/users/{user_id}", response_model=UserResponse)
# async def update_user(
#     user_id: int, 
#     user_update: UserUpdate,
#     current_user: dict = Depends(require_admin)
# ):
#     """
#     Update user information (Admin only)
#     """
#     try:
#         current_user_data = database.single_user(user_id)
#         if not current_user_data:
#             raise HTTPException(status_code=404, detail="User not found")
        
#         # Use provided values or keep existing ones
#         username = user_update.username or current_user_data["username"]
#         email = user_update.email or current_user_data["email"]
#         password = user_update.password or ""
#         first_name = user_update.first_name or current_user_data["first_name"]
#         last_name = user_update.last_name or current_user_data["last_name"]
#         phone = user_update.phone or current_user_data["phone"]
#         address = user_update.address or current_user_data["address"]
#         city = user_update.city or current_user_data["city"]
#         country = user_update.country or current_user_data["country"]
#         postal_code = user_update.postal_code or current_user_data["postal_code"]
        
#         data = (
#             username, email, password, first_name, last_name,
#             phone, address, city, country, postal_code, user_id
#         )
#         success = database.update(data)
        
#         if success:
#             updated_user = database.single_user(user_id)
#             if updated_user:
#                 return UserResponse(
#                     id=updated_user["id"],
#                     username=updated_user["username"],
#                     email=updated_user["email"],
#                     first_name=updated_user["first_name"],
#                     last_name=updated_user["last_name"],
#                     phone=updated_user["phone"],
#                     address=updated_user["address"],
#                     city=updated_user["city"],
#                     country=updated_user["country"],
#                     postal_code=updated_user["postal_code"],
#                     role=updated_user["role"],
#                     created_at=updated_user.get("created_at")
#                 )
#             else:
#                 raise HTTPException(status_code=500, detail="Failed to retrieve updated user")
#         else:
#             raise HTTPException(status_code=400, detail="Failed to update user - username or email may already exist")
#     except HTTPException:
#         raise
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=f"Update failed: {str(e)}")

# @app.delete("/users/{user_id}")
# async def delete_user(user_id: int, current_user: dict = Depends(require_admin)):
#     """
#     Delete a user (Admin only)
#     """
#     try:
#         success = database.delete(user_id)
#         if success:
#             return {"message": "User deleted successfully"}
#         else:
#             raise HTTPException(status_code=404, detail="User not found or cannot be deleted")
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=f"Deletion failed: {str(e)}")

# # Health check endpoint
# @app.get("/health")
# async def health_check():
#     return {"status": "healthy", "service": "user-management"}

# if __name__ == "__main__":
#     import uvicorn
#     uvicorn.run(app, host="0.0.0.0", port=8000)


from fastapi import FastAPI, HTTPException, Depends
from datetime import timedelta
from models import (
    UserCreate, UserResponse, UserUpdate, LoginRequest, Token,
    BaseResponse, UserBaseResponse, UsersListResponse, TokenResponse
)
from auth import (
    authenticate_user, create_access_token, get_current_active_user, 
    require_admin, ACCESS_TOKEN_EXPIRE_MINUTES
)
import database
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="User Management Service",
    description="Microservice for user authentication and management with JWT",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    allow_origins=["*"],
    expose_headers=["*"]
)

def create_user_response(user: dict) -> UserResponse:
    return UserResponse(
        id=user["id"], username=user["username"], email=user["email"],
        first_name=user["first_name"], last_name=user["last_name"],
        phone=user["phone"], address=user["address"], city=user["city"],
        country=user["country"], postal_code=user["postal_code"],
        role=user["role"], created_at=user.get("created_at")
    )

@app.post("/register", response_model=UserBaseResponse)
async def register(user: UserCreate):
    try:
        data = (user.username, user.email, user.password, user.first_name, 
                user.last_name, user.phone, user.address, user.city, 
                user.country, user.postal_code)
        success = database.reg(data)
        
        if success:
            new_user = database.get_user_by_username(user.username)
            if new_user:
                return BaseResponse(
                    success=True,
                    message="User registered successfully",
                    data=create_user_response(new_user)
                )
            raise HTTPException(status_code=500, detail="User created but cannot retrieve details")
        raise HTTPException(status_code=400, detail="Username or email already exists")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Registration failed: {str(e)}")

@app.post("/login", response_model=TokenResponse)
async def login(credentials: LoginRequest):
    user = authenticate_user(credentials.username, credentials.password)
    if not user:
        raise HTTPException(status_code=401, detail="Incorrect username or password",
                          headers={"WWW-Authenticate": "Bearer"})
    
    access_token = create_access_token(
        data={"sub": user["username"], "role": user["role"]},
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    
    return BaseResponse(
        success=True,
        message="Login successful",
        data=Token(access_token=access_token, token_type="bearer",
                   user=create_user_response(user))
    )

@app.post("/users/me", response_model=UserBaseResponse)
async def get_current_user_info(current_user: dict = Depends(get_current_active_user)):
    user = database.get_user_by_username(current_user["username"])
    if user:
        return BaseResponse(success=True, message="User retrieved successfully",
                          data=create_user_response(user))
    raise HTTPException(status_code=404, detail="User not found")

@app.put("/users/me", response_model=UserBaseResponse)
async def update_current_user(user_update: UserUpdate, 
                              current_user: dict = Depends(get_current_active_user)):
    try:
        user = database.get_user_by_username(current_user["username"])
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        data = (
            user_update.username or user["username"],
            user_update.email or user["email"],
            user_update.password or "",
            user_update.first_name or user["first_name"],
            user_update.last_name or user["last_name"],
            user_update.phone or user["phone"],
            user_update.address or user["address"],
            user_update.city or user["city"],
            user_update.country or user["country"],
            user_update.postal_code or user["postal_code"],
            user["id"]
        )
        
        if database.update(data):
            updated_user = database.single_user(user["id"])
            if updated_user:
                return BaseResponse(success=True, message="User updated successfully",
                                  data=create_user_response(updated_user))
            raise HTTPException(status_code=500, detail="Failed to retrieve updated user")
        raise HTTPException(status_code=400, detail="Failed to update user")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Update failed: {str(e)}")

@app.post("/users", response_model=UsersListResponse)
async def get_all_users(current_user: dict = Depends(require_admin)):
    try:
        users = database.show_all()
        return BaseResponse(
            success=True, message="Users retrieved successfully",
            data=[create_user_response(user) for user in users]
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch users: {str(e)}")

@app.post("/users/{user_id}", response_model=UserBaseResponse)
async def get_user(user_id: int, current_user: dict = Depends(require_admin)):
    user = database.single_user(user_id)
    if user:
        return BaseResponse(success=True, message="User retrieved successfully",
                          data=create_user_response(user))
    raise HTTPException(status_code=404, detail="User not found")

@app.put("/users/{user_id}", response_model=UserBaseResponse)
async def update_user(user_id: int, user_update: UserUpdate,
                     current_user: dict = Depends(require_admin)):
    try:
        current_data = database.single_user(user_id)
        if not current_data:
            raise HTTPException(status_code=404, detail="User not found")
        
        data = (
            user_update.username or current_data["username"],
            user_update.email or current_data["email"],
            user_update.password or "",
            user_update.first_name or current_data["first_name"],
            user_update.last_name or current_data["last_name"],
            user_update.phone or current_data["phone"],
            user_update.address or current_data["address"],
            user_update.city or current_data["city"],
            user_update.country or current_data["country"],
            user_update.postal_code or current_data["postal_code"],
            user_id
        )
        
        if database.update(data):
            updated_user = database.single_user(user_id)
            if updated_user:
                return BaseResponse(success=True, message="User updated successfully",
                                  data=create_user_response(updated_user))
            raise HTTPException(status_code=500, detail="Failed to retrieve updated user")
        raise HTTPException(status_code=400, detail="Failed to update user")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Update failed: {str(e)}")

@app.delete("/users/{user_id}", response_model=BaseResponse)
async def delete_user(user_id: int, current_user: dict = Depends(require_admin)):
    if database.delete(user_id):
        return BaseResponse(success=True, message="User deleted successfully", data=None)
    raise HTTPException(status_code=404, detail="User not found or cannot be deleted")

@app.get("/health")
async def health_check():
    return BaseResponse(success=True, message="Service is healthy", 
                       data={"status": "healthy", "service": "user-management"})

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)