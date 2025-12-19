from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List

import models
import schemas
import auth
import database

router = APIRouter(tags=["Authentication & Users"])

@router.post("/register", response_model=schemas.UserResponse)
async def register(user: schemas.UserCreate, db: AsyncSession = Depends(database.get_db)):
    # Check if email exists
    result = await db.execute(select(models.User).filter(models.User.email == user.email))
    if result.scalars().first():
        raise HTTPException(status_code=400, detail="Email already registered")
    
    # Create user
    hashed_password = auth.get_password_hash(user.password)
    db_user = models.User(
        email=user.email,
        password_hash=hashed_password,
        first_name=user.first_name,
        last_name=user.last_name,
        mobile=user.mobile,
        country=user.country,
        state=user.state,
        city=user.city,
        pincode=user.pincode
    )
    db.add(db_user)
    await db.commit()
    await db.refresh(db_user)
    return db_user

@router.post("/login", response_model=schemas.Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), db: AsyncSession = Depends(database.get_db)):
    # Authenticate user
    result = await db.execute(select(models.User).filter(models.User.email == form_data.username))
    user = result.scalars().first()
    
    if not user or not auth.verify_password(form_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token_expires = auth.timedelta(minutes=auth.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = auth.create_access_token(
        data={"sub": user.email}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

@router.get("/users/me", response_model=schemas.UserResponse)
async def read_users_me(current_user: models.User = Depends(auth.get_current_user), db: AsyncSession = Depends(database.get_db)):
    # Re-fetch user with submissions eagerly loaded
    result = await db.execute(
        select(models.User)
        .options(selectinload(models.User.submissions))
        .filter(models.User.id == current_user.id)
    )
    return result.scalars().first()

@router.get("/history", response_model=List[schemas.FormSubmissionResponse])
async def get_history(current_user: models.User = Depends(auth.get_current_user), db: AsyncSession = Depends(database.get_db)):
    result = await db.execute(
        select(models.FormSubmission)
        .filter(models.FormSubmission.user_id == current_user.id)
        .order_by(models.FormSubmission.timestamp.desc())
    )
    return result.scalars().all()
