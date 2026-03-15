from fastapi import FastAPI, HTTPException, Depends, status, Response
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel
from typing import List, Optional
import bcrypt
import psycopg2
from psycopg2.extras import RealDictCursor
import os
import jwt
from datetime import datetime, timedelta

app = FastAPI(title='Todo API')

# Configuration
DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://user:password@localhost:5432/todo_db')
SECRET_KEY = os.getenv('SECRET_KEY', 'your-secret-key')
ALGORITHM = 'HS256'
ACCESS_TOKEN_EXPIRE_MINUTES = 30

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")

def get_db_conn():
    conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
    try:
        yield conn
    finally:
        conn.close()

class UserCreate(BaseModel):
    username: str
    password: str

class UserResponse(BaseModel):
    id: int
    username: str

    class Config:
        from_attributes = True

class Token(BaseModel):
    access_token: str
    token_type: str

class TodoCreate(BaseModel):
    title: str
    description: Optional[str] = None

class TodoUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    completed: Optional[bool] = None

class TodoResponse(BaseModel):
    id: int
    title: str
    description: Optional[str]
    completed: bool
    user_id: int

    class Config:
        from_attributes = True

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({'exp': expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        user_id: int = payload.get("user_id")
        if username is None or user_id is None:
            raise credentials_exception
        return {"username": username, "id": user_id}
    except jwt.PyJWTError:
        raise credentials_exception

@app.post('/users', response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_user(user: UserCreate, conn = Depends(get_db_conn)):
    cursor = conn.cursor()
    cursor.execute('SELECT id FROM users WHERE username = %s', (user.username,))
    if cursor.fetchone():
        raise HTTPException(status_code=400, detail='Username already registered')
    
    hashed_password = bcrypt.hashpw(user.password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    cursor.execute(
        'INSERT INTO users (username, password_hash) VALUES (%s, %s) RETURNING id, username',
        (user.username, hashed_password)
    )
    new_user = cursor.fetchone()
    conn.commit()
    return new_user

@app.post('/login', response_model=Token)
def login(user_data: UserCreate, conn = Depends(get_db_conn)):
    cursor = conn.cursor()
    cursor.execute('SELECT id, username, password_hash FROM users WHERE username = %s', (user_data.username,))
    user = cursor.fetchone()
    
    if not user or not bcrypt.checkpw(user_data.password.encode('utf-8'), user['password_hash'].encode('utf-8')):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail='Incorrect username or password',
            headers={'WWW-Authenticate': 'Bearer'},
        )
    
    access_token = create_access_token(data={'sub': user['username'], 'user_id': user['id']})
    return {'access_token': access_token, 'token_type': 'bearer'}

@app.get('/todos', response_model=List[TodoResponse])
def get_todos(current_user: dict = Depends(get_current_user), conn = Depends(get_db_conn)):
    cursor = conn.cursor()
    cursor.execute('SELECT id, title, description, completed, user_id FROM todos WHERE user_id = %s', (current_user['id'],))
    todos = cursor.fetchall()
    return todos

@app.post('/todos', response_model=TodoResponse, status_code=status.HTTP_201_CREATED)
def create_todo(todo: TodoCreate, current_user: dict = Depends(get_current_user), conn = Depends(get_db_conn)):
    cursor = conn.cursor()
    cursor.execute(
        'INSERT INTO todos (title, description, user_id) VALUES (%s, %s, %s) RETURNING id, title, description, completed, user_id',
        (todo.title, todo.description, current_user['id'])
    )
    new_todo = cursor.fetchone()
    conn.commit()
    return new_todo

@app.get('/todos/{todo_id}', response_model=TodoResponse)
def get_todo(todo_id: int, current_user: dict = Depends(get_current_user), conn = Depends(get_db_conn)):
    cursor = conn.cursor()
    cursor.execute(
        'SELECT id, title, description, completed, user_id FROM todos WHERE id = %s AND user_id = %s',
        (todo_id, current_user['id'])
    )
    todo = cursor.fetchone()
    if not todo:
        raise HTTPException(status_code=404, detail='Todo not found')
    return todo

@app.put('/todos/{todo_id}', response_model=TodoResponse)
def update_todo(todo_id: int, todo_update: TodoUpdate, current_user: dict = Depends(get_current_user), conn = Depends(get_db_conn)):
    cursor = conn.cursor()
    cursor.execute('SELECT id FROM todos WHERE id = %s AND user_id = %s', (todo_id, current_user['id']))
    if not cursor.fetchone():
        raise HTTPException(status_code=404, detail='Todo not found')
    
    update_data = todo_update.dict(exclude_unset=True)
    if not update_data:
        cursor.execute('SELECT id, title, description, completed, user_id FROM todos WHERE id = %s', (todo_id,))
        return cursor.fetchone()
    
    set_clause = ", ".join([f"{k} = %s" for k in update_data.keys()])
    values = list(update_data.values())
    values.append(todo_id)
    query = f"UPDATE todos SET {set_clause}, updated_at = CURRENT_TIMESTAMP WHERE id = %s RETURNING id, title, description, completed, user_id"
    cursor.execute(query, values)
    updated_todo = cursor.fetchone()
    conn.commit()
    return updated_todo

@app.delete('/todos/{todo_id}', status_code=status.HTTP_204_NO_CONTENT)
def delete_todo(todo_id: int, current_user: dict = Depends(get_current_user), conn = Depends(get_db_conn)):
    cursor = conn.cursor()
    cursor.execute('DELETE FROM todos WHERE id = %s AND user_id = %s RETURNING id', (todo_id, current_user['id']))
    if not cursor.fetchone():
        raise HTTPException(status_code=404, detail='Todo not found')
    conn.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
