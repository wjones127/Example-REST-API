import logging
import os
from typing import Optional

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from mangum import Mangum
from dateutil.parser import isoparse

from models import (Comment, NewComment, NewPost, Post, PostList, UpdateComment,
    UpdatedPost, CommentList, User, NewUser, UpdateUser, UserList)
import store as store

URL_BASE = '/' + os.environ['BASE_PATH']

logger = logging.getLogger()
logger.setLevel(logging.INFO)

tags_metadata = [
    {
        "name": "posts",
        "description": "Operations with posts.",
    },
    {
        "name": "comments",
        "description": "Operations with comments on posts.",
    },
    {
        "name": "users",
        "description": "Operations with users.",
    },
]

app = FastAPI(
    title="Blog API",
    description="Example blog API",
    version="1.0.0",
    docs_url=URL_BASE + '/swagger',
    openapi_url=URL_BASE + '/openapi.json',
    redoc_url=None,
    openapi_tags=tags_metadata,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

handler = Mangum(app)

@app.get(URL_BASE + '/posts', response_model=PostList, tags=['posts'])
def list_posts(pageToken: Optional[str]=None, limit: int=20):
    '''List posts in the blog, ordered by created date (descending)'''
    try:
        return store.list_posts(pageToken, limit)
    except store.InvalidPageTokenError:
        return JSONResponse(content={'error': 'pageToken is invalid'}, status_code=400)

@app.post(URL_BASE + '/posts', response_model=Post, tags=['posts'])
def create_post(post: NewPost):
    '''Creates a new post. slug must be unique.
    
    The author specified in author_email must exist and must have the role 'Author'.'''
    try:
        author = store.get_user(post.author_email)
        assert author.role == 'Author'
    except store.NotFoundError:
        return JSONResponse(content={'error': 'User does not exist'}, status_code=400)
    except AssertionError:
        return JSONResponse(content={'error': 'User is not an author'}, status_code=400)

    try:
        return store.create_post(post)
    except store.ResourceAlreadyExistsError:
        return JSONResponse(content={"error": "Post slug already exists"}, status_code=400)

@app.get(URL_BASE + '/posts/{slug}', response_model=Post, tags=['posts'])
def get_post(slug: str):
    return store.get_post(slug)

@app.put(URL_BASE + '/posts/{slug}', response_model=Post, tags=['posts'])
def update_post(slug: str, post: UpdatedPost):
    try:
        author = store.get_user(post.author_email)
        assert author.role == 'Author'
    except store.NotFoundError:
        return JSONResponse(content={'error': 'User does not exist'}, status_code=400)
    except AssertionError:
        return JSONResponse(content={'error': 'User is not an author'}, status_code=400)
    
    return store.update_post(slug, post)

@app.delete(URL_BASE + '/posts/{slug}', status_code=204, tags=['posts'])
def delete_post(slug: str):
    store.delete_post(slug)
    return ''

@app.get(URL_BASE + '/comments/', response_model=CommentList, tags=['comments'])
def list_comments(pageToken: Optional[str]=None, limit: int=20):
    try:
        return store.list_comments(pageToken, limit)
    except store.InvalidPageTokenError:
        return JSONResponse(content={'error': 'pageToken is invalid'}, status_code=400)

@app.post(URL_BASE + '/posts/{slug}/comments/', response_model=Comment, tags=['comments'])
def create_comment(slug: str, comment: NewComment):
    try:
        store.get_user(comment.author_email)
    except store.NotFoundError:
        return JSONResponse(content={'error': 'User does not exist'}, status_code=400)

    try:
        return store.create_comment(slug, comment)
    except store.ResourceAlreadyExistsError:
        return JSONResponse(content={"error": "Too many comments at once"}, status_code=429)

@app.get(URL_BASE + '/posts/{slug}/comments/', response_model=CommentList, tags=['comments'])
def list_comments_for_post(slug: str, pageToken: Optional[str]=None, limit: int=2):
    try:
        return store.list_comments_for_post(slug, pageToken, limit)
    except store.InvalidPageTokenError:
        return JSONResponse(content={'error': 'pageToken is invalid'}, status_code=400)

@app.put(URL_BASE + '/posts/{slug}/comments/{author}/{date}', response_model=Comment, tags=['comments'])
def update_comment(slug: str, author: str, date: str, comment: UpdateComment):
    return store.update_comment(slug, author, isoparse(date), comment)

@app.delete(URL_BASE + '/posts/{slug}/comments/{author}/{date}', status_code=204, tags=['comments'])
def delete_comment(slug: str, author: str, date: str):
    store.delete_comment(slug, author, isoparse(date))
    return ''


@app.post(URL_BASE + '/users/', response_model=User, tags=['users'])
def create_user(user: NewUser):
    try:
        return store.create_user(user)
    except store.ResourceAlreadyExistsError:
        return JSONResponse(content={"error": "User already exists with that email"}, status_code=400)

@app.get(URL_BASE + '/users/{email}/', response_model=User, tags=['users'])
def get_user(email: str):
    try:
        return store.get_user(email)
    except store.NotFoundError:
        return JSONResponse(content={"error": "User not found"}, status_code=404)

@app.put(URL_BASE + '/users/{email}/', response_model=User, tags=['users'])
def update_user(email: str, user: UpdateUser):
    return store.update_user(email, user)

@app.delete(URL_BASE + '/users/{email}/', status_code=204, tags=['users'])
def delete_user(email: str):
    store.delete_user(email)
    return ''

@app.get(URL_BASE + '/users/', response_model=UserList, tags=['users'])
def list_users(pageToken: Optional[str]=None, limit: int=20):
    try:
        return store.list_users(pageToken, limit)
    except store.InvalidPageTokenError:
        return JSONResponse(content={'error': 'pageToken is invalid'}, status_code=400)

@app.get(URL_BASE + '/users/{email}/posts', response_model=PostList, tags=['posts'])
def list_posts_for_author(email: str, pageToken: Optional[str]=None, limit: int=20):
    '''List posts in the blog, ordered by created date (descending)'''
    try:
        return store.list_posts_for_author(email, pageToken, limit)
    except store.InvalidPageTokenError:
        return JSONResponse(content={'error': 'pageToken is invalid'}, status_code=400)

@app.get(URL_BASE + '/users/{email}/comments', response_model=PostList, tags=['comments'])
def list_comments_for_author(email: str, pageToken: Optional[str]=None, limit: int=20):
    '''List posts in the blog, ordered by created date (descending)'''
    try:
        return store.list_comments_for_author(email, pageToken, limit)
    except store.InvalidPageTokenError:
        return JSONResponse(content={'error': 'pageToken is invalid'}, status_code=400)


if __name__ == '__main__':
    import argparse
    import uvicorn
    parser = argparse.ArgumentParser()
    parser.add_argument('--host')
    parser.add_argument('--port', type=int)
    args = parser.parse_args()

    uvicorn.run(app, host=args.host, port=args.port, log_level='info')