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
