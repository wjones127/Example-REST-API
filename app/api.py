import logging
import os
from typing import Optional

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from mangum import Mangum
from botocore.exceptions import ClientError

from models import NewPost, Post, PostList, UpdatedPost
import store as store

URL_BASE = '/' + os.environ['BASE_PATH']

logger = logging.getLogger()
logger.setLevel(logging.INFO)

app = FastAPI(
    title="Blog API",
    description="Example blog API",
    version="1.0.0",
    docs_url=URL_BASE + '/swagger',
    openapi_url=URL_BASE + '/openapi.json',
    redoc_url=None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

handler = Mangum(app)

@app.get(URL_BASE + '/post', response_model=PostList)
def list_posts(pageToken: Optional[str]=None, limit: int=2):
    '''List posts in the blog, ordered by created date (descending)'''
    return store.list_posts(pageToken, limit)

@app.post(URL_BASE + '/post', response_model=Post)
def create_post(post: NewPost):
    '''Creates a new post. slug must be unique.'''
    try:
        return store.create_post(post)
    except ClientError as e:  
        if e.response['Error']['Code']=='ConditionalCheckFailedException': 
            return JSONResponse(content={"error":"Post slug already exists"}, status_code=400)

@app.get(URL_BASE + '/post/{slug}', response_model=Post)
def get_post(slug: str):
    return store.get_post(slug)

@app.put(URL_BASE + '/post/{slug}', response_model=Post)
def update_post(slug: str, post: UpdatedPost):
    return store.update_post(slug, post)

@app.delete(URL_BASE + '/post/{slug}', status_code=204)
def delete_post(slug: str):
    store.delete_post(slug)
    return ''

if __name__ == '__main__':
    import argparse
    import uvicorn
    parser = argparse.ArgumentParser()
    parser.add_argument('--host')
    parser.add_argument('--port', type=int)
    args = parser.parse_args()

    uvicorn.run(app, host=args.host, port=args.port, log_level='info')