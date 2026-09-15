from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User, UserRole
from app.schemas import UserRegisterRequest, UserLoginRequest, TokenResponse, UserResponse
from app.auth import hash_password, verify_password, create_access_token, get_current_user

router = APIRouter(prefix="/auth", tags=["Authentication"])

@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(request: UserRegisterRequest, db: Session = Depends(get_db)):
    """Registers a new user, hashes password with bcrypt, and returns a JWT token."""
    # Check for existing email
    existing_user = db.query(User).filter(User.email == request.email.lower().strip()).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An account with this email already exists"
        )
    
    # Enforce valid role
    assigned_role = UserRole.MEMBER.value
    if request.role and request.role.lower() == UserRole.ADMIN.value:
        assigned_role = UserRole.ADMIN.value

    # Hash password with bcrypt
    hashed_pwd = hash_password(request.password)

    # Create new user
    new_user = User(
        email=request.email.lower().strip(),
        password_hash=hashed_pwd,
        role=assigned_role,
        confidence_threshold=0.75
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    # Generate JWT token
    token_payload = {
        "sub": str(new_user.id),
        "email": new_user.email,
        "role": new_user.role
    }
    access_token = create_access_token(token_payload)

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        user=UserResponse.model_validate(new_user)
    )

@router.post("/login", response_model=TokenResponse)
def login(request: UserLoginRequest, db: Session = Depends(get_db)):
    """Authenticates a user by email and password, returning a JWT token on success."""
    clean_email = request.email.lower().strip()
    user = db.query(User).filter(User.email == clean_email).first()
    
    is_valid = verify_password(request.password, user.password_hash) if user else False
    print(f"[AUTH_DEBUG] login: email='{clean_email}', db_url='{db.bind.url}', user_found={user is not None}, user_id={user.id if user else None}, pass_verified={is_valid}")

    if not user or not is_valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Generate JWT token
    token_payload = {
        "sub": str(user.id),
        "email": user.email,
        "role": user.role
    }
    access_token = create_access_token(token_payload)

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        user=UserResponse.model_validate(user)
    )

@router.get("/me", response_model=UserResponse)
def get_current_user_profile(current_user: User = Depends(get_current_user)):
    """Protected endpoint to retrieve the authenticated user's profile from JWT."""
    return UserResponse.model_validate(current_user)
