from fastapi import FastAPI, Depends, HTTPException, status, BackgroundTasks
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import List
from . import models, schemas, database, auth
from .database import engine

models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="WhatsApp Broadcast SaaS")

# CORS
origins = ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_db():
    return database.get_db()


# --- Auth Routes ---
@app.post("/signup", response_model=schemas.User)
def signup(user: schemas.UserCreate, db: Session = Depends(database.get_db)):
    db_user = db.query(models.User).filter(models.User.email == user.email).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Email already registered")

    # Create Organization first
    new_org = models.Organization(name=user.organization_name)
    db.add(new_org)
    db.commit()
    db.refresh(new_org)

    # Create User
    print(f"Hashing password for {user.email}")
    hashed_password = auth.get_password_hash(user.password)
    print(f"Password hashed: {hashed_password}")
    db_user = models.User(
        email=user.email,
        hashed_password=hashed_password,
        full_name=user.full_name,
        organization_id=new_org.id,
        role="admin",
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user


@app.post("/token", response_model=schemas.Token)
def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(database.get_db),
):
    user = db.query(models.User).filter(models.User.email == form_data.username).first()
    if not user or not auth.verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token = auth.create_access_token(data={"sub": user.email})
    return {"access_token": access_token, "token_type": "bearer"}


@app.get("/users/me", response_model=schemas.User)
def read_users_me(current_user: models.User = Depends(auth.get_current_user)):
    return current_user


@app.put("/users/me", response_model=schemas.User)
def update_user_me(
    user_update: schemas.UserUpdate,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    # Determine if we need to update fields
    if user_update.full_name:
        current_user.full_name = user_update.full_name

    # Only update password if provided and not empty/dummy
    if user_update.password and len(user_update.password) > 3:
        current_user.hashed_password = auth.get_password_hash(user_update.password)

    db.commit()
    db.refresh(current_user)
    return current_user


# --- Member Routes ---
@app.get("/members", response_model=List[schemas.Member])
def read_members(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    members = (
        db.query(models.Member)
        .filter(models.Member.organization_id == current_user.organization_id)
        .offset(skip)
        .limit(limit)
        .all()
    )
    return members


@app.post("/members", response_model=schemas.Member)
def create_member(
    member: schemas.MemberCreate,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    # Check limit (MVP: 1000 members)
    count = (
        db.query(models.Member)
        .filter(models.Member.organization_id == current_user.organization_id)
        .count()
    )
    if count >= 1000:
        raise HTTPException(status_code=400, detail="Member limit reached (1000)")

    db_member = models.Member(
        **member.dict(), organization_id=current_user.organization_id
    )
    db.add(db_member)
    db.commit()
    db.refresh(db_member)
    return db_member


@app.put("/members/{member_id}", response_model=schemas.Member)
def update_member(
    member_id: int,
    member_update: schemas.MemberUpdate,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    db_member = (
        db.query(models.Member)
        .filter(
            models.Member.id == member_id,
            models.Member.organization_id == current_user.organization_id,
        )
        .first()
    )
    if not db_member:
        raise HTTPException(status_code=404, detail="Member not found")

    if member_update.name:
        db_member.name = member_update.name
    if member_update.phone_number:
        db_member.phone_number = member_update.phone_number

    db.commit()
    db.refresh(db_member)
    return db_member


@app.delete("/members/{member_id}")
def delete_member(
    member_id: int,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    db_member = (
        db.query(models.Member)
        .filter(
            models.Member.id == member_id,
            models.Member.organization_id == current_user.organization_id,
        )
        .first()
    )
    if not db_member:
        raise HTTPException(status_code=404, detail="Member not found")

    # Manually delete logs first (Cascade handling for SQLite/No-Migration env)
    db.query(models.BroadcastLog).filter(
        models.BroadcastLog.member_id == member_id
    ).delete()

    db.delete(db_member)
    db.commit()
    return {"detail": "Member deleted"}


# --- Broadcast Logic ---
def process_broadcast(broadcast_id: int, db: Session):
    # This runs in background
    broadcast = (
        db.query(models.Broadcast).filter(models.Broadcast.id == broadcast_id).first()
    )
    if not broadcast:
        return

    # Get active members
    members = (
        db.query(models.Member)
        .filter(
            models.Member.organization_id == broadcast.organization_id,
            models.Member.status == models.MemberStatus.ACTIVE,
        )
        .all()
    )

    broadcast.status = models.BroadcastStatus.PROCESSING
    db.commit()

    for member in members:
        # Create Log
        log = models.BroadcastLog(
            broadcast_id=broadcast.id,
            member_id=member.id,
            status="sent",  # Optimistic for MVP
        )
        db.add(log)

        # Simulate WhatsApp Send
        print(f"[{member.phone_number}] Sending Message: {broadcast.content}")

        # In real app, call WA API here
        # try:
        #    wa_api.send(member.phone, broadcast.content)
        #    log.status = "delivered"
        # except Exception as e:
        #    log.status = "failed"
        #    log.error_reason = str(e)

    broadcast.status = models.BroadcastStatus.COMPLETED
    db.commit()


@app.post("/broadcasts", response_model=schemas.Broadcast)
def create_broadcast(
    broadcast: schemas.BroadcastCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    db_broadcast = models.Broadcast(
        **broadcast.dict(), organization_id=current_user.organization_id
    )
    db.add(db_broadcast)
    db.commit()
    db.refresh(db_broadcast)

    # Enqueue job
    background_tasks.add_task(process_broadcast, db_broadcast.id, db)

    return db_broadcast


@app.get("/broadcasts", response_model=List[schemas.Broadcast])
def read_broadcasts(
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    return (
        db.query(models.Broadcast)
        .filter(models.Broadcast.organization_id == current_user.organization_id)
        .all()
    )
