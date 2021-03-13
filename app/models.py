from datetime import datetime
from dateutil.parser import isoparse
from typing import Any, Dict, List, Optional

import pydantic

class UpdatedPost(pydantic.BaseModel):
    title: str
    author_email: str
    content: str

class NewPost(UpdatedPost):
    slug: str

class Post(NewPost):
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_dynamo_item(cls, item: Dict[str, Dict[str, Any]]) -> 'Post':
        return cls(
            slug=item['Slug']['S'],
            title=item['Title']['S'],
            content=item['Content']['S'],
            author_email=item['AuthorEmail']['S'],
            created_at=isoparse(item['CreatedAt']['S']),
            updated_at=isoparse(item['UpdatedAt']['S']),
        )

class PostListItem(pydantic.BaseModel):
    title: str
    author_email: str
    slug: str
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_dynamo_item(cls, item: Dict[str, Dict[str, Any]]) -> 'PostListItem':
        return cls(
            slug=item['Slug']['S'],
            title=item['Title']['S'],
            author_email=item['AuthorEmail']['S'],
            created_at=isoparse(item['CreatedAt']['S']),
            updated_at=isoparse(item['UpdatedAt']['S']),
        )

class PostList(pydantic.BaseModel):
    posts: List[PostListItem]
    nextPageToken: Optional[str]
    prevPageToken: Optional[str]

class UpdateComment(pydantic.BaseModel):
    content: str

class NewComment(UpdateComment):
    author_email: str

class Comment(NewComment):
    post_slug: str
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_dynamo_item(cls, item: Dict[str, Dict[str, Any]]) -> 'Comment':
        return cls(
            post_slug=item['Slug']['S'],
            author_email=item['AuthorEmail']['S'],
            created_at=isoparse(item['CreatedAt']['S']),
            updated_at=isoparse(item['UpdatedAt']['S']),
            content=item['Content']['S'],
        )

class CommentList(pydantic.BaseModel):
    comments: List[Comment]
    nextPageToken: Optional[str]
    prevPageToken: Optional[str]

class UpdateUser(pydantic.BaseModel):
    first_name: str
    last_name: str
    role: str

class NewUser(UpdateUser):
    email: str

class User(NewUser):
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_dynamo_item(cls, item: Dict[str, Dict[str, Any]]) -> 'User':
        return cls(
            first_name=item['FirstName']['S'],
            last_name=item['LastName']['S'],
            role=item['Role']['S'],
            email=item['PK']['S'].split('#')[2:],
            created_at=isoparse(item['CreatedAt']['S']),
            updated_at=isoparse(item['UpdatedAt']['S']),
        )

class UserList(pydantic.BaseModel):
    users: List[User]
    nextpageToken: Optional[str]
    prevPageToken: Optional[str]
